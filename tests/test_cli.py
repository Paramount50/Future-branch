from __future__ import annotations

import json
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


def test_cli_json_contains_candidate_snapshot(clean_repo: Path, tmp_path: Path, capsys):
    report_file = tmp_path / "report.html"

    code = main(
        [
            str(clean_repo),
            "feature-a",
            "feature-b",
            "--report",
            str(report_file),
            "--format",
            "json",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result["status"] == "clean"
    assert result["candidate_ref"]
    assert result["candidate_tree"]
    assert result["pairwise_checks"] == [
        {
            "conflict_paths": [],
            "detail": None,
            "left": "feature-a",
            "right": "feature-b",
            "status": "clean",
        }
    ]


def test_cli_sarif_contains_clean_run(clean_repo: Path, tmp_path: Path, capsys):
    report_file = tmp_path / "report.html"

    code = main(
        [
            str(clean_repo),
            "feature-a",
            "feature-b",
            "--report",
            str(report_file),
            "--format",
            "sarif",
        ]
    )
    sarif = json.loads(capsys.readouterr().out)

    assert code == 0
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"] == []
    assert sarif["runs"][0]["properties"]["status"] == "clean"


def test_cli_writes_sarif_artifact(clean_repo: Path, tmp_path: Path, capsys):
    report_file = tmp_path / "report.html"
    output_file = tmp_path / "artifacts" / "future-branch.sarif"

    code = main(
        [
            str(clean_repo),
            "feature-a",
            "feature-b",
            "--report",
            str(report_file),
            "--format",
            "sarif",
            "--output",
            str(output_file),
        ]
    )

    assert code == 0
    assert capsys.readouterr().out == ""
    assert json.loads(output_file.read_text(encoding="utf-8"))["version"] == "2.1.0"


def test_cli_rejects_output_with_console_format(clean_repo: Path):
    with pytest.raises(SystemExit) as exc_info:
        main([str(clean_repo), "feature-a", "feature-b", "--output", "result.json"])

    assert exc_info.value.code != 0


def test_cli_rejects_negative_pairwise_limit(clean_repo: Path):
    with pytest.raises(SystemExit) as exc_info:
        main([str(clean_repo), "feature-a", "feature-b", "--max-pairwise-checks", "-1"])

    assert exc_info.value.code != 0
