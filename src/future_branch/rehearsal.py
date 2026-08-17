"""Git operations and rehearsal merge simulation inside disposable clones."""

from __future__ import annotations

import contextlib
import gc
import tempfile
from pathlib import Path

from git import GitCommandError, Repo

from future_branch.analyzer import ConflictResult


def rehearse_merges(repo_path: Path, base: str, branches: list[str]) -> list[ConflictResult]:
    """Merge branches in order inside a disposable clone and return conflicts."""
    source = Repo(str(repo_path))
    base_sha = source.commit(base).hexsha
    branch_shas = {branch: source.commit(branch).hexsha for branch in branches}
    source.close()
    with tempfile.TemporaryDirectory(prefix="future-branch-", ignore_cleanup_errors=True) as temporary:
        clone_path = Path(temporary) / "repo"
        clone = Repo.clone_from(str(repo_path), str(clone_path), no_single_branch=True)
        future = clone.create_head("future-main", base_sha)
        for branch in branches:
            if branch not in clone.heads:
                clone.create_head(branch, branch_shas[branch])
        clone.head.reference = future
        clone.head.reset(index=True, working_tree=True)
        conflicts: list[ConflictResult] = []
        try:
            for branch in branches:
                try:
                    clone.git.merge(branch, "--no-edit", "--no-ff")
                except GitCommandError as exc:
                    output = f"{exc.stdout or ''}\n{exc.stderr or ''}"
                    paths = sorted(
                        {line.split(":", 1)[-1].strip() for line in output.splitlines() if line.startswith("CONFLICT")}
                    )
                    if not paths:
                        paths = ["(merge state)"]
                    for path in paths:
                        conflicts.append(
                            ConflictResult(
                                path,
                                list(dict.fromkeys([*branches, branch])),
                                "Git could not merge overlapping changes.",
                                "Resolve the merge markers between the named branches, then rerun the rehearsal.",
                                kind="merge",
                                severity="error",
                                owner_changed=branch,
                                owner_consumer=branches[0],
                                evidence=[output.strip()],
                            )
                        )
                    with contextlib.suppress(GitCommandError):
                        clone.git.merge(abort=True)
                    break
            return conflicts
        finally:
            clone.git.clear_cache()
            clone.close()
            future = None
            del clone
            gc.collect()
