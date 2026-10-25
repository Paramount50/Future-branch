from __future__ import annotations

from pathlib import Path

from future_branch.reporter import render_report, write_report


def test_clean_report_contains_passed():
    result = {
        "status": "clean",
        "base": "main",
        "branches": ["branch-a", "branch-b"],
        "conflicts": [],
    }
    html = render_report(result)
    assert "REHEARSAL CLEAN" in html
    assert "Rehearsal passed" in html
    assert "branch-a" in html
    assert "branch-b" in html


def test_conflict_report_contains_incident():
    result = {
        "status": "conflicts",
        "base": "main",
        "branches": ["branch-a", "branch-b"],
        "conflicts": [
            {
                "path": "frontend/api.js",
                "branches": ["branch-a", "branch-b"],
                "description": "Backend contract removed 'credits', but the frontend still reads response.credits.",
                "suggested_fix": "Update frontend to consume renamed field.",
                "kind": "semantic",
                "severity": "error",
                "changed_code": "credits -> creditsbalance",
                "expected_code": "response.credits",
                "owner_changed": "branch-a",
                "owner_consumer": "branch-b",
                "evidence": ["backend/app.py: fields changed", "frontend/api.js: response.credits"],
            }
        ],
    }
    html = render_report(result)
    assert "CONFLICT DETECTED" in html
    assert "frontend/api.js" in html
    assert "credits" in html
    assert "Evidence Trace" in html
    assert "branch-a" in html
    assert "branch-b" in html


def test_html_escaping():
    result = {
        "status": "conflicts",
        "base": "main<script>",
        "branches": ["<script>alert(1)</script>", "branch-b"],
        "conflicts": [
            {
                "path": "<img src=x onerror=alert(1)>",
                "branches": ["<script>alert(1)</script>", "branch-b"],
                "description": "XSS test & check",
                "suggested_fix": "Fix & sanitize",
                "kind": "semantic",
                "severity": "error",
                "changed_code": "<b>test</b>",
                "expected_code": "<i>test</i>",
                "owner_changed": "<script>",
                "owner_consumer": "branch-b",
                "evidence": ["<evidence>"],
            }
        ],
    }
    html = render_report(result)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_write_report_creates_file(tmp_path: Path):
    output_path = tmp_path / "reports" / "incident.html"
    result = {
        "status": "clean",
        "base": "main",
        "branches": ["b1", "b2"],
        "conflicts": [],
    }
    returned_path = write_report(result, output_path)
    assert returned_path.exists()
    assert "REHEARSAL CLEAN" in returned_path.read_text(encoding="utf-8")


def test_incomplete_report_does_not_claim_clean():
    result = {
        "status": "incomplete",
        "base": "main",
        "branches": ["branch-a", "branch-b"],
        "conflicts": [],
        "incomplete_reasons": ["Could not parse candidate Python source at broken.py."],
    }

    rendered = render_report(result)

    assert "ANALYSIS INCOMPLETE" in rendered
    assert "broken.py" in rendered
    assert "REHEARSAL CLEAN" not in rendered
