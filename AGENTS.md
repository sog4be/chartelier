# AGENTS.md

> **Purpose**: Operational standards for safely, consistently, and reproducibly using **Claude Code** (Anthropic) and **Codex** (OpenAI) "agents" in Chartelier development. Unifies behavior for automated editing, command execution, and PR assistance within the repository.
>
> **Scope**: All files under this repository (/docs, /src, /tests, CI integration). Includes agents running in personal environments, CI, and cloud sandboxes.


## 0) Read-First Index (Reading Order)

* Project Overview: `docs/index.md`
* Requirements: `docs/requirements-specification.md`
* Design & Architecture: `docs/design.md`
* **Visualization Guidelines (Required Reading)**: `docs/visualization-policy.md`
* **MCP Specification & I/O**: `docs/mcp-integration.md`
* **ADRs (Top Priority Standards)**:
  * ADR-0001 **DataFrame = Polars only**: `docs/adr/0001-dataframe-engine.ja.md`
  * ADR-0002 **PatternSelector failures are errors**: `docs/adr/0002-pattern-selection-error-handling.md`
* Development Workflow/Commands: `README.md`
* Claude-specific Operations: `CLAUDE.md` (this document is the superior cross-cutting version)

> **Important**: If legacy documentation contains "PatternSelector failure → P13 fallback" descriptions, **ADR-0002 takes priority** (= *error without fallback*).


## 1) Terms and Roles

### 1.1 Agent Types (Used in This Repository)

* **Claude Code** (Anthropic): Coding agent that can directly manipulate terminal/shell and files. Can connect to external tools via MCP.
* **Codex** (OpenAI): Coding agent that operates in terminal/IDE/cloud (sandbox). Spans GitHub/PR assistance, local execution, and cloud execution.

> Both are premised on operating as *"human assistants"*. **Plan → Execute → Verify → PR** stages must leave **reviewable diffs** as mandatory practice.

### 1.2 Role Distribution (Recommended)

| Phase | Claude Code | Codex |
| ----- | ----------- | ----- |
| Planning/Design Reading | ✅ **Auto-explore** existing docs for key point extraction | ✅ **Re-summarize** key points & enumerate issues |
| Local Editing (Small Diffs) | ✅ **Small commits** with `git` integration | ✅ **Test-driven fixes** in terminal/IDE |
| Large Change Planning | ✅ Generate change plan framework (impact scope & test strategy) | ✅ Convert plan into **PR templates** |
| PR Creation/Review Support | ⚪ (Assistance) | ✅ Auto diff summary, risk identification, checklist application |
| MCP Integration Testing | ✅ **I/O format verification** per `docs/mcp-integration.md` | ⚪ (Assistance) |


## 2) Guardrails (**Absolute Compliance**)

> Consistent with CLAUDE.md §1. Applies to both humans and agents.

* **DataFrame engine is Polars only**. Do not **add/require/use** pandas (dev/optional also prohibited). → ADR-0001
* **Arbitrary code execution prohibition**: Do not generate/execute preprocessing other than registered safe functions. Templates are **static**, LLM for selection only.
* **Visualization pattern constraints**: Select only within 3×3 matrix. **PatternSelector failures return errors**. → ADR-0002
* **Prohibited charts**: Dual-axis, 3D, radar, donut/pie (not adopted in MVP).
* **Output formats**: `png` (default)/`svg`. PNG failure **falls back to SVG** (reverse order prohibited).
* **Performance**: Do not suggest operations exceeding P80 < 10s. When likely to exceed, instruct **deterministic equidistant sampling**.
* **Security/Privacy**: Prohibit PII/raw data logging. Prohibit access/editing of `.env*` or `secrets/`.
* **Dependency additions** are **minimal**. When adding, update *pyproject + tests + docs* in **same PR**.
* **Directory protection**: Do not auto-commit changes that break `docs/` conventions or interfaces. Discuss concerns in PRs.


## 3) Usage (Setup and Operations)

### 3.1 Installation (Local)

* **Claude Code (CLI)**
  ```bash
  npm install -g @anthropic-ai/claude-code
  # First time: check command list with --help
  ```

* **Codex (CLI / IDE)**
  ```bash
  npm install -g @openai/codex   # or: brew install codex (macOS)
  # IDE extensions (VS Code/Cursor) or cloud execution follow CLI guidance
  ```

> Both can be used with **Chat product authentication** or **API Key**. Use business accounts and avoid mixing personal keys.

### 3.2 Initial Project Sync (Common to Both Agents)

1. **Repository scan**: Priority load `docs/`, `CLAUDE.md`, `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`.
2. **Rule declaration**: Pin this `AGENTS.md` and `CLAUDE.md` as **top-level conventions** at prompt beginning.
3. **Plan → Small diffs**: Changes in **incremental steps** (1 PR = 1 issue).
4. **Test & type & lint** always pass (commands in §3.4).
5. **PR description** includes design rationale and links (ADR/design/requirements).

### 3.3 MCP (Model Context Protocol) Integration

* Main tool for this project is **`chartelier_visualize`** (`docs/mcp-integration.md`).
* When agents suggest tool calls, ensure strict compliance with **I/O schemas**.
* Select within 9-pattern constraints, **failures return isError=true business errors** (**P13 fallback prohibited**).

