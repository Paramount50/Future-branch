from __future__ import annotations

from pathlib import Path

import pytest

from future_branch.cli import main


def test_cli_exit_0_on_clean(clean_repo: Path, tmp_path: Path):
    report_file = tmp_path / "report.html"
    code = main([str(clean_repo), "feature-a", "feature-b", "--report", str(report_file)])
    assert code == 0
    assert report_file.exists()


def test_cli_exit_1_on_conflict(demo_repo: Path, tmp_path: Path):
    report_file = tmp_path / "report.html"
    code = main([str(demo_repo), "agent-a-backend", "agent-b-frontend", "--report", str(report_file)])
    assert code == 1
    assert report_file.exists()


def test_cli_fewer_than_two_branches_errors(clean_repo: Path):
    with pytest.raises(SystemExit) as exc_info:
        main([str(clean_repo), "feature-a"])
    assert exc_info.value.code != 0
