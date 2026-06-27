import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from agent.skill_registry import SkillRegistry
from main import app
from tools import skill_installer_tool
from tools.registry import execute_tool, get_tool_names


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "skill_installer" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def skill_markdown():
    return """---
skill_id: nature_observer
name: Nature Observer
description: Help observe forests and summarize nature notes.
enabled: true
triggers:
  - forest
  - nature notes
---

# Nature Observer

## Instructions
- Ask for location, season, and observed species.
- Summarize observations into structured field notes.
"""


def test_registry_exposes_skill_tools():
    names = set(get_tool_names())

    assert {"install_skill", "list_skills"}.issubset(names)


def test_list_skills_tool_lists_static_skills():
    result = execute_tool({"name": "list_skills", "arguments": {}})

    assert result["ok"] is True
    skill_ids = {skill["skill_id"] for skill in result["result"]["skills"]}
    assert {"web_research", "code_review", "stm32_debug", "course_report"}.issubset(skill_ids)


def test_install_skill_downloads_markdown_to_imported_dir(monkeypatch):
    tmp_path = local_tmp_path()
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(skill_markdown()))
    imported_dir = tmp_path / "skills" / "imported"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)

    result = execute_tool(
        {
            "name": "install_skill",
            "arguments": {"url": "https://example.test/skills/nature.md"},
        }
    )

    assert result["ok"] is True
    payload = result["result"]
    assert payload["skill_id"] == "nature_observer"
    assert payload["path"].endswith("nature_observer.md")
    assert (imported_dir / "nature_observer.md").read_text(encoding="utf-8") == skill_markdown()


def test_install_skill_invalid_url_returns_structured_tool_error():
    result = execute_tool({"name": "install_skill", "arguments": {"url": "file:///tmp/skill.md"}})

    assert result["ok"] is False
    assert result["tool"] == "install_skill"
    assert result["error"]["code"] == "invalid_url"


def test_installed_skill_can_match_next_round(monkeypatch):
    tmp_path = local_tmp_path()
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(skill_markdown()))
    static_dir = tmp_path / "skills"
    imported_dir = static_dir / "imported"
    generated_dir = tmp_path / "generated_skills"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)

    execute_tool({"name": "install_skill", "arguments": {"url": "https://example.test/nature.md"}})
    registry = SkillRegistry(static_dir=static_dir, generated_dir=generated_dir)

    matched = registry.match("please organize these forest observations")

    assert matched[0]["skill_id"] == "nature_observer"


def test_skills_api_lists_and_installs(monkeypatch):
    tmp_path = local_tmp_path()
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(skill_markdown()))
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    imported_dir = static_dir / "imported"
    static_dir.mkdir(parents=True)
    generated_dir.mkdir()
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", static_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", generated_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)

    client = TestClient(app)
    install_response = client.post("/skills/install", json={"url": "https://example.test/nature.md"})

    assert install_response.status_code == 200
    assert install_response.json()["skill_id"] == "nature_observer"

    list_response = client.get("/skills")

    assert list_response.status_code == 200
    skills = list_response.json()["skills"]
    assert skills[0]["skill_id"] == "nature_observer"
    assert skills[0]["enabled"] is True
