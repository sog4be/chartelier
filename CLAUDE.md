# CLAUDE.md

**Goal:** Generate honest, reproducible static charts (PNG/SVG) from CSV/JSON via a constrained, MCP-compliant pipeline—fast (P80 < 10s), safe (no arbitrary code), and deterministic.

Keep your responses concise; when details are needed, open the referenced docs and follow them.

## 0) Read-First Index (open these when needed)

- Project overview: `docs/index.md`
- Requirements: `docs/requirements-specification.md`
- Design & components: `docs/design.md`
- Visualization rules (mandatory): `docs/visualization-policy.md`
- MCP integration (tool schema, error policy): `docs/mcp-integration.md`
- ADRs (decisions are normative):
    - ADR-0001 Polars-only DataFrame engine: `docs/adr/0001-dataframe-engine.ja.md`
    - ADR-0002 Pattern selection error handling: `docs/adr/0002-pattern-selection-error-handling.md`
- Dev workflow (commands live here too): `README.md`

> When you need specifics, reference files using @ (e.g., "See @docs/design.md §6.3").
> Do not bulk-quote long docs into chat unless necessary.

## 1) Guardrails (Hard Rules)

- **DataFrame engine:** **Use Polars only.** Do **not** add or rely on pandas (including dev/optional dependencies). Ref: ADR-0001.
- **Arbitrary code:** Prohibited. Pre-processing must use only registered safe functions (Design §6.3 / Visualization Policy).
- **Visualization patterns:** Within 3×3 matrix range (P01–P32). PatternSelector failures must **return as errors**.
- **Output:** PNG (Base64)/SVG only. Dependencies like `vl-convert` must follow design policies. Fallback order: **PNG→SVG**.
- **Performance budget:** P80 < 10s (Design §10.1). Heavy inputs require **deterministic equidistant sampling** (cell limit 1,000,000).
- **Security & privacy:** No PII or raw data in logs. Do not touch `.env*` or `secrets/` (ask humans if needed).
- **Dependencies:** When additions are needed, **minimize** and update `pyproject.toml`, tests, and documentation simultaneously. Pandas is prohibited.
- **Forbidden charts:** Dual-axis, 3D, radar, donut/pie (not adopted in MVP). Follow Visualization Policy.

## 2) Collaboration Protocol (How to Work With Me)

1. **Plan first.** Present a brief plan before changes (purpose → impact scope → steps). Propose task division if it's getting large.
2. **Small diffs.** Minimal changes, incremental PRs. Avoid interface breaking unless justified by requirements.
3. **Keep sources of truth.** ADRs are **top priority**. When you find conflicts between ADRs and design/README, **prioritize ADRs** and simultaneously create todos for document updates if needed.
4. **Test & types & lint.** Always pass type/lint/tests when making changes (commands below).
5. **Docs & examples.** Changes affecting visualization templates or error specifications must include `docs/` updates and sample/warning text reviews in the **same PR**.
6. **MCP contract compliance.** Follow `tools/list` / `tools/call` input/output schemas and error return methods (`isError=true`, etc.).
7. **Ask precisely.** Only ask **specific** questions narrowed to one point when unclear (after referencing materials).

## 3) Daily Commands (Use These Exact Invocations)

> Prefer uv & tox as the single entrypoints.

- **Setup**
    ```bash
    uv sync --all-extras
    uv run pre-commit install
    ```

- **All checks (lint, mypy, pytest)**
    ```bash
    uv run tox
    ```

- **Unit tests (matrix via CI; local default py311)**
    ```bash
    uv run tox -e py311
    ```

- **Lint / Type / Coverage**
    ```bash
    uv run tox -e lint
    uv run tox -e type
    uv run tox -e coverage
    ```

- **Run pytest directly**
    ```bash
    uv run pytest
    ```

> CI mirrors these via .github/workflows/ci.yml. Fix locally failing items before PR.

## 4) Code Style & Quality

- **Ruff:** Rules reference `tool.ruff` (mostly ALL, selective ignore). Auto-fix via `uv run tox -e lint` / pre-commit.
- **MyPy:** `strict=true`. Add types, avoid ambiguous `Any`. `plugins=pydantic.mypy` is enabled.
- **Tests:** pytest with coverage (branch). Add UT for new modules + IT/ST as needed.
- **Commits/PRs:** Conventional Commits (e.g., `feat: ...`). Include **operation verification**, **compatibility**, and links (related docs/Issues) in PR descriptions.

## 5) Architecture Quick Map (For Navigation)

- **Layers:** Interface(MCP) / Orchestration / Processing(DataValidator, PatternSelector, ChartSelector, DataProcessor, DataMapper) / Core(ChartBuilder) / Infra(LLMClient) — Details in `docs/design.md §5-6`.
- **Primary tool:** `chartelier_visualize` (schema/errors in `docs/mcp-integration.md`).
- **Templates:** Altair-based **pre-validated** templates only. Auxiliary elements follow template-side allowlist (max 3 elements).

## 6) What to Do / Not Do (Checklist)

**Do**
- Build pre-processing pipelines using only existing safe functions (Design §6.3).
- Select templates within 9 patterns and perform **type-safe mapping** (return structured errors on failure).
- Use **equidistant sampling** when exceeding cell limits, leave notifications in `metadata.warnings`.
- Return **structured errors** (code/hint/correlation ID) on failure, follow policies for degradation and retry.

**Don't**
- Introduce or use pandas (**prohibited**).
- Generate dual-axis/3D/radar/donut charts.
- Use unregistered pre-processing operations, arbitrary code, or dynamic template generation.

## 7) Typical Tasks (How to Approach)

- **Add/modify a chart template:** Read existing templates → identify requirement differences → add to `ChartBuilder` → update allowed auxiliary elements → UT/ST → verify compliance with relevant rules in `docs/visualization-policy.md` → regression test sample images (if needed).
- **Tweak error messages:** Match minimal form in `docs/mcp-integration.md §4`, include hints with correctable actions (column candidates, type casting, etc.).
- **Performance regression:** Check §10.1 budget, record phase times in metadata, identify hotspots, first adjust I/O/pre-processing vectorization and thread settings.

## 8) Safety & Permissions

- Do not touch `.env`, `secrets/**`, or build artifacts. Ask for human approval if needed.
- **Explicitly** request/record external communications and additional tools, avoid creating unnecessary persistent dependencies for the project.
- Image output defaults to `png` (`svg` when needed). Follow design specifications for fonts/locales.

## 9) Definition of Done (Per PR)

- ✅ `uv run tox` succeeds locally (lint/type/tests/coverage).
- ✅ **Consistent** with specs/design/ADRs. Include document updates if there are differences.
- ✅ Error messages include **correction hints** (when applicable).
- ✅ Compliant with visualization policy (axes, colors, accessibility).
- ✅ Tests added/updated proportional to change scope.

## 10) If You Get Stuck

- First re-read `docs/` and ADRs. If intent is unclear, ask **one short, specific** question (attach related files with `@`).
- If you find conflicts in design or policy, present small **proposed patches** (code + docs/tests).
