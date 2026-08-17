# Contributing to Future Branch

Thank you for your interest in contributing to Future Branch! We are building a deterministic pre-merge rehearsal gate to catch cross-branch contract mismatches before they hit `main`.

Whether you are fixing a bug, adding a new language analyzer, improving documentation, or writing tests, your contributions are welcome.

---

## Quick Start (Development Setup)

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/<your-username>/Future-branch.git
   cd Future-branch
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate

   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install the package in editable mode with development dependencies**:
   ```bash
   pip install -e .[dev]
   ```

4. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

5. **Run the test suite**:
   ```bash
   pytest
   ```

---

## Development Workflow

### 1. Branch Naming
Create a feature branch with a descriptive prefix:
- `feat/add-pydantic-analyzer`
- `fix/js-destructuring-regex`
- `docs/add-plugin-guide`
- `test/rehearsal-edge-cases`

### 2. Code Quality & Formatting
We use **[Ruff](https://github.com/astral-sh/ruff)** for fast linting and formatting.

Before committing, ensure your code passes:
```bash
# Check and auto-fix lint issues
ruff check . --fix

# Format code
ruff format .

# Run the test suite
pytest
```

### 3. Commit Message Conventions
We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat: support pydantic BaseModel field extraction`
- `fix: correct regex for multiline JS imports`
- `docs: clarify CLI arguments in README`
- `test: add tests for FastAPI router endpoints`
- `chore: update CI matrix`

---

## Submitting a Pull Request (PR)

1. Push your branch to your fork:
   ```bash
   git push origin feat/your-feature-name
   ```
2. Open a Pull Request on GitHub against the `main` branch.
3. Fill out the PR template with:
   - A clear summary of the changes.
   - Any linked issues (e.g. `Fixes #12`).
   - Confirmation that all tests and lint checks pass.
4. Maintainers will review your PR promptly and provide feedback.

---

## Code of Conduct

Please note that this project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.
