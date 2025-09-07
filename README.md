# chartelier

> [!WARNING]
> This project is in a **pre-release experimental phase**.
> The library is not intended for production use, and contributions are not being accepted at this stage.
> Following the completion of MVP validation, we plan to release it officially on PyPI and provide announcements for users and contributors.


## Why chartelier?

Most visualizations unintentionally mislead—often without anyone noticing. Good tools exist, but only reach those who already value accuracy.

Now, AI agents generate visualizations at scale, but they do so blindly. LLMs can't "see" what they create, resulting in subtle but significant errors.

`chartelier` doesn't make LLMs do more—it makes them do less. We restrict their role to what they're best at, constraining choices to a finite, validated space. No arbitrary code, no guesswork, just clarity.

Users get reliable visualizations by default, without even thinking about it. The way it always should have been.

## Development Setup

### Prerequisites

- Python 3.11+
- uv (for package management)

### Initial Setup

1. Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies:
```bash
uv sync --all-extras
```

3. Install pre-commit hooks:
```bash
uv run pre-commit install
```

### Development Workflow

#### Running Tests
```bash
# Run all tests with coverage
uv run tox -e coverage

# Run tests for specific Python version
uv run tox -e py311

# Run tests directly with pytest
uv run pytest
```

#### Code Quality Checks
```bash
# Run all checks (ruff, mypy, pytest)
uv run tox

# Run individual checks
uv run tox -e lint    # Ruff linting
uv run tox -e type    # MyPy type checking
uv run tox -e format  # Auto-format code
```

#### Pre-commit Hooks
Pre-commit hooks run automatically on `git commit`. To run manually:
```bash
uv run pre-commit run --all-files
```

### Project Structure
```
chartelier/
├── src/
│   └── chartelier/          # Main package
├── tests/                   # Test files
├── docs/                    # Documentation
├── pyproject.toml           # Project configuration
├── tox.ini                  # Tox configuration (in pyproject.toml)
├── .pre-commit-config.yaml
└── .github/
    └── workflows/
        └── ci.yml           # GitHub Actions CI
```

### Configuration

- **Ruff**: All rules enabled with selective ignores (see pyproject.toml)
- **MyPy**: Strict mode enabled
- **Pytest**: Coverage reporting enabled
- **Tox**: Environments for py311/312/313, lint, type, coverage

### CI/CD

GitHub Actions runs on:
- Push to main/develop branches
- Pull requests
- Python 3.11, 3.12, 3.13 on Ubuntu

Tests include:
- Unit tests with coverage
- Ruff linting
- MyPy type checking
