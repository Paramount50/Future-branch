from __future__ import annotations

from pathlib import Path

from git import Repo

from future_branch.analyzer import (
    ConflictResult,
    _js_contracts,
    _python_contracts,
    analyze_repository,
)


def _candidate_repo(
    root: Path,
    base_files: dict[str, str],
    branch_a_files: dict[str, str | None],
    branch_b_files: dict[str, str | None],
) -> Path:
    root.mkdir()
    repo = Repo.init(str(root), initial_branch="main")
    repo.config_writer().set_value("user", "name", "Test Runner").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    def commit(files: dict[str, str | None], message: str) -> None:
        for relative, content in files.items():
            path = root / relative
            if content is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
        repo.git.add(all=True)
        repo.index.commit(message)

    commit(base_files, "base")
    repo.git.checkout("-b", "branch-a")
    commit(branch_a_files, "branch a")
    repo.git.checkout("main")
    repo.git.checkout("-b", "branch-b")
    commit(branch_b_files, "branch b")
    repo.git.checkout("main")
    repo.close()
    return root


def test_python_contracts_class_fields():
    code = """
class Profile:
    name: str
    age = 30
    tags: list[str]
"""
    contracts = _python_contracts(code)
    assert "class:Profile" in contracts
    assert contracts["class:Profile"] == {"name", "age", "tags"}


def test_python_contracts_signatures():
    code = """
def simple(x, y: int = 1) -> bool:
    return True

async def fetch_data(*args, timeout: int = 10, **kwargs) -> dict:
    return {}
"""
    contracts = _python_contracts(code)
    assert contracts["function:simple"] == "simple(x, y) -> bool"
    assert contracts["function:fetch_data"] == "fetch_data(*args, timeout, **kwargs) -> dict"


def test_python_contracts_routes():
    code = """
class App:
    def get(self, *a, **k):
        return lambda f: f

app = App()

@app.get("/api/v1/users")
def get_users():
    return [{"username": "alice"}]
"""
    contracts = _python_contracts(code)
    assert "routes" in contracts
    assert "GET /api/v1/users" in contracts["routes"]


def test_python_contracts_syntax_error_graceful():
    code = "def broken(:"
    contracts = _python_contracts(code)
    assert contracts == {}


def test_js_contracts_extraction():
    js_code = """
import { helper } from './utils';
import defaultExport from './other';

export async function getUser() {
  const response = await fetch('/api/user');
  const data = await response.json();
  console.log(response.status);
  return data.username;
}

export const API_KEY = 'secret';
"""
    contracts = _js_contracts(js_code)
    assert "getUser" in contracts["exports"]
    assert "API_KEY" in contracts["exports"]
    assert "/api/user" in contracts["api-calls"]
    assert "status" in contracts["consumed-fields"]
    assert "username" in contracts["consumed-fields"]


def test_field_rename_detected(demo_repo: Path):
    result = analyze_repository(demo_repo, "main", ["agent-a-backend", "agent-b-frontend"])
    assert result["status"] == "conflicts"
    assert len(result["conflicts"]) == 1

    conflict = result["conflicts"][0]
    assert conflict["kind"] == "semantic"
    assert "credits" in conflict["description"]
    assert conflict["owner_changed"] == "agent-a-backend"
    assert conflict["owner_consumer"] == "agent-b-frontend"


def test_clean_branches_no_conflicts(clean_repo: Path):
    result = analyze_repository(clean_repo, "main", ["feature-a", "feature-b"])
    assert result["status"] == "clean"
    assert len(result["conflicts"]) == 0


def test_conflict_result_to_dict():
    cr = ConflictResult(
        path="app.py",
        branches=["b1", "b2"],
        description="test desc",
        suggested_fix="test fix",
    )
    d = cr.to_dict()
    assert d["path"] == "app.py"
    assert d["kind"] == "semantic"
    assert d["severity"] == "error"


