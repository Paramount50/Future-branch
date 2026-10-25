"""Static contract analysis for exact Future Branch candidate snapshots."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from git import Repo

from future_branch.contracts import (
    ConsumerContract,
    ContractInventory,
    EndpointContract,
    extract_javascript_consumers,
    extract_python_endpoints,
)


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


# Compatibility alias
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

    # Only response-shaped dictionaries contribute wire fields. String literals
    # in logs, SQL, headers, and configuration are not API contracts.
    keys: set[str] = set()
    for returned in (node for node in ast.walk(tree) if isinstance(node, ast.Return)):
        for mapping in (node for node in ast.walk(returned.value) if isinstance(node, ast.Dict)):
            keys.update(
                key.value for key in mapping.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
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
    consumed = set(re.findall(r"\b(?:response|res|data|profile|user)\s*\.\s*([A-Za-z_$][\w$]*)", source))
    for destructured in re.findall(r"\b(?:const|let|var)\s*\{([^{}]+)\}\s*=", source):
        consumed.update(
            match.group(1) for item in destructured.split(",") if (match := re.match(r"\s*([A-Za-z_$][\w$]*)", item))
        )
    result["consumed-fields"] = consumed
    return result


def _all_fields(contracts: dict[str, set[str] | str]) -> set[str]:
    fields = set(contracts.get("response-fields", set()))
    for key, value in contracts.items():
        if key.startswith("class:") and isinstance(value, set):
            fields.update(value)
    return fields


def _source_paths(commit: Any, suffixes: set[str]) -> set[str]:
    return {
        item.path
        for item in commit.tree.traverse()
        if item.type == "blob" and Path(item.path).suffix.lower() in suffixes
    }


def _endpoint_paths(contracts: dict[str, set[str] | str]) -> set[str]:
    return {route.split(" ", 1)[1] for route in contracts.get("routes", set()) if " " in route}


def _matching_endpoint(endpoint: EndpointContract, candidates: list[EndpointContract]) -> EndpointContract | None:
    if endpoint.identity is not None:
        return next((candidate for candidate in candidates if candidate.identity == endpoint.identity), None)
    return next((candidate for candidate in candidates if candidate.identity is None), None)


def _consumer_matches(endpoint: EndpointContract, consumer: ConsumerContract) -> bool:
    if endpoint.identity is None:
        return True
    if consumer.identity is None:
        return False
    endpoint_method, endpoint_path = endpoint.identity
    consumer_method, consumer_path = consumer.identity
    return endpoint_path == consumer_path and consumer_method in {endpoint_method, "ANY"}


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

    def _semantic_analysis(
        self, base_ref: str, branches: list[str], candidate_ref: str
    ) -> tuple[list[ConflictResult], list[str], ContractInventory]:
        base = self._commit(base_ref)
        candidate = self._commit(candidate_ref)
        commits = [(name, self._commit(name)) for name in branches]
        results: list[ConflictResult] = []
        incomplete: list[str] = []
        changes_by_branch = {name: _changed(base, commit) for name, commit in commits}
        candidate_changes = _changed(base, candidate)
        python_changes = {path for path in candidate_changes if Path(path).suffix.lower() == ".py"}
        inventory = ContractInventory(snapshot_id=candidate.hexsha)

        for path in _source_paths(candidate, {".js", ".mjs", ".ts", ".tsx"}):
            source = _read(candidate, path)
            if source is not None:
                consumers, coverage = extract_javascript_consumers(source, path, candidate.hexsha)
                inventory.consumers.extend(consumers)
                inventory.coverage.append(coverage)
                if coverage.status == "partial":
                    incomplete.append(f"Partial JavaScript consumer coverage at {path}: {coverage.reason}")

        for path in sorted(python_changes):
            old_source = _read(base, path) or ""
            new_source = _read(candidate, path) or ""
            old_endpoints, old_coverage = extract_python_endpoints(old_source, path, base.hexsha)
            new_endpoints, new_coverage = extract_python_endpoints(new_source, path, candidate.hexsha)
            inventory.endpoints.extend(new_endpoints)
            inventory.coverage.append(new_coverage)
            if old_coverage.status == "error":
                incomplete.append(f"Could not parse base Python source at {path}: {old_coverage.reason}")
                continue
            if new_coverage.status == "error":
                incomplete.append(f"Could not parse candidate Python source at {path}: {new_coverage.reason}")
                continue
            if new_coverage.status == "partial":
                incomplete.append(f"Partial Python endpoint coverage at {path}: {new_coverage.reason}")

            producer_owners = [name for name, changed in changes_by_branch.items() if path in changed]
            for old_endpoint in old_endpoints:
                new_endpoint = _matching_endpoint(old_endpoint, new_endpoints)
                old_fields = {field.name: field for field in old_endpoint.response_fields}
                new_fields = (
                    {field.name: field for field in new_endpoint.response_fields} if new_endpoint is not None else {}
                )
                removed = set(old_fields) - set(new_fields)
                if not removed:
                    continue
                for consumer in inventory.consumers:
                    if not _consumer_matches(old_endpoint, consumer):
                        continue
                    used = {field.name for field in consumer.response_fields}
                    stale = sorted(removed & used)
                    if not stale:
                        continue
                    consumer_path = consumer.source.path
                    consumer_owners = [name for name, changed in changes_by_branch.items() if consumer_path in changed]
                    owners = list(dict.fromkeys([*producer_owners, *consumer_owners]))
                    field_name = stale[0]
                    endpoint_label = (
                        f"{old_endpoint.method} {old_endpoint.path}"
                        if old_endpoint.path is not None
                        else f"unresolved contract in {path}"
                    )
                    results.append(
                        ConflictResult(
                            consumer_path,
                            owners,
                            f"Candidate contract removed '{field_name}', but the candidate consumer still reads it.",
                            f"Update the consumer or preserve '{field_name}' as a compatibility alias.",
                            changed_code=f"{field_name} -> {sorted(new_fields)}",
                            expected_code=f"response.{field_name}",
                            owner_changed=producer_owners[0] if producer_owners else "candidate",
                            owner_consumer=consumer_owners[0] if consumer_owners else "base",
                            evidence=[
                                f"{path}:{old_endpoint.source.line}: {endpoint_label}",
                                f"{consumer_path}:{consumer.source.line}: consumes {field_name}",
                                f"candidate: {candidate.hexsha}",
                                f"producer confidence: {old_endpoint.confidence:.2f}",
                                f"consumer confidence: {consumer.confidence:.2f}",
                            ],
                        )
                    )

        return results, incomplete, inventory

    def semantic_conflicts(
        self, base_ref: str, branches: list[str], candidate_ref: str | None = None
    ) -> list[ConflictResult]:
        if candidate_ref is None:
            from future_branch.rehearsal import rehearse_merges

            rehearsal = rehearse_merges(Path(self.repo.working_tree_dir or "."), base_ref, branches)
            if rehearsal.candidate_ref is None:
                return []
            candidate_ref = rehearsal.candidate_ref
        results, _, _ = self._semantic_analysis(base_ref, branches, candidate_ref)
        return results

    def analyze(
        self,
        base: str,
        branches: list[str],
        merge_conflicts: Iterable[ConflictResult] = (),
        candidate_ref: str | None = None,
        candidate_tree: str | None = None,
        incomplete_reasons: Iterable[str] = (),
    ) -> dict[str, Any]:
        incomplete = list(incomplete_reasons)
        try:
            self._commit(base)
            for branch in branches:
                self._commit(branch)
            if candidate_ref is None and not incomplete:
                from future_branch.rehearsal import rehearse_merges

                rehearsal = rehearse_merges(Path(self.repo.working_tree_dir or "."), base, branches)
                merge_conflicts = [*merge_conflicts, *rehearsal.conflicts]
                candidate_ref = rehearsal.candidate_ref
                candidate_tree = rehearsal.candidate_tree
                incomplete.extend(rehearsal.incomplete_reasons)

            conflicts = list(merge_conflicts)
            inventory: ContractInventory | None = None
            if candidate_ref is not None:
                semantic, coverage_gaps, inventory = self._semantic_analysis(base, branches, candidate_ref)
                conflicts.extend(semantic)
                incomplete.extend(coverage_gaps)
            elif not incomplete:
                incomplete.append("No candidate snapshot was available for semantic analysis.")

            status = "conflicts" if conflicts else "incomplete" if incomplete else "clean"
            return {
                "status": status,
                "base": base,
                "branches": branches,
                "candidate_ref": candidate_ref,
                "candidate_tree": candidate_tree,
                "conflicts": [x.to_dict() for x in conflicts],
                "incomplete_reasons": incomplete,
                "contracts": inventory.to_dict() if inventory is not None else None,
            }
        except Exception as exc:
            return {"status": "error", "base": base, "branches": branches, "conflicts": [], "error": str(exc)}


def analyze_repository(
    repo_path: str | Path,
    base: str,
    branches: list[str],
    merge_conflicts: Iterable[ConflictResult] = (),
    candidate_ref: str | None = None,
    candidate_tree: str | None = None,
    incomplete_reasons: Iterable[str] = (),
) -> dict[str, Any]:
    analyzer = BranchAnalyzer(repo_path)
    try:
        return analyzer.analyze(
            base,
            branches,
            merge_conflicts,
            candidate_ref=candidate_ref,
            candidate_tree=candidate_tree,
            incomplete_reasons=incomplete_reasons,
        )
    finally:
        analyzer.repo.close()
