"""SARIF 2.1.0 serialization for Future Branch analysis results."""

from __future__ import annotations

import re
from typing import Any

from future_branch import __version__


def _line_from_evidence(path: str, evidence: list[str]) -> int | None:
    normalized = path.replace("\\", "/")
    for item in evidence:
        match = re.match(r"(.+?):(\d+):", item)
        if match and match.group(1).replace("\\", "/") == normalized:
            return int(match.group(2))
    return None


def _location(conflict: dict[str, Any]) -> dict[str, Any] | None:
    path = str(conflict.get("path", "")).strip()
    if not path or path == "(merge state)":
        return None
    physical: dict[str, Any] = {"artifactLocation": {"uri": path.replace("\\", "/")}}
    line = _line_from_evidence(path, list(conflict.get("evidence", [])))
    if line is not None:
        physical["region"] = {"startLine": line}
    return {"physicalLocation": physical}


def to_sarif(analysis: dict[str, Any]) -> dict[str, Any]:
    """Convert a structured analysis result into a SARIF 2.1.0 log."""
    findings: list[dict[str, Any]] = []
    rule_ids: set[str] = set()
    for conflict in analysis.get("conflicts", []):
        rule_id = str(conflict.get("code") or "ERR_SEMANTIC")
        rule_ids.add(rule_id)
        finding: dict[str, Any] = {
            "ruleId": rule_id,
            "level": "error" if conflict.get("severity", "error") == "error" else "warning",
            "message": {"text": str(conflict.get("description", "Future Branch conflict"))},
            "properties": {
                "branches": list(conflict.get("branches", [])),
                "suggestedFix": str(conflict.get("suggested_fix", "")),
                "ownerChanged": str(conflict.get("owner_changed", "")),
                "ownerConsumer": str(conflict.get("owner_consumer", "")),
                "evidence": list(conflict.get("evidence", [])),
            },
        }
        if location := _location(conflict):
            finding["locations"] = [location]
        findings.append(finding)

    incomplete = list(analysis.get("incomplete_reasons", []))
    if incomplete:
        rule_ids.add("FB_INCOMPLETE")
        findings.extend(
            {
                "ruleId": "FB_INCOMPLETE",
                "level": "warning",
                "message": {"text": str(reason)},
            }
            for reason in incomplete
        )
    if analysis.get("status") == "error":
        rule_ids.add("FB_ERROR")
        findings.append(
            {
                "ruleId": "FB_ERROR",
                "level": "error",
                "message": {"text": str(analysis.get("error", "Future Branch analysis failed"))},
            }
        )

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Future Branch",
                        "semanticVersion": __version__,
                        "informationUri": "https://github.com/Paramount50/Future-branch",
                        "rules": [
                            {"id": rule_id, "shortDescription": {"text": rule_id.replace("_", " ").title()}}
                            for rule_id in sorted(rule_ids)
                        ],
                    }
                },
                "results": findings,
                "properties": {
                    "status": analysis.get("status", "error"),
                    "base": analysis.get("base"),
                    "branches": list(analysis.get("branches", [])),
                    "candidateRef": analysis.get("candidate_ref"),
                    "candidateTree": analysis.get("candidate_tree"),
                },
            }
        ],
    }