def test_analyzes_coordinated_merged_state(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "coordinated",
        {
            "api.py": 'def payload():\n    return {"credits": 1}\n',
            "client.js": "export function view(profile) { return profile.credits; }\n",
            "README.md": "base\n",
        },
        {
            "api.py": 'def payload():\n    return {"balance": 1}\n',
            "client.js": "export function view(profile) { return profile.balance; }\n",
        },
        {"README.md": "unrelated edit\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "incomplete"
    assert result["candidate_ref"]
    assert result["candidate_tree"]
    assert result["contracts"]["ucm_version"] == "1"
    assert result["contracts"]["snapshot_id"] == result["candidate_ref"]
    assert any(record["status"] == "partial" for record in result["contracts"]["coverage"])


def test_deleted_provider_is_not_reported_clean(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "deleted-provider",
        {"api.py": 'def payload():\n    return {"credits": 1}\n', "README.md": "base\n"},
        {"api.py": None},
        {"client.js": "export function view(profile) { return profile.credits; }\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "incomplete"
    assert result["conflicts"] == []


def test_unchanged_consumers_are_checked(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "unchanged-consumer",
        {
            "api.py": 'def payload():\n    return {"credits": 1}\n',
            "client.js": "export function view(profile) { return profile.credits; }\n",
            "README.md": "base\n",
        },
        {"api.py": 'def payload():\n    return {"balance": 1}\n'},
        {"README.md": "unrelated edit\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "incomplete"
    assert result["conflicts"] == []


def test_logs_are_not_response_fields(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "log-string",
        {"api.py": 'def payload():\n    print("credits")\n    return {"name": "Ada"}\n'},
        {"api.py": 'def payload():\n    return {"name": "Ada"}\n'},
        {"client.js": "export function view(profile) { return profile.credits; }\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "incomplete"
    assert result["conflicts"] == []


def test_endpoint_identity_prevents_field_name_collision(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "endpoint-identity",
        {"api.py": '@app.get("/profile")\ndef payload():\n    return {"credits": 1}\n'},
        {"api.py": '@app.get("/profile")\ndef payload():\n    return {"balance": 1}\n'},
        {
            "client.js": (
                'export async function view() { const data = await (await fetch("/billing")).json(); '
                "return data.credits; }\n"
            )
        },
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "clean"


def test_parse_failure_marks_analysis_incomplete(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "parse-failure",
        {"README.md": "base\n"},
        {"broken.py": "def broken(:\n"},
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "incomplete"
    assert any("broken.py" in reason for reason in result["incomplete_reasons"])


def test_destructured_consumer_is_checked(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "destructured",
        {"api.py": '@app.get("/profile")\ndef payload():\n    return {"credits": 1}\n'},
        {"api.py": '@app.get("/profile")\ndef payload():\n    return {"balance": 1}\n'},
        {
            "client.js": (
                'export async function view() { const { credits } = await (await fetch("/profile")).json(); '
                "return credits; }\n"
            )
        },
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"


def test_removed_endpoint_is_detected_without_response_field_access(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "removed-endpoint",
        {"api.py": '@app.get("/profile")\ndef profile():\n    return {"credits": 1}\n'},
        {"api.py": None},
        {"client.js": 'export async function load() { await fetch("/profile"); }\n'},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_ENDPOINT_REMOVED"]


def test_http_method_change_is_detected(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "method-mismatch",
        {"api.py": '@app.post("/profile")\ndef profile():\n    return {"ok": True}\n'},
        {"api.py": '@app.put("/profile")\ndef profile():\n    return {"ok": True}\n'},
        {"client.js": ('export async function save() { await fetch("/profile", { method: "POST" }); }\n')},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_METHOD_MISMATCH"]


def test_coordinated_http_method_change_is_clean(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "coordinated-method",
        {
            "api.py": '@app.post("/profile")\ndef profile():\n    return {"ok": True}\n',
            "client.js": 'export async function save() { await fetch("/profile", { method: "POST" }); }\n',
        },
        {"api.py": '@app.put("/profile")\ndef profile():\n    return {"ok": True}\n'},
        {"client.js": 'export async function save() { await fetch("/profile", { method: "PUT" }); }\n'},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "clean"
    assert result["conflicts"] == []


def test_new_required_query_parameter_is_detected(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "required-query",
        {
            "api.py": '@app.get("/profile")\ndef profile():\n    return {"ok": True}\n',
            "client.js": 'export async function load() { await fetch("/profile"); }\n',
            "README.md": "base\n",
        },
        {"api.py": '@app.get("/profile")\ndef profile(org_id: str):\n    return {"ok": True}\n'},
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_PARAM_REQUIRED"]


def test_coordinated_required_query_parameter_is_clean(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "coordinated-query",
        {
            "api.py": '@app.get("/profile")\ndef profile():\n    return {"ok": True}\n',
            "client.js": 'export async function load() { await fetch("/profile"); }\n',
        },
        {"api.py": '@app.get("/profile")\ndef profile(org_id: str):\n    return {"ok": True}\n'},
        {"client.js": 'export async function load() { await fetch("/profile?org_id=acme"); }\n'},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "clean"
    assert result["conflicts"] == []


def test_dynamic_request_body_does_not_create_missing_parameter_false_positive(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "dynamic-body",
        {
            "api.py": (
                "class Update:\n    name: str\n\n"
                '@app.post("/profile")\ndef profile(payload: Update):\n    return {"ok": True}\n'
            ),
            "client.js": (
                'export async function save(payload) { await fetch("/profile", { method: "POST", body: payload }); }\n'
            ),
            "README.md": "base\n",
        },
        {
            "api.py": (
                "class Update:\n    name: str\n    org_id: str\n\n"
                '@app.post("/profile")\ndef profile(payload: Update):\n    return {"ok": True}\n'
            )
        },
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "incomplete"
    assert result["conflicts"] == []


def test_new_required_body_field_is_detected_from_literal_request(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "required-body",
        {
            "api.py": (
                "class Update:\n    name: str\n\n"
                '@app.post("/profile")\ndef profile(payload: Update):\n    return {"ok": True}\n'
            ),
            "client.js": (
                'export async function save() { await fetch("/profile", '
                '{ method: "POST", body: JSON.stringify({ name: "Ada" }) }); }\n'
            ),
            "README.md": "base\n",
        },
        {
            "api.py": (
                "class Update:\n    name: str\n    org_id: str\n\n"
                '@app.post("/profile")\ndef profile(payload: Update):\n    return {"ok": True}\n'
            )
        },
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_PARAM_REQUIRED"]


def test_consumed_response_type_mutation_is_detected(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "type-mutation",
        {
            "api.py": (
                "class Profile:\n    credits: int\n\n"
                '@app.get("/profile")\ndef profile() -> Profile:\n    raise NotImplementedError\n'
            ),
            "client.js": (
                'export async function load() { const data = await (await fetch("/profile")).json(); '
                "return data.credits; }\n"
            ),
            "README.md": "base\n",
        },
        {
            "api.py": (
                "class Profile:\n    credits: str\n\n"
                '@app.get("/profile")\ndef profile() -> Profile:\n    raise NotImplementedError\n'
            )
        },
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_TYPE_MUTATION"]


def test_numeric_response_widening_is_wire_compatible(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "numeric-widening",
        {
            "api.py": (
                "class Profile:\n    credits: int\n\n"
                '@app.get("/profile")\ndef profile() -> Profile:\n    raise NotImplementedError\n'
            ),
            "client.js": (
                'export async function load() { const data = await (await fetch("/profile")).json(); '
                "return data.credits; }\n"
            ),
            "README.md": "base\n",
        },
        {
            "api.py": (
                "class Profile:\n    credits: float\n\n"
                '@app.get("/profile")\ndef profile() -> Profile:\n    raise NotImplementedError\n'
            )
        },
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "clean"
    assert result["conflicts"] == []


def test_consumed_response_becoming_nullable_is_detected(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "nullable-mutation",
        {
            "api.py": (
                "class Profile:\n    name: str\n\n"
                '@app.get("/profile")\ndef profile() -> Profile:\n    raise NotImplementedError\n'
            ),
            "client.js": (
                'export async function load() { const data = await (await fetch("/profile")).json(); '
                "return data.name; }\n"
            ),
            "README.md": "base\n",
        },
        {
            "api.py": (
                "from typing import Optional\n\nclass Profile:\n    name: Optional[str] = None\n\n"
                '@app.get("/profile")\ndef profile() -> Profile:\n    raise NotImplementedError\n'
            )
        },
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_TYPE_MUTATION"]


def test_parameterized_route_matches_template_literal_consumer(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "template-route",
        {
            "api.py": ('@app.get("/users/{user_id}")\ndef user(user_id: str):\n    return {"credits": 1}\n'),
            "client.js": (
                "export async function load(userId) { "
                "const data = await (await fetch(`/users/${userId}`)).json(); return data.credits; }\n"
            ),
            "README.md": "base\n",
        },
        {"api.py": ('@app.get("/users/{user_id}")\ndef user(user_id: str):\n    return {"balance": 1}\n')},
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_FIELD_REMOVED"]


def test_route_parameter_rename_preserves_endpoint_identity(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "route-parameter-rename",
        {
            "api.py": ('@app.get("/users/{user_id}")\ndef user(user_id: str):\n    return {"credits": 1}\n'),
            "client.js": (
                "export async function load(userId) { "
                "const data = await (await fetch(`/users/${userId}`)).json(); return data.credits; }\n"
            ),
            "README.md": "base\n",
        },
        {"api.py": '@app.get("/users/{id}")\ndef user(id: str):\n    return {"credits": 1}\n'},
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "clean"
    assert result["conflicts"] == []


def test_fastapi_response_model_field_removal_is_detected(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "response-model-removal",
        {
            "api.py": (
                "class Profile:\n    name: str\n    credits: int\n\n"
                '@app.get("/profile", response_model=Profile)\n'
                "def profile():\n    return service.load_profile()\n"
            ),
            "client.js": (
                'export async function load() { const data = await (await fetch("/profile")).json(); '
                "return data.credits; }\n"
            ),
            "README.md": "base\n",
        },
        {
            "api.py": (
                "class Profile:\n    name: str\n\n"
                '@app.get("/profile", response_model=Profile)\n'
                "def profile():\n    return service.load_profile()\n"
            )
        },
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_FIELD_REMOVED"]


def test_prefixed_fastapi_router_matches_consumer(tmp_path: Path):
    base_api = (
        'router = APIRouter(prefix="/profiles")\n\n'
        '@router.get("/{profile_id}")\n'
        'def profile(profile_id: str):\n    return {"credits": 1}\n\n'
        'app.include_router(router, prefix="/api")\n'
    )
    changed_api = base_api.replace('return {"credits": 1}', 'return {"balance": 1}')
    repo = _candidate_repo(
        tmp_path / "router-prefix-collision",
        {
            "api.py": base_api,
            "client.js": (
                "export async function load(id) { "
                "const data = await (await fetch(`/api/profiles/${id}`)).json(); return data.credits; }\n"
            ),
            "README.md": "base\n",
        },
        {"api.py": changed_api},
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "conflicts"
    assert [conflict["code"] for conflict in result["conflicts"]] == ["ERR_FIELD_REMOVED"]


def test_ambiguous_multi_fetch_fields_do_not_create_false_conflict(tmp_path: Path):
    repo = _candidate_repo(
        tmp_path / "ambiguous-multi-fetch",
        {
            "api.py": (
                '@app.get("/profile")\ndef profile():\n    return {"credits": 1}\n\n'
                '@app.get("/billing")\ndef billing():\n    return {"credits": 2}\n'
            ),
            "client.js": (
                'export async function load() { await fetch("/profile"); '
                'const data = await (await fetch("/billing")).json(); return data.credits; }\n'
            ),
            "README.md": "base\n",
        },
        {
            "api.py": (
                '@app.get("/profile")\ndef profile():\n    return {"balance": 1}\n\n'
                '@app.get("/billing")\ndef billing():\n    return {"credits": 2}\n'
            )
        },
        {"README.md": "changed\n"},
    )

    result = analyze_repository(repo, "main", ["branch-a", "branch-b"])

    assert result["status"] == "incomplete"
    assert result["conflicts"] == []
