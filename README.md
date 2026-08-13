# Future Branch

> Individually correct. **Collectively broken.** Future Branch catches it before merge.

Future Branch is a pre-merge rehearsal gate for parallel coding-agent branches. It merges branches in an isolated, disposable clone and runs offline static analysis to catch contract mismatches that Git cannot see — before anything touches your real `main` branch.

Two agents. One renames a field. The other reads it. Both changes compile. The application breaks silently when they merge. Future Branch prevents this.

## What it does

- **Clones** the repository into a temporary environment.
- **Merges** each agent branch sequentially into a disposable `future-main`.
- **Detects** Git merge conflicts and semantic contract mismatches across Python and JavaScript/TypeScript.
- **Generates** a self-contained HTML incident report with root cause analysis, evidence trace, and a recommended intervention.
- **Returns** exit code `0` (clean) or `1` (conflicts found) for scripting and CI integration.

No LLM. No build pipeline. No network dependency. Pure Git operations and static analysis.

## Install and run

Python 3.10+ and Git are required.

```bash
python -m pip install -r requirements.txt
python rehearse.py /path/to/repo branch-a branch-b [branch-c ...]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--base` | `main` | Base branch to rehearse against |
| `--report` | `incident_report.html` | Output path for the HTML report |

The first positional argument is the repository path, followed by two or more branch names. The temporary `future-main` is created and removed inside a disposable clone, so the source checkout is left untouched.

## Demo

Run the included demo to see Future Branch in action:

```bash
# Linux / macOS
bash setup_demo.sh

# Windows
powershell -ExecutionPolicy Bypass -File .\setup_demo.ps1
```

The script creates a temporary repository with three branches:

| Branch | What it does |
|--------|-------------|
| `main` | Base with a `credits` field in the backend API |
| `agent-a-backend` | Renames `credits` → `creditsbalance` |
| `agent-b-frontend` | Reads `profile.credits` from the API response |

Then run the generated rehearsal command:

```bash
python rehearse.py "<temp-repo-path>" agent-a-backend agent-b-frontend
```

Future Branch detects that the backend removed the `credits` field while the frontend still depends on it, and generates an incident report with the exact root cause and suggested fix.

## Architecture

| File | Role |
|------|------|
| `rehearse.py` | CLI entry point — clones, merges, orchestrates analysis |
| `analyzer.py` | Static contract extraction using Python `ast` and regex for JS/TS |
| `reporter.py` | Generates a self-contained dark-themed HTML incident report |

The analyzer extracts:
- Python: function signatures, class fields, response keys, FastAPI routes
- JS/TS: exports, imports, fetch calls, consumed response properties

Cross-language contract mismatches (e.g., a Python backend field rename breaking a JS frontend consumer) are detected by comparing the base branch contracts against each agent branch.

## Built with Agent Orchestrator

Future Branch was built during **The Orchestra**, AO's first hackathon (August 12–13, 2026).

The entire project — planning, implementation, styling, and testing — was done using [Agent Orchestrator](https://aoagents.dev/) as the development workspace. AO agents helped write the static analysis engine, design the incident report, and verify the end-to-end demo flow.

Future Branch is currently **CLI-first**. CI integration is the next step, because the tool needs to discover multiple active agent branches — not just react to a single pull request.

## AO integration

AO can provide the active agent branches and notify owners after a rehearsal:

```bash
ao session ls
ao send --session <session-id> --message "Future Branch found a contract conflict in ..."
```

Use the branch names reported by the AO session when invoking the CLI, then send the report path and suggested intervention back to the responsible agent.
