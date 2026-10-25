"""Non-mutating Git merge rehearsal using native object-tree plumbing."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from git import Repo

from future_branch.analyzer import ConflictResult


@dataclass
class RehearsalResult:
    """The conflicts and immutable candidate produced by a rehearsal."""

    conflicts: list[ConflictResult] = field(default_factory=list)
    candidate_ref: str | None = None
    candidate_tree: str | None = None
    incomplete_reasons: list[str] = field(default_factory=list)

    # Preserve the list-like interface used by the original public helper.
    def __iter__(self) -> Iterator[ConflictResult]:
        return iter(self.conflicts)

    def __len__(self) -> int:
        return len(self.conflicts)


def _git(repo_path: Path, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_NAME": "Future Branch",
            "GIT_AUTHOR_EMAIL": "future-branch@localhost",
            "GIT_COMMITTER_NAME": "Future Branch",
            "GIT_COMMITTER_EMAIL": "future-branch@localhost",
        }
    )
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env=environment,
    )


def _conflict_paths(output: str) -> list[str]:
    """Extract the name-only section emitted before merge-tree messages."""
    lines = output.splitlines()[1:]
    paths: list[str] = []
    for line in lines:
        if not line.strip():
            break
        paths.append(line.strip())
    return paths or ["(merge state)"]


def rehearse_merges(repo_path: Path, base: str, branches: list[str]) -> RehearsalResult:
    """Build the requested candidate without changing refs, the index, or a worktree."""
    repo_path = Path(repo_path).resolve()
    source = Repo(str(repo_path))
    try:
        current_ref = source.commit(base).hexsha
        branch_refs = [(branch, source.commit(branch).hexsha) for branch in branches]
    finally:
        source.close()

    result = RehearsalResult(candidate_ref=current_ref, candidate_tree=current_ref)
    integrated: list[str] = []
    for branch, branch_ref in branch_refs:
        merge = _git(repo_path, "merge-tree", "--write-tree", "--name-only", "--messages", current_ref, branch_ref)
        output = merge.stdout or merge.stderr
        if merge.returncode == 1:
            owners = [*integrated, branch]
            for path in _conflict_paths(output):
                result.conflicts.append(
                    ConflictResult(
                        path=path,
                        branches=owners,
                        description="Git could not merge overlapping changes.",
                        suggested_fix="Resolve the merge conflict, then rerun the rehearsal.",
                        kind="merge",
                        severity="error",
                        owner_changed=branch,
                        owner_consumer=integrated[-1] if integrated else base,
                        evidence=[output.strip()],
                    )
                )
            result.candidate_ref = None
            result.candidate_tree = None
            result.incomplete_reasons.append(
                f"No unambiguous combined snapshot exists after merging {branch!r}; semantic checks that depend on it were skipped."
            )
            break
        if merge.returncode != 0:
            detail = output.strip() or f"git merge-tree exited with status {merge.returncode}"
            result.candidate_ref = None
            result.candidate_tree = None
            result.incomplete_reasons.append(detail)
            break

        tree_oid = merge.stdout.splitlines()[0].strip()
        commit = _git(
            repo_path,
            "commit-tree",
            tree_oid,
            "-p",
            current_ref,
            "-p",
            branch_ref,
            input_text=f"Future Branch candidate including {branch}\n",
        )
        if commit.returncode != 0:
            result.candidate_ref = None
            result.candidate_tree = None
            result.incomplete_reasons.append(commit.stderr.strip() or "Could not materialize the candidate commit.")
            break
        current_ref = commit.stdout.strip()
        result.candidate_ref = current_ref
        result.candidate_tree = tree_oid
        integrated.append(branch)

    return result
