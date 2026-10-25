"""Versioned, language-neutral contract records and bounded extractors."""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

UCM_VERSION = "1"


@dataclass(frozen=True)
class SourceLocation:
    path: str
    line: int
    column: int = 0


@dataclass(frozen=True)
class FieldContract:
    name: str
    type_repr: str = "unknown"
    required: bool = True
    nullable: bool = False
    location: Literal["path", "query", "body", "response", "unknown"] = "unknown"
    source_line: int = 0
    declared_name: str | None = None


@dataclass(frozen=True)
class EndpointContract:
    method: str
    path: str | None
    request_fields: tuple[FieldContract, ...]
    response_fields: tuple[FieldContract, ...]
    source: SourceLocation
    snapshot_id: str
    confidence: float
    extractor: str = "python-ast-v1"
    ucm_version: str = UCM_VERSION

    @property
    def identity(self) -> tuple[str, str] | None:
        if self.path is None:
            return None
        return self.method, self.path

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConsumerContract:
    method: str
    target_endpoint: str | None
    request_fields: tuple[FieldContract, ...]
    response_fields: tuple[FieldContract, ...]
    source: SourceLocation
    snapshot_id: str
    confidence: float
    extractor: str = "javascript-pattern-v1"
    ucm_version: str = UCM_VERSION

    @property
    def identity(self) -> tuple[str, str] | None:
        if self.target_endpoint is None:
            return None
        return self.method, self.target_endpoint

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageRecord:
    source: SourceLocation
    language: str
    status: Literal["supported", "partial", "error"]
    reason: str
    extractor: str
    snapshot_id: str
    ucm_version: str = UCM_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContractInventory:
    snapshot_id: str
    endpoints: list[EndpointContract] = field(default_factory=list)
    consumers: list[ConsumerContract] = field(default_factory=list)
    coverage: list[CoverageRecord] = field(default_factory=list)
    ucm_version: str = UCM_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "ucm_version": self.ucm_version,
            "snapshot_id": self.snapshot_id,
            "endpoints": [endpoint.to_dict() for endpoint in self.endpoints],
            "consumers": [consumer.to_dict() for consumer in self.consumers],
            "coverage": [record.to_dict() for record in self.coverage],
        }


def _annotation(annotation: ast.expr | None) -> tuple[str, bool]:
    if annotation is None:
        return "unknown", False
    rendered = ast.unparse(annotation)
    nullable = (
        isinstance(annotation, ast.Subscript)
        and isinstance(annotation.value, ast.Name)
        and annotation.value.id == "Optional"
    ) or "None" in rendered.split(" | ")
    return rendered, nullable


