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
    code: str = "ERR_SEMANTIC"

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
        return next(
            (
                candidate
                for candidate in candidates
                if candidate.method == endpoint.method
                and candidate.path is not None
                and endpoint.path is not None
                and _paths_match(endpoint.path, candidate.path)
            ),
            None,
        )
    return next((candidate for candidate in candidates if candidate.identity is None), None)


def _paths_match(provider_path: str, consumer_path: str) -> bool:
    def segments(path: str) -> list[str]:
        stripped = path.split("?", 1)[0].strip("/")
        return [] if not stripped else stripped.split("/")

    provider_parts = segments(provider_path)
    consumer_parts = segments(consumer_path)
    if len(provider_parts) != len(consumer_parts):
        return False
    return all(
        provider == consumer
        or (provider.startswith("{") and provider.endswith("}"))
        or (consumer.startswith("${") and consumer.endswith("}"))
        for provider, consumer in zip(provider_parts, consumer_parts, strict=True)
    )


def _consumer_matches(endpoint: EndpointContract, consumer: ConsumerContract) -> bool:
    if endpoint.identity is None:
        return True
    if consumer.identity is None:
        return False
    endpoint_method, endpoint_path = endpoint.identity
    consumer_method, consumer_path = consumer.identity
    return _paths_match(endpoint_path, consumer_path) and consumer_method in {endpoint_method, "ANY"}


def _wire_type(type_repr: str) -> str | None:
    """Map common Python annotations to conservative JSON wire categories."""
    compact = type_repr.replace(" ", "")
    if compact.startswith("Optional[") and compact.endswith("]"):
        compact = compact[9:-1]
    compact = compact.removesuffix("|None").removeprefix("None|")
    lowered = compact.lower()
    primitives = {
        "str": "string",
        "uuid": "string",
        "date": "string",
        "datetime": "string",
        "int": "number",
        "float": "number",
        "decimal": "number",
        "bool": "boolean",
        "dict": "object",
        "mapping": "object",
    }
    if lowered in primitives:
        return primitives[lowered]
    generic = re.fullmatch(r"(list|sequence|tuple|set)\[(.+)\]", lowered)
    if generic:
        item_type = _wire_type(generic.group(2))
        return f"array<{item_type}>" if item_type else "array"
    if re.fullmatch(r"(dict|mapping)\[.+\]", lowered):
        return "object"
    return None


