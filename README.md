# Future Branch

<p align="center">
  <a href="https://github.com/Paramount50/Future-branch/actions/workflows/ci.yml"><img src="https://github.com/Paramount50/Future-branch/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue" alt="Python 3.10-3.13"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

> **Individually correct. Collectively broken.** Future Branch catches it before merge.

**Future Branch** is a deterministic, offline pre-merge rehearsal gate for parallel coding branches. It constructs an immutable candidate with native Git object-tree operations and performs multi-language static contract analysis to catch schema mismatches that Git textual merges cannot see — before anything reaches `main`.

---

## The Problem

When multiple coding agents or developers work on separate branches simultaneously:
1. **Branch A (Backend)** renames a response field: `credits` &rarr; `creditsbalance`.
2. **Branch B (Frontend)** reads `profile.credits` from the API response.
3. Both branches pass their respective local tests.
4. Git executes a clean merge without any textual conflicts.
5. **Production breaks silently at runtime.**

Future Branch rehearses the merge ahead of time and surfaces cross-branch contract incompatibilities deterministically.

---

## Features

- 🛡️ **Immutable Git Rehearsal:** Builds the exact sequential candidate with `git merge-tree` without touching your working tree, index, or source branches.
- 🧭 **Pairwise Attribution:** Emits a bounded branch-pair merge matrix alongside the authoritative ordered candidate.
- 🔍 **Static Contract Analysis:** Uses Python AST traversal and JS/TS pattern matching to detect function signature drifts, removed schema fields, and broken route endpoints.
- 🧾 **Versioned Contract Evidence:** Emits a language-neutral contract inventory with endpoint identity, requiredness, nullability, source locations, extractor confidence, and snapshot provenance.
- 🔁 **Bidirectional Endpoint Checks:** Detects stale callers after endpoint deletion, HTTP method changes, required-parameter additions, response-field removal, and incompatible response-shape mutations with stable machine-readable conflict codes.
- 📊 **Self-Contained Dark HTML Report:** Generates an incident report with side-by-side contract diffs, evidence traces, and actionable interventions.
- ⚡ **Zero External Heavy Dependencies:** Pure Python + Git operations. No LLM APIs, no build pipelines, no runtime execution of untrusted code.
- 🚦 **CI/CD Ready:** Returns exit code `0` on clean rehearsals and `1` on conflicts for seamless integration into CI gates.

---

## Installation

Future Branch requires **Python 3.10+** and **Git**.

```bash
# Clone the repository
git clone https://github.com/Paramount50/Future-branch.git
cd Future-branch

# Install in editable mode
pip install -e .

# Or install with development dependencies (pytest, ruff, pre-commit)
pip install -e .[dev]
```

---

## Usage

```bash
future-branch <path-to-repo> <branch-1> <branch-2> [branch-3 ...] [options]
```

### Options

| Flag | Default | Description |
|:---|:---|:---|
| `<repo>` | *(required)* | Path to the local Git repository |
| `<branches...>` | *(required)* | Two or more branch names to merge sequentially |
| `--base` | `main` | Base branch to rehearse against |
| `--report` | `incident_report.html` | Path where the HTML incident report will be generated |
| `--format` | `console` | Standard output format: `console`, machine-readable `json`, or SARIF 2.1.0 `sarif` |
| `--output` | stdout | Write JSON or SARIF to a file; relative paths resolve inside the analyzed repository |

### Example

```bash
future-branch ./my-repo agent-backend-refactor agent-frontend-widget --base main --report reports/incident.html
```

For a CI artifact suitable for code-scanning upload:

```bash
future-branch ./my-repo agent-backend-refactor agent-frontend-widget \
  --base main --format sarif --output reports/future-branch.sarif
```

---

## Interactive Demo

To test Future Branch against a simulated cross-branch contract mismatch:

```bash
# On Linux / macOS
bash setup_demo.sh

# On Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\setup_demo.ps1
```

The script initializes a temporary repository demonstrating:
- `main`: Baseline API returning `credits`.
- `agent-a-backend`: Renames `credits` &rarr; `creditsbalance`.
- `agent-b-frontend`: Displays `profile.credits`.

Run the generated command:
```bash
future-branch "<temp-repo-path>" agent-a-backend agent-b-frontend
```

Future Branch will catch the silent break, return exit code `1`, and output `incident_report.html`.

---

## Package Architecture

```
Future-branch/
├── .github/
│   ├── ISSUE_TEMPLATE/     # Bug and feature request templates
│   ├── workflows/ci.yml    # Multi-Python GitHub Actions CI
│   └── pull_request_template.md
├── docs/
│   └── architecture.md     # In-depth system design & extension guide
├── src/
│   └── future_branch/
│       ├── __init__.py     # Package metadata
│       ├── __main__.py     # python -m future_branch support
│       ├── analyzer.py     # Python AST & JS/TS contract extraction
│       ├── contracts.py    # Versioned universal contract records and bounded extractors
│       ├── cli.py          # Command-line entry point
│       ├── rehearsal.py    # Git sandbox & merge simulation
│       └── reporter.py     # HTML report rendering engine
├── tests/                  # Pytest test suite with shared Git fixtures
├── pyproject.toml          # PEP 621 packaging & Ruff/pytest configuration
└── rehearse.py             # Backward-compatible CLI shim
```

For complete technical details, see the [Architecture Documentation](docs/architecture.md).

---

## Known Limitations

Future Branch is focused on fast, offline static analysis:
- **JS/TS Parsing:** Currently uses regex tokenization for property access and fetch endpoints rather than a full TypeScript compiler AST.
- **Python Schemas:** Extracts annotated class/Pydantic fields, aliases, inheritance, return annotations, FastAPI `response_model`, and local `APIRouter`/`include_router` prefixes; validators, computed fields, generics, imported-router composition, and ORM models remain unsupported.
- **Dynamic Attributes:** Dynamic runtime evaluation (e.g. `getattr()`, `eval()`, runtime dictionary unpacking) cannot be statically inferred.
- **Conflicted Candidates:** Rehearsal records the first textual conflict and reports semantic coverage as incomplete rather than inventing an `ours` or `theirs` resolution.
- **Candidate Coverage:** Python syntax failures and unavailable candidate snapshots return an explicit `incomplete` status; exit code `1` prevents an unverified candidate from being reported clean.
- **Linkage Coverage:** Consumers without a resolved endpoint and files with multiple fetch calls are preserved as partial evidence and make the rehearsal `incomplete` when Python contracts changed.
- **Parameterized Routes:** FastAPI-style `{parameter}` paths match concrete and JavaScript template-literal caller segments; query strings are normalized separately.
- **Pairwise Scale:** Pairwise diagnostics are capped at 500 checks. Larger branch sets still build the ordered candidate but return `incomplete` because the matrix was skipped.

---

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting pull requests.

### Development Workflow

```bash
# Run tests
pytest

# Check linting and formatting
ruff check .
ruff format --check .
```

---

## License

This project is licensed under the [MIT License](LICENSE).
