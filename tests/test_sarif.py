from __future__ import annotations

from future_branch.sarif import to_sarif


def test_sarif_serializes_conflict_code_location_and_metadata():
    analysis = {
        "status": "conflicts",
        "base": "main",
        "branches": ["backend", "frontend"],
        "candidate_ref": "abc123",
        "candidate_tree": "def456",
        "incomplete_reasons": [],
        "conflicts": [
            {
                "code": "ERR_FIELD_REMOVED",
                "severity": "error",
                "path": "web/client.ts",
                "branches": ["backend", "frontend"],
                "description": "Response field was removed.",
                "suggested_fix": "Update the consumer.",
                "owner_changed": "backend",
                "owner_consumer": "frontend",
                "evidence": ["web/client.ts:42: consumes credits"],
            }
        ],
    }

    sarif = to_sarif(analysis)

    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "Future Branch"
    assert run["tool"]["driver"]["rules"][0]["id"] == "ERR_FIELD_REMOVED"
    finding = run["results"][0]
    assert finding["ruleId"] == "ERR_FIELD_REMOVED"
    assert finding["locations"][0]["physicalLocation"]["region"]["startLine"] == 42
    assert run["properties"]["candidateRef"] == "abc123"


def test_sarif_emits_incomplete_coverage_as_warning():
    sarif = to_sarif(
        {
            "status": "incomplete",
            "base": "main",
            "branches": ["a", "b"],
            "conflicts": [],
            "incomplete_reasons": ["Dynamic request body could not be enumerated."],
        }
    )

    finding = sarif["runs"][0]["results"][0]
    assert finding["ruleId"] == "FB_INCOMPLETE"
    assert finding["level"] == "warning"
