"""Pure-Python contract analysis for Future Branch rehearsals."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from git import Repo


@dataclass
class ConflictResult:
    path: str
    branches: list[str]
    description: str
    suggested_fix: str
    kind: str = "semantic"
    severity: str = "error"
    changed_code: str = ""
    expected_code: str = ""
    owner_changed: str = ""
    owner_consumer: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Kept as a compatibility alias for the first prototype.
Conflict = ConflictResult


def _read(commit: Any, path: str) -> str | None:
    try:
        return (commit.tree / path).data_stream.read().decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        return None


def _changed(base: Any, commit: Any) -> set[str]:
    paths: set[str] = set()
    for diff in commit.diff(base):
        paths.update(p for p in (diff.a_path, diff.b_path) if p)
    return paths


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [a.arg for a in node.args.posonlyargs + node.args.args]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    args.extend(a.arg for a in node.args.kwonlyargs)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    annotation = ast.unparse(node.returns) if node.returns else ""
    return f"{node.name}({', '.join(args)}) -> {annotation}" if annotation else f"{node.name}({', '.join(args)})"


def _python_contracts(source: str) -> dict[str, set[str] | str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    result: dict[str, set[str] | str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[f"function:{node.name}"] = _signature(node)
        elif isinstance(node, ast.ClassDef):
            fields: set[str] = set()
            for child in node.body:
                if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    fields.add(child.target.id)
                elif isinstance(child, ast.Assign):
                    fields.update(t.id for t in child.targets if isinstance(t, ast.Name))
            if fields:
                result[f"class:{node.name}"] = fields
    # Include dict response keys, which covers small FastAPI-style examples.
    keys = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    result["response-fields"] = keys
    routes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.args
                    and isinstance(dec.args[0], ast.Constant)
                    and dec.func.attr in {"get", "post", "put", "patch", "delete"}
                    and isinstance(dec.args[0].value, str)
                ):
                    routes.add(f"{dec.func.attr.upper()} {dec.args[0].value}")
    result["routes"] = routes
    return result


def _js_contracts(source: str) -> dict[str, set[str] | str]:
    result: dict[str, set[str] | str] = {}
    exports = set(re.findall(r"\bexport\s+(?:async\s+)?(?:function|const|let|class)\s+([A-Za-z_$][\w$]*)", source))
    imports = set(re.findall(r"\bimport\s+(?:\{([^}]+)\}|([\w$]+))\s+from\s+['\"]([^'\"]+)", source))
    result["exports"] = exports
    result["imports"] = {str(x).strip() for item in imports for x in item if x}
    result["api-calls"] = set(re.findall(r"fetch\s*\(\s*['\"]([^'\"]+)", source))
    result["consumed-fields"] = set(
        re.findall(r"\b(?:response|res|data|profile|user)\s*\.\s*([A-Za-z_$][\w$]*)", source)
    )
    return result


def _all_fields(contracts: dict[str, set[str] | str]) -> set[str]:
    fields = set(contracts.get("response-fields", set()))
    for key, value in contracts.items():
        if key.startswith("class:") and isinstance(value, set):
            fields.update(value)
    return fields


class BranchAnalyzer:
    def __init__(self, repo_path: str | Path = ".") -> None:
        self.repo = Repo(str(repo_path))

    def _commit(self, ref: str) -> Any:
        return self.repo.commit(ref)

    def textual_conflict(self, path: str, branches: list[str], details: str = "") -> ConflictResult:
        return ConflictResult(
            path,
            branches,
            "Git could not merge overlapping changes.",
            "Resolve the conflict, then rerun the rehearsal.",
            kind="merge",
            severity="error",
            evidence=[details] if details else [],
        )

    def semantic_conflicts(self, base_ref: str, branches: list[str]) -> list[ConflictResult]:
        base = self._commit(base_ref)
        commits = [(name, self._commit(name)) for name in branches]
        results: list[ConflictResult] = []
        python_by_branch: dict[str, dict[str, dict[str, set[str] | str]]] = {}
        js_by_branch: dict[str, dict[str, dict[str, set[str] | str]]] = {}
        for name, commit in commits:
            python_by_branch[name] = {}
            js_by_branch[name] = {}
            for path in _changed(base, commit):
                source = _read(commit, path)
                if source is None:
                    continue
                if Path(path).suffix.lower() == ".py":
                    python_by_branch[name][path] = _python_contracts(source)
                elif Path(path).suffix.lower() in {".js", ".mjs", ".ts", ".tsx"}:
                    js_by_branch[name][path] = _js_contracts(source)

        for changed_name, changed_files in python_by_branch.items():
            for path, contracts in changed_files.items():
                base_contracts = _python_contracts(_read(base, path) or "")
                old_fields = _all_fields(base_contracts)
                new_fields = _all_fields(contracts)
                removed = old_fields - new_fields
                if not removed:
                    continue
                for consumer_name, files in js_by_branch.items():
                    if consumer_name == changed_name:
                        continue
                    for consumer_path, consumer in files.items():
                        used = set(consumer.get("consumed-fields", set()))
                        stale = sorted(removed & used)
                        if stale:
                            field_name = stale[0]
                            results.append(
                                ConflictResult(
                                    consumer_path,
                                    [changed_name, consumer_name],
                                    f"Backend contract removed '{field_name}', but the frontend still reads response.{field_name}.",
                                    f"Have {consumer_name} consume the renamed field, or preserve '{field_name}' as a compatibility alias in {changed_name}.",
                                    changed_code=f"{field_name} -> {sorted(new_fields)}",
                                    expected_code=f"response.{field_name}",
                                    owner_changed=changed_name,
                                    owner_consumer=consumer_name,
                                    evidence=[
                                        f"{path}: fields changed from {sorted(old_fields)} to {sorted(new_fields)}",
                                        f"{consumer_path}: response.{field_name}",
                                    ],
                                )
                            )
        for name_a, files_a in python_by_branch.items():
            for name_b, files_b in python_by_branch.items():
                if name_a >= name_b:
                    continue
                for path in set(files_a) & set(files_b):
                    ca, cb = files_a[path], files_b[path]
                    for symbol in set(ca) & set(cb):
                        if isinstance(ca[symbol], str) and ca[symbol] != cb[symbol]:
                            results.append(
                                ConflictResult(
                                    path,
                                    [name_a, name_b],
                                    f"Both branches changed the Python contract {symbol} incompatibly.",
                                    "Coordinate one signature and update every caller before merging.",
                                    changed_code=str(ca[symbol]),
                                    expected_code=str(cb[symbol]),
                                    owner_changed=name_a,
                                    owner_consumer=name_b,
                                    evidence=[f"{name_a}: {ca[symbol]}", f"{name_b}: {cb[symbol]}"],
                                )
                            )
        return results

    def analyze(self, base: str, branches: list[str], merge_conflicts: Iterable[ConflictResult] = ()) -> dict[str, Any]:
        try:
            self._commit(base)
            for branch in branches:
                self._commit(branch)
            conflicts = list(merge_conflicts) + self.semantic_conflicts(base, branches)
            return {
                "status": "conflicts" if conflicts else "clean",
                "base": base,
                "branches": branches,
                "conflicts": [x.to_dict() for x in conflicts],
            }
        except Exception as exc:
            return {"status": "error", "base": base, "branches": branches, "conflicts": [], "error": str(exc)}


def analyze_repository(
    repo_path: str | Path, base: str, branches: list[str], merge_conflicts: Iterable[ConflictResult] = ()
) -> dict[str, Any]:
    return BranchAnalyzer(repo_path).analyze(base, branches, merge_conflicts)
