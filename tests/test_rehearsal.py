from __future__ import annotations

from pathlib import Path

from git import Repo

from rehearse import rehearse_merges


def test_merge_conflict_detected(merge_conflict_repo: Path):
    conflicts = rehearse_merges(merge_conflict_repo, "main", ["branch-a", "branch-b"])
    assert len(conflicts) > 0
    assert any(c.kind == "merge" for c in conflicts)
    assert any("file.txt" in c.path for c in conflicts)


def test_clean_sequential_merge(clean_repo: Path):
    conflicts = rehearse_merges(clean_repo, "main", ["feature-a", "feature-b"])
    assert len(conflicts) == 0


def test_source_repo_untouched(demo_repo: Path):
    source = Repo(str(demo_repo))
    initial_branches = [h.name for h in source.heads]
    initial_head_sha = source.head.commit.hexsha
    source.close()

    # Run rehearsal
    rehearse_merges(demo_repo, "main", ["agent-a-backend", "agent-b-frontend"])

    source_after = Repo(str(demo_repo))
    branches_after = [h.name for h in source_after.heads]
    head_sha_after = source_after.head.commit.hexsha
    source_after.close()

    assert initial_branches == branches_after
    assert "future-main" not in branches_after
    assert initial_head_sha == head_sha_after
