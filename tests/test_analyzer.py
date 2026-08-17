from __future__ import annotations

from pathlib import Path

from analyzer import (
    ConflictResult,
    _js_contracts,
    _python_contracts,
    analyze_repository,
)


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