def _wire_name(node: ast.AnnAssign) -> str:
    declared = node.target.id if isinstance(node.target, ast.Name) else "unknown"
    if not isinstance(node.value, ast.Call):
        return declared
    for keyword in node.value.keywords:
        if (
            keyword.arg in {"alias", "serialization_alias"}
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            return keyword.value.value
    return declared


def _is_required(node: ast.AnnAssign) -> bool:
    if node.value is None:
        return True
    if not isinstance(node.value, ast.Call):
        return False
    call_name = node.value.func.id if isinstance(node.value.func, ast.Name) else ""
    if call_name != "Field":
        return False
    if node.value.args:
        return isinstance(node.value.args[0], ast.Constant) and node.value.args[0].value is Ellipsis
    return not any(keyword.arg == "default" for keyword in node.value.keywords)


def _class_fields(tree: ast.AST) -> dict[str, tuple[FieldContract, ...]]:
    models: dict[str, tuple[FieldContract, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        fields: list[FieldContract] = []
        for child in node.body:
            if not isinstance(child, ast.AnnAssign) or not isinstance(child.target, ast.Name):
                continue
            type_repr, nullable = _annotation(child.annotation)
            fields.append(
                FieldContract(
                    name=_wire_name(child),
                    declared_name=child.target.id,
                    type_repr=type_repr,
                    required=_is_required(child),
                    nullable=nullable,
                    location="response",
                    source_line=child.lineno,
                )
            )
        if fields:
            models[node.name] = tuple(fields)
    return models


def _route(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, str] | None:
    for decorator in node.decorator_list:
        if not (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in {"get", "post", "put", "patch", "delete"}
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and isinstance(decorator.args[0].value, str)
        ):
            continue
        return decorator.func.attr.upper(), decorator.args[0].value
    return None


def _request_fields(node: ast.FunctionDef | ast.AsyncFunctionDef, route_path: str) -> tuple[FieldContract, ...]:
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    fields: list[FieldContract] = []
    for argument, default in zip(positional, defaults, strict=True):
        if argument.arg in {"self", "cls"}:
            continue
        type_repr, nullable = _annotation(argument.annotation)
        fields.append(
            FieldContract(
                name=argument.arg,
                type_repr=type_repr,
                required=default is None,
                nullable=nullable,
                location="path" if "{" + argument.arg + "}" in route_path else "query",
                source_line=argument.lineno,
            )
        )
    return tuple(fields)


def _returned_fields(
    node: ast.FunctionDef | ast.AsyncFunctionDef, models: dict[str, tuple[FieldContract, ...]]
) -> tuple[FieldContract, ...]:
    if isinstance(node.returns, ast.Name) and node.returns.id in models:
        return models[node.returns.id]
    fields: dict[str, FieldContract] = {}
    for returned in (candidate for candidate in ast.walk(node) if isinstance(candidate, ast.Return)):
        for mapping in (candidate for candidate in ast.walk(returned.value) if isinstance(candidate, ast.Dict)):
            for key, value in zip(mapping.keys, mapping.values, strict=True):
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    continue
                inferred = type(value.value).__name__ if isinstance(value, ast.Constant) else "unknown"
                fields[key.value] = FieldContract(
                    name=key.value,
                    type_repr=inferred,
                    required=True,
                    nullable=isinstance(value, ast.Constant) and value.value is None,
                    location="response",
                    source_line=getattr(key, "lineno", node.lineno),
                )
    return tuple(fields.values())


def extract_python_endpoints(source: str, path: str, snapshot_id: str) -> tuple[list[EndpointContract], CoverageRecord]:
    location = SourceLocation(path=path, line=1)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [], CoverageRecord(
            source=SourceLocation(path=path, line=exc.lineno or 1, column=exc.offset or 0),
            language="python",
            status="error",
            reason=exc.msg,
            extractor="python-ast-v1",
            snapshot_id=snapshot_id,
        )

    models = _class_fields(tree)
    endpoints: list[EndpointContract] = []
    implicit_fields: dict[str, FieldContract] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        response_fields = _returned_fields(node, models)
        route = _route(node)
        if route is None:
            for response_field in response_fields:
                implicit_fields[response_field.name] = response_field
            continue
        method, route_path = route
        endpoints.append(
            EndpointContract(
                method=method,
                path=route_path,
                request_fields=_request_fields(node, route_path),
                response_fields=response_fields,
                source=SourceLocation(path=path, line=node.lineno, column=node.col_offset),
                snapshot_id=snapshot_id,
                confidence=0.9,
            )
        )

    # A bounded compatibility fallback keeps non-framework examples observable.
    # Its missing identity and lower confidence prevent it from masquerading as
    # a resolved HTTP endpoint.
    if not endpoints:
        for model_fields in models.values():
            for model_field in model_fields:
                implicit_fields[model_field.name] = model_field
        if implicit_fields:
            endpoints.append(
                EndpointContract(
                    method="ANY",
                    path=None,
                    request_fields=(),
                    response_fields=tuple(implicit_fields.values()),
                    source=location,
                    snapshot_id=snapshot_id,
                    confidence=0.4,
                )
            )

    status: Literal["supported", "partial"] = (
        "supported" if not endpoints or all(endpoint.path for endpoint in endpoints) else "partial"
    )
    reason = (
        "No endpoint contract found."
        if not endpoints
        else "Extracted decorated Python endpoints."
        if status == "supported"
        else "No resolved route; emitted a file-level contract."
    )
    return endpoints, CoverageRecord(
        source=location,
        language="python",
        status=status,
        reason=reason,
        extractor="python-ast-v1",
        snapshot_id=snapshot_id,
    )


def extract_javascript_consumers(
    source: str, path: str, snapshot_id: str
) -> tuple[list[ConsumerContract], CoverageRecord]:
    calls = list(re.finditer(r"fetch\s*\(\s*['\"]([^'\"]+)", source))
    field_lines: dict[str, int] = {}
    for match in re.finditer(r"\b(?:response|res|data|profile|user)\s*\.\s*([A-Za-z_$][\w$]*)", source):
        name = match.group(1)
        if name != "json":
            field_lines.setdefault(name, source.count("\n", 0, match.start(1)) + 1)
    for match in re.finditer(r"\b(?:const|let|var)\s*\{([^{}]+)\}\s*=", source):
        for item in match.group(1).split(","):
            if name := re.match(r"\s*([A-Za-z_$][\w$]*)", item):
                field_lines.setdefault(name.group(1), source.count("\n", 0, match.start(1)) + 1)
    response_fields = tuple(
        FieldContract(name=name, required=True, location="response", source_line=field_lines[name])
        for name in sorted(field_lines)
    )
    consumers = [
        ConsumerContract(
            method="GET",
            target_endpoint=call.group(1),
            request_fields=(),
            response_fields=response_fields,
            source=SourceLocation(path=path, line=source.count("\n", 0, call.start()) + 1),
            snapshot_id=snapshot_id,
            confidence=0.7 if len(calls) == 1 else 0.45,
        )
        for call in calls
    ]
    if not calls and response_fields:
        first_field = min((field.source_line for field in response_fields), default=1)
        consumers.append(
            ConsumerContract(
                method="ANY",
                target_endpoint=None,
                request_fields=(),
                response_fields=response_fields,
                source=SourceLocation(path=path, line=first_field),
                snapshot_id=snapshot_id,
                confidence=0.35,
            )
        )
    status: Literal["supported", "partial"] = (
        "supported" if len(calls) == 1 or (not calls and not response_fields) else "partial"
    )
    reason = (
        "Extracted one fetch consumer."
        if len(calls) == 1
        else "No consumer contract found."
        if not calls and not response_fields
        else "No fetch target; emitted an unresolved file-level consumer."
        if not calls
        else "Multiple fetch calls share file-level field evidence."
    )
    return consumers, CoverageRecord(
        source=SourceLocation(path=path, line=1),
        language="javascript",
        status=status,
        reason=reason,
        extractor="javascript-pattern-v1",
        snapshot_id=snapshot_id,
    )