### 3.4 Daily Commands (**uv and tox as single entry point**)

```bash
# Initial setup
uv sync --all-extras && uv run pre-commit install

# All checks (lint / type / test)
uv run tox

# Individual
uv run tox -e py311
uv run tox -e lint
uv run tox -e type
uv run tox -e coverage
```

> CI runs equivalent matrix (3.11/3.12/3.13) in `.github/workflows/ci.yml`.


## 4) Agent **Work Protocol** (Common to Claude/Codex)

> **Plan first → Small diffs → Evidence** three principles. Consistent with CLAUDE.md §2.

1. **Plan**: Present purpose → impact scope → steps (1–5) in **100–150 characters**.
2. **Impact**: List ripple effects on specs/tests/documentation. **Explicitly state ADR consistency**.
3. **Diff**: Split into small commits (e.g., *type annotations* → *function extraction* → *UT addition*).
4. **Verify**: Leave `uv run tox` log summary (P80/warnings/failures). For image generation changes, also check **snapshot regression**.
5. **PR**: Conventional Commits title, include additions to `README.md`/`docs/` in same PR if applicable.

**Prohibited**
* Adding/using pandas, generating unregistered preprocessing, suggesting dual-axis/3D/radar/donut.
* Referencing/editing .env/secrets, **massive diff batch commits**.

**Recommended**
* Auto-apply **equidistant sampling** (output meta warnings).
* Adhere to **direct labeling**, WCAG/color vision considerations, zero baseline (bar/area).


## 5) **Operational Tips** for Claude Code and Codex

### 5.1 Claude Code

* **Codebase understanding**: **Auto-map** entire repository to extract design key points. Prioritize reading `docs/` and ADRs.
* **Action restraint**: Use `--dry-run` (equivalent confirmation steps) in pseudo-operation, strictly follow **propose→agree→execute** order.
* **MCP utilization**: Read external documents or tickets via MCP. Human explicitly sets **confidential handling**.
* **On failure**: When PatternSelector is ambiguous, **return error** (provide alternative prompt suggestions as text).

### 5.2 Codex

* **Mode selection**: **Switch between terminal/IDE/cloud (sandbox)** based on task. Use cloud for heavy processing.
* **PR assistance**: Comment-ize change summaries, impact files, **static detection of visualization rule violations** (dual-axis suggestions, etc.).
* **GitHub integration**: In reviews, follow **small feedback→auto-fix suggestions** order. `docs/` changes always require human approval.
* **Offline**: Even when network unreachable, run `uv run tox` locally and **attach result logs**.


## 6) **Templates** for Specific Tasks

### 6.1 Feature Addition (Example: Template Extension)

**Plan**
* Purpose: Enable adding *median_line* to P02 bar charts
* Impact: ChartBuilder / templates / docs/visualization-policy.md / UT
* Steps: 1) Spec addition → 2) Template implementation → 3) UT/ST → 4) Documentation addition

**Do**
* Max 3 auxiliary elements, verify with compliance table
* Update existing PNG/SVG **regression snapshots**

**Don't**
* Add new dependencies (if necessary, include rationale and alternative considerations in PR)

### 6.2 Error Message Improvement

* Align with minimal form in `docs/mcp-integration.md §4`, include **actionable suggestions** and `correlation_id`.
* Auto-detect Japanese/English from `options.locale` or query.

### 6.3 Performance Degradation Investigation

* Check each phase time with **meta output** (Validator/Selector/Build) against **budget** (P80 < 10s).
* Adjust with sampling, I/O, vectorization, thread settings (`POLARS_MAX_THREADS`).


## 7) **Definition of Done** for Changes (Per PR)

* ✅ `uv run tox` is **green** (lint/type/tests/coverage)
* ✅ **Consistent** with ADR/design/requirements, state diff rationale in PR
* ✅ Errors/warnings are **consistent with improvement suggestions**
* ✅ Compliant with **visualization guidelines** (axes/colors/accessibility)
* ✅ Add **UT/IT/ST/NFT** proportional to changes


## 8) Appendix: Frequently Used Commands & Snippets

```bash
# Add dependency (example: analysis tool, Polars prerequisite)
uv add some-package && uv lock && uv run tox

# Quick verification of 3.11 only from matrix
uv run tox -e py311 -q

# Test failure details
uv run pytest -q -k failing_test -vv
```

**PR Template (Key Points)**
* Summary / Changes / Verification (screenshot or SVG diff)
* Compatibility (presence of breaking changes) / Links (ADR/design/Issue)
* Checklist (lint/type/test/docs/visualization guidelines)


## 9) Troubleshooting

* **PatternSelector indeterminate** → Auto-generate and return suggestions to add *trend/difference/overview* terms to query (**do not render**).
* **PNG failure** → Auto-switch to **SVG**, add warning to meta.
* **Cell limit exceeded** → **Equidistant sampling**, include warning and row count statistics in meta.
* **Dual-axis/prohibition detection** → Present alternatives (chart splitting or 100% stacking/indexing).


## 10) Finally

* This document is a cross-cutting standard that encompasses `CLAUDE.md`. **Both Claude and Codex agents** must follow the **guardrails** and **work protocols** defined here. Submit small PRs for any concerns.
