from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from future_branch.rehearsal import MAX_PAIRWISE_CHECKS, rehearse_merges


def test_merge_conflict_detected(merge_conflict_repo: Path):
    rehearsal = rehearse_merges(merge_conflict_repo, "main", ["branch-a", "branch-b"])
    assert len(rehearsal) > 0
    assert any(c.kind == "merge" for c in rehearsal)
    assert any("file.txt" in c.path for c in rehearsal)
    assert rehearsal.candidate_ref is None
    assert rehearsal.incomplete_reasons


def test_clean_sequential_merge(clean_repo: Path):
    rehearsal = rehearse_merges(clean_repo, "main", ["feature-a", "feature-b"])
    assert len(rehearsal) == 0
    assert rehearsal.candidate_ref
    assert rehearsal.candidate_tree
    assert [check.status for check in rehearsal.pairwise_checks] == ["clean"]


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


def test_pairwise_matrix_attributes_conflict(merge_conflict_repo: Path):
    rehearsal = rehearse_merges(merge_conflict_repo, "main", ["branch-a", "branch-b"])

    assert len(rehearsal.pairwise_checks) == 1
    check = rehearsal.pairwise_checks[0]
    assert (check.left, check.right) == ("branch-a", "branch-b")
    assert check.status == "conflict"
    assert "file.txt" in check.conflict_paths


def test_pairwise_limit_does_not_block_ordered_candidate(clean_repo: Path):
    rehearsal = rehearse_merges(clean_repo, "main", ["feature-a", "feature-b"], max_pairwise_checks=0)

    assert MAX_PAIRWISE_CHECKS > 0
    assert rehearsal.pairwise_checks == []
    assert rehearsal.candidate_ref
    assert any("pairwise checks" in reason for reason in rehearsal.incomplete_reasons)


def test_negative_pairwise_limit_is_rejected(clean_repo: Path):
    with pytest.raises(ValueError, match="zero or greater"):
        rehearse_merges(clean_repo, "main", ["feature-a", "feature-b"], max_pairwise_checks=-1)
