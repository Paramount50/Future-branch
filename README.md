# Future Branch

Future Branch rehearses the integration of parallel coding-agent branches before they reach a shared base. It sequentially merges the branches in an isolated temporary `future-main`, captures real Git merge conflicts, and statically checks Python and JavaScript/TypeScript contracts for mismatches that Git cannot see.

> Individually correct. Collectively broken. Future Branch catches it before merge.

## Install and run

Python 3.10+ and Git are required. The analyzer is fully offline and does not require an LLM.

```bash
python -m pip install -r requirements.txt
python rehearse.py /path/to/repo agent-a agent-b agent-c
```

The first positional argument is the repository, followed by at least two branches. Use `--base develop` for a base other than `main`, or `--report path/to/report.html` to choose the incident report location. Exit code `0` means clean; exit code `1` means conflicts or an invalid rehearsal. The temporary `future-main` is created and removed inside a disposable clone, so the source checkout is left untouched.

## Demo scenario

Run one of these from the project root:

```bash
bash setup_demo.sh
powershell -ExecutionPolicy Bypass -File .\setup_demo.ps1
```

The script creates a fresh temporary repository with `main`, `agent-a-backend`, and `agent-b-frontend`. The backend branch renames `credits` to `creditsbalance`; the frontend branch consumes `response.credits`. Future Branch reports that the branches need a coordinated contract change.

## Architecture

`rehearse.py` uses GitPython to clone the repository temporarily, create `future-main`, and merge each branch in order. `analyzer.py` uses Python's `ast` module for functions, classes, fields, response keys, and FastAPI-style routes, plus regex-based export/import/fetch/property extraction for JS/TS. `reporter.py` writes one escaped HTML file with inline CSS and no external dependencies.

The optional `google-generativeai` dependency is reserved for future explanations; no analysis path depends on it.

## AO integration

AO can provide the active agent branches and notify owners after a rehearsal:

```bash
ao session ls
ao send --session <session-id> --message "Future Branch found a contract conflict in ..."
```

Use the branch names reported by the AO session when invoking the CLI, then send the report path and suggested intervention back to the responsible agent.
