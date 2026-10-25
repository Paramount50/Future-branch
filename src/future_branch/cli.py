"""Command-line interface for Future Branch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from future_branch.analyzer import analyze_repository
from future_branch.rehearsal import rehearse_merges
from future_branch.reporter import write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="future-branch",
        description="Rehearse parallel coding-agent branches before merge.",
    )
    parser.add_argument("repo", help="path to the Git repository")
    parser.add_argument("branches", nargs="+", help="two or more branch names, merged in this order")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument(
        "--report",
        default="incident_report.html",
        help="HTML report path (default: incident_report.html)",
    )
    parser.add_argument(
        "--format",
        choices=("console", "json"),
        default="console",
        help="stdout format (default: console)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if len(args.branches) < 2:
        build_parser().error("at least two branch names are required")
    repo_path = Path(args.repo).resolve()
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = repo_path / report_path
    try:
        rehearsal = rehearse_merges(repo_path, args.base, args.branches)
        result = analyze_repository(
            repo_path,
            args.base,
            args.branches,
            rehearsal.conflicts,
            candidate_ref=rehearsal.candidate_ref,
            candidate_tree=rehearsal.candidate_tree,
            incomplete_reasons=rehearsal.incomplete_reasons,
        )
    except Exception as exc:
        result = {
            "status": "error",
            "base": args.base,
            "branches": args.branches,
            "conflicts": [],
            "error": str(exc),
        }
    write_report(result, report_path)
    status = result.get("status", "error")
    num_conflicts = len(result.get("conflicts", []))

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if status == "clean" else 1

    # ANSI escape codes for coloring
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    if status == "clean":
        status_str = f"{GREEN}{BOLD}CLEAN{RESET}"
    elif status == "conflicts":
        status_str = f"{RED}{BOLD}CONFLICT DETECTED ({num_conflicts} conflict(s)){RESET}"
    elif status == "incomplete":
        status_str = f"{YELLOW}{BOLD}ANALYSIS INCOMPLETE{RESET}"
    else:
        status_str = f"{RED}{BOLD}ERROR{RESET}"

    print(f"Future Branch: {status_str}")
    print(f"Incident report: {YELLOW}{report_path}{RESET}")
    if result.get("error"):
        print(f"{RED}Error: {result['error']}{RESET}", file=sys.stderr)
    for reason in result.get("incomplete_reasons", []):
        print(f"{YELLOW}Incomplete: {reason}{RESET}", file=sys.stderr)
    return 0 if status == "clean" else 1


if __name__ == "__main__":
    raise SystemExit(main())
