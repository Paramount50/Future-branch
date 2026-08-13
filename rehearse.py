"""Command-line entry point for rehearsing a multi-branch Git integration."""
from __future__ import annotations

import argparse
import gc
import sys
import tempfile
from pathlib import Path

from git import GitCommandError, Repo

from analyzer import ConflictResult, analyze_repository
from reporter import write_report


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
                    paths = sorted({line.split(":", 1)[-1].strip() for line in output.splitlines() if line.startswith("CONFLICT")})
                    if not paths:
                        paths = ["(merge state)"]
                    for path in paths:
                        conflicts.append(ConflictResult(path, list(dict.fromkeys([*branches, branch])), "Git could not merge overlapping changes.", "Resolve the merge markers between the named branches, then rerun the rehearsal.", kind="merge", severity="error", owner_changed=branch, owner_consumer=branches[0], evidence=[output.strip()]))
                    try:
                        clone.git.merge(abort=True)
                    except GitCommandError:
                        pass
                    break
            return conflicts
        finally:
            clone.git.clear_cache()
            clone.close()
            future = None
            del clone
            gc.collect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rehearse parallel coding-agent branches before merge.")
    parser.add_argument("repo", help="path to the Git repository")
    parser.add_argument("branches", nargs="+", help="two or more branch names, merged in this order")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument("--report", default="incident_report.html", help="HTML report path (default: incident_report.html)")
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
        merge_conflicts = rehearse_merges(repo_path, args.base, args.branches)
        result = analyze_repository(repo_path, args.base, args.branches, merge_conflicts)
    except Exception as exc:
        result = {"status": "error", "base": args.base, "branches": args.branches, "conflicts": [], "error": str(exc)}
    write_report(result, report_path)
    status = result.get("status", "error")
    num_conflicts = len(result.get("conflicts", []))
    
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
    else:
        status_str = f"{RED}{BOLD}ERROR{RESET}"

    print(f"Future Branch: {status_str}")
    print(f"Incident report: {YELLOW}{report_path}{RESET}")
    if result.get("error"):
        print(f"{RED}Error: {result['error']}{RESET}", file=sys.stderr)
    return 0 if status == "clean" else 1


if __name__ == "__main__":
    raise SystemExit(main())
