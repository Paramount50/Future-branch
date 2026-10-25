# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Build immutable sequential candidates with `git merge-tree` and analyze the resulting snapshot rather than independent branch tips.
- Return candidate commit/tree identifiers and explicit incomplete-analysis reasons.
- Add machine-readable JSON output with `--format json`.
- Limit Python response fields to returned dictionaries and class fields instead of every string literal.
- Check unchanged JavaScript/TypeScript consumers and basic destructuring against changed Python contracts.
- Use known endpoint paths to avoid matching identical field names across unrelated routes.

### Fixed
- Coordinated producer/consumer changes no longer report stale branch-tip conflicts.
- Deleted providers, unchanged consumers, and Python parse failures can no longer be silently reported clean.

## [0.1.0] - 2026-08-17

### Added
- Pre-merge rehearsal gate for parallel coding branches.
- Disposable Git clone environment simulating sequential merges.
- Python AST contract extractor (functions, dataclass/class fields, FastAPI routes).
- JavaScript/TypeScript property consumption and fetch call contract extractor.
- Pure CSS dark-themed self-contained HTML incident report generator.
- ANSI color-coded CLI interface with exit codes (0 for clean, 1 for conflict).
- Complete test suite for analyzer, rehearsal engine, report generation, and CLI.
- GitHub Actions multi-Python CI pipeline (Python 3.10, 3.11, 3.12, 3.13).
- Contributor documentation, Code of Conduct, and GitHub issue/PR templates.
