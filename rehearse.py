"""Backward-compatible entry point. Prefer running `future-branch` CLI."""

from future_branch.cli import main

# Expose rehearse_merges for direct module imports if needed
from future_branch.rehearsal import rehearse_merges  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