def _field_breaks_consumer(old: Any, new: Any) -> bool:
    old_wire = _wire_type(old.type_repr)
    new_wire = _wire_type(new.type_repr)
    type_changed = old_wire is not None and new_wire is not None and old_wire != new_wire
    lost_presence = old.required and not new.required
    gained_null = not old.nullable and new.nullable
    return type_changed or lost_presence or gained_null


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
                matching_consumers = [
                    consumer for consumer in inventory.consumers if _consumer_matches(old_endpoint, consumer)
                ]
                if old_endpoint.identity is not None and new_endpoint is None:
                    replacement_methods = sorted(
                        endpoint.method
                        for endpoint in new_endpoints
                        if endpoint.path is not None
                        and old_endpoint.path is not None
                        and _paths_match(old_endpoint.path, endpoint.path)
                        and endpoint.method != old_endpoint.method
                    )
                    for consumer in matching_consumers:
                        consumer_path = consumer.source.path
                        consumer_owners = [
                            name for name, changed in changes_by_branch.items() if consumer_path in changed
                        ]
                        owners = list(dict.fromkeys([*producer_owners, *consumer_owners]))
                        if replacement_methods:
                            code = "ERR_METHOD_MISMATCH"
                            description = (
                                f"Candidate endpoint {old_endpoint.path!r} no longer accepts {old_endpoint.method}; "
                                f"the candidate consumer still sends {consumer.method}."
                            )
                            suggested_fix = (
                                f"Update the consumer to use {replacement_methods[0]} or preserve the "
                                f"{old_endpoint.method} route during migration."
                            )
                            changed_code = f"{old_endpoint.method} -> {replacement_methods}"
                        else:
                            code = "ERR_ENDPOINT_REMOVED"
                            description = (
                                f"Candidate endpoint {old_endpoint.method} {old_endpoint.path} was removed, "
                                "but the candidate consumer still calls it."
                            )
                            suggested_fix = "Update the consumer target or preserve the endpoint during migration."
                            changed_code = f"{old_endpoint.method} {old_endpoint.path} -> removed"
                        results.append(
                            ConflictResult(
                                consumer_path,
                                owners,
                                description,
                                suggested_fix,
                                changed_code=changed_code,
                                expected_code=f"{consumer.method} {consumer.target_endpoint}",
                                owner_changed=producer_owners[0] if producer_owners else "candidate",
                                owner_consumer=consumer_owners[0] if consumer_owners else "base",
                                evidence=[
                                    f"{path}:{old_endpoint.source.line}: provider before candidate",
                                    f"{consumer_path}:{consumer.source.line}: candidate consumer",
                                    f"candidate: {candidate.hexsha}",
                                ],
                                code=code,
                            )
                        )
                    continue

                old_fields = {field.name: field for field in old_endpoint.response_fields}
                new_fields = (
                    {field.name: field for field in new_endpoint.response_fields} if new_endpoint is not None else {}
                )
                removed = set(old_fields) - set(new_fields)
                for consumer in matching_consumers:
                    if not consumer.response_evidence_complete:
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
                            code="ERR_FIELD_REMOVED",
                        )
                    )

                if new_endpoint is not None:
                    for consumer in matching_consumers:
                        if not consumer.response_evidence_complete:
                            continue
                        used = {field.name for field in consumer.response_fields}
                        consumer_path = consumer.source.path
                        consumer_owners = [
                            name for name, changed in changes_by_branch.items() if consumer_path in changed
                        ]
                        owners = list(dict.fromkeys([*producer_owners, *consumer_owners]))
                        for field_name in sorted(set(old_fields) & set(new_fields) & used):
                            old_field = old_fields[field_name]
                            new_field = new_fields[field_name]
                            if not _field_breaks_consumer(old_field, new_field):
                                continue
                            old_shape = (
                                f"{old_field.type_repr}, required={old_field.required}, nullable={old_field.nullable}"
                            )
                            new_shape = (
                                f"{new_field.type_repr}, required={new_field.required}, nullable={new_field.nullable}"
                            )
                            results.append(
                                ConflictResult(
                                    consumer_path,
                                    owners,
                                    f"Candidate response field {field_name!r} changed from {old_shape} to {new_shape}, "
                                    "but the candidate consumer still reads it.",
                                    "Update the consumer for the new response shape or preserve a compatible wire contract.",
                                    changed_code=f"{field_name}: {old_shape} -> {new_shape}",
                                    expected_code=f"response.{field_name}",
                                    owner_changed=producer_owners[0] if producer_owners else "candidate",
                                    owner_consumer=consumer_owners[0] if consumer_owners else "base",
                                    evidence=[
                                        f"{path}:{new_field.source_line}: candidate provider field",
                                        f"{consumer_path}:{consumer.source.line}: candidate consumer",
                                        f"candidate: {candidate.hexsha}",
                                    ],
                                    code="ERR_TYPE_MUTATION",
                                )
                            )

                if new_endpoint is None:
                    continue
                old_request_names = {field.name for field in old_endpoint.request_fields}
                added_required = [
                    field
                    for field in new_endpoint.request_fields
                    if field.required and field.name not in old_request_names
                ]
                for consumer in inventory.consumers:
                    if not _consumer_matches(new_endpoint, consumer):
                        continue
                    supplied = {field.name for field in consumer.request_fields}
                    for required_field in added_required:
                        if (
                            required_field.name in supplied
                            or required_field.location not in consumer.complete_request_locations
                        ):
                            continue
                        consumer_path = consumer.source.path
                        consumer_owners = [
                            name for name, changed in changes_by_branch.items() if consumer_path in changed
                        ]
                        owners = list(dict.fromkeys([*producer_owners, *consumer_owners]))
                        results.append(
                            ConflictResult(
                                consumer_path,
                                owners,
                                f"Candidate endpoint {new_endpoint.method} {new_endpoint.path} added required "
                                f"{required_field.location} parameter {required_field.name!r}, but the candidate "
                                "consumer does not supply it.",
                                f"Supply {required_field.name!r} or make the new parameter optional during migration.",
                                changed_code=f"required {required_field.location}: {required_field.name}",
                                expected_code=f"{consumer.method} {consumer.target_endpoint}",
                                owner_changed=producer_owners[0] if producer_owners else "candidate",
                                owner_consumer=consumer_owners[0] if consumer_owners else "base",
                                evidence=[
                                    f"{path}:{required_field.source_line}: required provider field",
                                    f"{consumer_path}:{consumer.source.line}: complete {required_field.location} request evidence",
                                    f"candidate: {candidate.hexsha}",
                                ],
                                code="ERR_PARAM_REQUIRED",
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
        pairwise_checks: Iterable[dict[str, Any]] = (),
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
                pairwise_checks = [check.to_dict() for check in rehearsal.pairwise_checks]

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
                "pairwise_checks": list(pairwise_checks),
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
    pairwise_checks: Iterable[dict[str, Any]] = (),
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
            pairwise_checks=pairwise_checks,
        )
    finally:
        analyzer.repo.close()
