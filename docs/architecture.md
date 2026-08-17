# Future Branch Architecture & Technical Design

Future Branch is a deterministic, offline pre-merge rehearsal gate designed for multi-branch development workflows — particularly where autonomous coding agents or human contributors work on parallel features that touch cross-module contracts.

---

## The Core Problem: Silent Contract Breaks

In traditional Git workflows, merges succeed cleanly whenever lines of code do not textually overlap in the exact same file region. However, in modern multi-tier applications:

```
[Agent A: Backend Branch]                    [Agent B: Frontend Branch]
Refactors user profile schema:               Builds billing widget:
  credits -> creditsbalance                     reads profile.credits
            │                                              │
            └───────────────┬──────────────────────────────┘
                            ▼
                   [Git Merge to main]
                  Textual Conflicts: 0
                  Build Status: Succeeded
                  Runtime Status: 💥 BROKEN (NaN / Undefined)
```

Both branches are **individually correct** in isolation, pass their own unit tests, and merge without conflict — yet the combined result is **collectively broken**.

---

## System Flow & Execution Pipeline

```mermaid
flowchart TD
    CLI["CLI Invocation<br><code>future-branch repo branch-a branch-b ...</code>"] --> Sandbox["1. Sandbox Isolation<br><code>tempfile.TemporaryDirectory</code>"]
    Sandbox --> Clone["2. Clone & Branch Setup<br><code>git.Repo.clone_from()</code>"]
    
    subgraph RehearsalPhase ["Rehearsal Engine (rehearsal.py)"]
        Clone --> VirtualHead["Create temporary <code>future-main</code>"]
        VirtualHead --> SeqMerge["Sequentially merge branch-a, branch-b..."]
        SeqMerge -->|Merge Conflict| TextualConflict["Capture Conflict Markers<br>kind: 'merge'"]
        SeqMerge -->|Clean Merge| CleanMerge["Proceed to Semantic Phase"]
    end
    
    subgraph AnalyzerPhase ["Static Analysis Engine (analyzer.py)"]
        CleanMerge --> ASTDiff["Extract contracts across commits"]
        ASTDiff --> PyExtractor["Python AST Extractor<br><code>ast.parse</code>: functions, dataclasses, routes, fields"]
        ASTDiff --> JSExtractor["JS/TS Extractor<br>Regex: exports, imports, fetch, property access"]
        PyExtractor --> CrossMatcher["Cross-Branch Contract Matcher"]
        JSExtractor --> CrossMatcher
        CrossMatcher --> SemanticConflict["Capture Breaking Changes<br>kind: 'semantic'"]
    end

    TextualConflict --> Aggregator["Result Aggregator"]
    SemanticConflict --> Aggregator
    
    subgraph OutputPhase ["Reporting & Feedback (reporter.py / cli.py)"]
        Aggregator --> HTMLReport["Self-Contained Dark HTML<br><code>incident_report.html</code>"]
        Aggregator --> Terminal["ANSI Color-Coded Terminal Summary"]
        Aggregator --> ExitCode["Exit Code: 0 (Clean) / 1 (Conflict)"]
    end
```

---

## Component Architecture

| Module | Role | Key Responsibilities |
|:---|:---|:---|
| `future_branch.cli` | User Entry Point | CLI parsing, path resolution, ANSI terminal formatting, exit code management. |
| `future_branch.rehearsal` | Git Sandbox Engine | Disposable clone lifecycle, sequential branch merging, merge conflict interception, handle cleanup. |
| `future_branch.analyzer` | Static Contract Analysis | Python AST traversal, JS/TS contract extraction, cross-branch schema & signature difference matching. |
| `future_branch.reporter` | Incident Visualizer | Standalone responsive dark-themed HTML report generation with evidence traces and suggested interventions. |

---

## Static Contract Extraction

### Python AST Parsing
The Python analyzer parses valid Python files into abstract syntax trees without executing code:
* **Functions (`ast.FunctionDef`, `ast.AsyncFunctionDef`)**: Reconstructs canonical signatures including positional args, keyword-only args, variadic `*args`/`**kwargs`, and return annotations.
* **Classes & Models (`ast.ClassDef`)**: Extracts type-annotated attributes (`ast.AnnAssign`) and standard assignments (`ast.Assign`).
* **Route Decorators (`@app.get`, `@app.post`, etc.)**: Extracts HTTP methods and endpoint paths.
* **Response Keys**: Scans return values and constant string literals for dictionary keys.

### JavaScript / TypeScript Pattern Extraction
The JS analyzer scans source files for contract touchpoints:
* **Exports & Imports**: Tracks exported functions, classes, and imported modules.
* **API Invocations**: Identifies `fetch()` URL endpoints.
* **Consumed Fields**: Scans accessed response properties (e.g. `response.<field>`, `data.<field>`, `profile.<field>`).

---

## Extensibility: Adding New Analyzers

Future Branch is designed to be easily extensible. To add a new language or framework analyzer:

1. **Define contract extraction**: Add a parser function in `analyzer.py` (e.g. `_go_contracts(source: str)` or `_rust_contracts(source: str)`).
2. **Register file extensions**: In `BranchAnalyzer.semantic_conflicts()`, map file extensions (e.g. `.go`, `.rs`, `.java`) to your contract extractor.
3. **Add diff rules**: Implement matching logic comparing base contracts against branch changes.
4. **Add unit tests**: Add test cases in `tests/test_analyzer.py` validating extraction and conflict detection.

---

## Known Limitations

Future Branch is intentionally focused and offline. The current analyzer has specific boundaries:

1. **JavaScript/TypeScript parsing**: Uses regex matching rather than a full TypeScript compiler/AST. Complex destructuring patterns (`const { a, b: c } = await res.json()`) or type definitions are not yet fully introspected.
2. **Python Schema Frameworks**: Introspects standard dataclasses and class attributes; explicit Pydantic v2 `BaseModel` field validators, `TypedDict`, and SQLAlchemy column definitions are planned enhancements.
3. **Sequential Merge Interruption**: Rehearsal stops on the first Git textual conflict; subsequent branches are not analyzed until merge markers are resolved.
4. **Dynamic Runtime Evaluation**: Contracts constructed entirely dynamically at runtime (e.g., dynamic `setattr` or dictionary unpacking) cannot be verified statically.
