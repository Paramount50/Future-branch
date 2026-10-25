from __future__ import annotations

from future_branch.contracts import (
    UCM_VERSION,
    ContractInventory,
    extract_javascript_consumers,
    extract_python_endpoints,
)


def test_python_endpoint_preserves_presence_and_nullability():
    source = """
from typing import Optional
from pydantic import BaseModel, Field

class UserResponse(BaseModel):
    name: str
    nickname: Optional[str]
    bio: Optional[str] = None
    internal_id: int = Field(alias="id")

@app.get("/users/{user_id}")
def get_user(user_id: str, verbose: bool = False) -> UserResponse:
    raise NotImplementedError
"""

    endpoints, coverage = extract_python_endpoints(source, "api/users.py", "candidate-1")

    assert coverage.status == "supported"
    assert len(endpoints) == 1
    endpoint = endpoints[0]
    assert endpoint.identity == ("GET", "/users/{user_id}")
    assert endpoint.snapshot_id == "candidate-1"
    assert endpoint.ucm_version == UCM_VERSION

    request = {field.name: field for field in endpoint.request_fields}
    assert request["user_id"].required is True
    assert request["user_id"].location == "path"
    assert request["verbose"].required is False
    assert request["verbose"].location == "query"

    response = {field.name: field for field in endpoint.response_fields}
    assert response["nickname"].required is True
    assert response["nickname"].nullable is True
    assert response["bio"].required is False
    assert response["bio"].nullable is True
    assert response["id"].declared_name == "internal_id"


def test_python_return_dict_is_endpoint_specific():
    source = """
@app.get("/profile")
def profile():
    return {"credits": 1, "name": "Ada"}

@app.get("/billing")
def billing():
    return {"plan": "pro"}
"""

    endpoints, _ = extract_python_endpoints(source, "api.py", "candidate-2")

    by_path = {endpoint.path: {field.name for field in endpoint.response_fields} for endpoint in endpoints}
    assert by_path["/profile"] == {"credits", "name"}
    assert by_path["/billing"] == {"plan"}


def test_fastapi_response_model_and_inherited_fields_are_extracted():
    source = """
from pydantic import BaseModel

class Entity(BaseModel):
    id: str

class Profile(Entity):
    credits: int

@app.get("/profile", response_model=Profile)
def profile():
    return service.load_profile()
"""

    endpoints, coverage = extract_python_endpoints(source, "api.py", "candidate-response-model")

    assert coverage.status == "supported"
    assert len(endpoints) == 1
    assert {field.name for field in endpoints[0].response_fields} == {"id", "credits"}


def test_fastapi_router_and_include_prefixes_are_resolved():
    source = """
router = APIRouter(prefix="/users")

@router.get("/{user_id}")
def user(user_id: str):
    return {"id": user_id}

app.include_router(router, prefix="/api/v1")
"""

    endpoints, coverage = extract_python_endpoints(source, "api.py", "candidate-router-prefix")

    assert coverage.status == "supported"
    assert endpoints[0].identity == ("GET", "/api/v1/users/{user_id}")


def test_fastapi_router_mounted_twice_emits_both_endpoints():
    source = """
router = APIRouter(prefix="/health")

@router.get("")
def health():
    return {"ok": True}

app.include_router(router, prefix="/api/v1")
app.include_router(router, prefix="/api/v2")
"""

    endpoints, coverage = extract_python_endpoints(source, "api.py", "candidate-multiple-mounts")

    assert coverage.status == "supported"
    assert {endpoint.identity for endpoint in endpoints} == {
        ("GET", "/api/v1/health"),
        ("GET", "/api/v2/health"),
    }


def test_python_syntax_error_is_coverage_error():
    endpoints, coverage = extract_python_endpoints("def broken(:\n", "broken.py", "candidate-3")

    assert endpoints == []
    assert coverage.status == "error"
    assert coverage.source.path == "broken.py"


def test_javascript_consumer_has_snapshot_and_source_evidence():
    source = """
export async function load() {
  const response = await fetch('/profile');
  const { credits } = await response.json();
  return credits;
}
"""

    consumers, coverage = extract_javascript_consumers(source, "client.ts", "candidate-4")

    assert coverage.status == "supported"
    assert len(consumers) == 1
    consumer = consumers[0]
    assert consumer.identity == ("GET", "/profile")
    assert consumer.source.line == 3
    assert consumer.snapshot_id == "candidate-4"
    assert {field.name for field in consumer.response_fields} == {"credits"}
    assert consumer.response_fields[0].source_line == 4


def test_javascript_fetch_method_is_extracted():
    source = """
await fetch('/users', {
  method: 'POST',
  body: JSON.stringify({ name: 'Ada' }),
});
"""

    consumers, coverage = extract_javascript_consumers(source, "client.ts", "candidate-method")

    assert coverage.status == "supported"
    assert len(consumers) == 1
    assert consumers[0].identity == ("POST", "/users")


def test_javascript_request_fields_and_target_are_extracted():
    source = """
await fetch('/users?verbose=true', {
  method: 'POST',
  body: JSON.stringify({ name: 'Ada', "org_id": orgId }),
});
"""

    consumers, coverage = extract_javascript_consumers(source, "client.ts", "candidate-request")

    assert coverage.status == "supported"
    consumer = consumers[0]
    assert consumer.identity == ("POST", "/users")
    assert {(field.name, field.location) for field in consumer.request_fields} == {
        ("verbose", "query"),
        ("name", "body"),
        ("org_id", "body"),
    }
    assert consumer.complete_request_locations == ("query", "body")


def test_dynamic_javascript_body_is_not_marked_complete():
    consumers, coverage = extract_javascript_consumers(
        'fetch("/users", { method: "POST", body: payload })', "client.ts", "candidate-dynamic"
    )

    assert consumers[0].complete_request_locations == ("query",)
    assert coverage.status == "partial"


def test_javascript_template_literal_target_is_extracted():
    consumers, coverage = extract_javascript_consumers("fetch(`/users/${userId}`)", "client.ts", "candidate-template")

    assert coverage.status == "supported"
    assert consumers[0].identity == ("GET", "/users/${userId}")


def test_inventory_serializes_versioned_records():
    endpoints, python_coverage = extract_python_endpoints(
        '@app.get("/health")\ndef health():\n    return {"ok": True}\n', "api.py", "candidate-5"
    )
    consumers, js_coverage = extract_javascript_consumers(
        'fetch("/health").then(response => response.json())', "client.js", "candidate-5"
    )
    inventory = ContractInventory(
        snapshot_id="candidate-5",
        endpoints=endpoints,
        consumers=consumers,
        coverage=[python_coverage, js_coverage],
    )

    encoded = inventory.to_dict()

    assert encoded["ucm_version"] == UCM_VERSION
    assert encoded["snapshot_id"] == "candidate-5"
    assert encoded["endpoints"][0]["source"]["path"] == "api.py"
    assert encoded["consumers"][0]["source"]["path"] == "client.js"
