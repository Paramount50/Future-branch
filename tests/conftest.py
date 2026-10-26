from __future__ import annotations

import gc
from pathlib import Path

import pytest
from git import Repo


@pytest.fixture
def demo_repo(tmp_path: Path) -> Path:
    """Create a temporary Git repository replicating the standard demo conflict."""
    repo_dir = tmp_path / "demo_repo"
    repo_dir.mkdir()
    backend_dir = repo_dir / "backend"
    frontend_dir = repo_dir / "frontend"
    backend_dir.mkdir()
    frontend_dir.mkdir()

    # Base state
    app_py = backend_dir / "app.py"
    app_py.write_text(
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class UserResponse:\n"
        "    username: str\n"
        "    credits: int\n\n"
        "def get_profile() -> UserResponse:\n"
        '    return UserResponse(username="ada", credits=42)\n',
        encoding="utf-8",
    )

    api_js = frontend_dir / "api.js"
    api_js.write_text(
        "export async function loadProfile() {\n"
        '  const response = await fetch("/api/profile");\n'
        "  return response.json();\n"
        "}\n",
        encoding="utf-8",
    )

    repo = Repo.init(str(repo_dir), initial_branch="main")
    repo.config_writer().set_value("user", "name", "Test Runner").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    repo.git.add(all=True)
    repo.index.commit("main: initial commit")

    # Agent A: Backend renames credits -> creditsbalance
    repo.git.checkout("-b", "agent-a-backend")
    app_py.write_text(
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class UserResponse:\n"
        "    username: str\n"
        "    creditsbalance: int\n\n"
        "def get_profile() -> UserResponse:\n"
        '    return UserResponse(username="ada", creditsbalance=42)\n',
        encoding="utf-8",
    )
    repo.git.add(str(app_py))
    repo.index.commit("agent-a: rename credits to creditsbalance")

    # Agent B: Frontend consumes profile.credits
    repo.git.checkout("main")
    repo.git.checkout("-b", "agent-b-frontend")
    api_js.write_text(
        "export async function loadProfile() {\n"
        '  const response = await fetch("/api/profile");\n'
        "  return response.json();\n"
        "}\n\n"
        "export function showBilling(profile) {\n"
        "  return `Billing credits: ${profile.credits}`;\n"
        "}\n",
        encoding="utf-8",
    )
    repo.git.add(str(api_js))
    repo.index.commit("agent-b: consume credits")

    repo.git.checkout("main")
    repo.close()
    gc.collect()

    return repo_dir


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    """Create a temporary Git repository with two non-conflicting branches."""
    repo_dir = tmp_path / "clean_repo"
    repo_dir.mkdir()
    backend_dir = repo_dir / "backend"
    backend_dir.mkdir()

    app_py = backend_dir / "app.py"
    app_py.write_text(
        'def greet(name: str) -> str:\n    return f"Hello {name}"\n',
        encoding="utf-8",
    )

    repo = Repo.init(str(repo_dir), initial_branch="main")
    repo.config_writer().set_value("user", "name", "Test Runner").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    repo.git.add(all=True)
    repo.index.commit("main: initial commit")

    # Branch A: Adds helper
    repo.git.checkout("-b", "feature-a")
    helper_py = backend_dir / "helper.py"
    helper_py.write_text("def helper() -> int:\n    return 1\n", encoding="utf-8")
    repo.git.add(str(helper_py))
    repo.index.commit("feature-a: add helper")

    # Branch B: Adds another helper
    repo.git.checkout("main")
    repo.git.checkout("-b", "feature-b")
    utils_py = backend_dir / "utils.py"
    utils_py.write_text("def util() -> int:\n    return 2\n", encoding="utf-8")
    repo.git.add(str(utils_py))
    repo.index.commit("feature-b: add util")

    repo.git.checkout("main")
    repo.close()
    gc.collect()

    return repo_dir


@pytest.fixture
def merge_conflict_repo(tmp_path: Path) -> Path:
    """Create a temporary Git repository with a textual merge conflict."""
    repo_dir = tmp_path / "merge_conflict_repo"
    repo_dir.mkdir()

    file_txt = repo_dir / "file.txt"
    file_txt.write_text("initial line\n", encoding="utf-8")

    repo = Repo.init(str(repo_dir), initial_branch="main")
    repo.config_writer().set_value("user", "name", "Test Runner").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    repo.git.add(all=True)
    repo.index.commit("main: initial commit")

    # Branch A edits file.txt
    repo.git.checkout("-b", "branch-a")
    file_txt.write_text("branch A change\n", encoding="utf-8")
    repo.git.add(str(file_txt))
    repo.index.commit("branch-a: edit file.txt")

    # Branch B edits same line in file.txt
    repo.git.checkout("main")
    repo.git.checkout("-b", "branch-b")
    file_txt.write_text("branch B change\n", encoding="utf-8")
    repo.git.add(str(file_txt))
    repo.index.commit("branch-b: edit file.txt")

    repo.git.checkout("main")
    repo.close()
    gc.collect()

    return repo_dir
