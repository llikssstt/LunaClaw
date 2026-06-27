import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from agent.skill_registry import SkillRegistry
from main import app
from tools import skill_installer_tool
from tools.registry import execute_tool


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "skill_installer_contract" / uuid.uuid4().hex
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
skill_id: nature_reader
name: Nature Reader
description: Build bilingual paper readers with figure-text alignment.
enabled: true
triggers:
  - nature reader
  - paper reader
  - 原文对照
---

# Nature Reader

## Instructions
- Keep paragraph-level source anchors.
- Pair figures with the text that discusses them.
"""


def test_install_skill_saves_downloaded_markdown(monkeypatch):
    tmp_path = local_tmp_path()
    imported_dir = tmp_path / "skills" / "imported"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(skill_markdown()))

    result = skill_installer_tool.install_skill("https://example.test/nature-reader.md")

    assert result["ok"] is True
    assert result["skill_id"] == "nature_reader"
    assert (imported_dir / "nature_reader.md").read_text(encoding="utf-8") == skill_markdown()


def test_list_skills_returns_static_skill_shape():
    result = skill_installer_tool.list_skills()

    assert result["ok"] is True
    web_research = next(skill for skill in result["skills"] if skill["skill_id"] == "web_research")
    assert {"skill_id", "name", "description", "triggers", "enabled", "path"}.issubset(web_research)


def test_github_blob_url_is_converted_to_raw_url(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return FakeResponse(skill_markdown())

    monkeypatch.setattr(skill_installer_tool.requests, "get", fake_get)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", local_tmp_path() / "skills" / "imported")

    result = skill_installer_tool.install_skill(
        "https://github.com/Yuan1z0825/nature-skills/blob/main/skills/nature-reader/SKILL.md"
    )

    assert result["ok"] is True
    assert captured["url"] == "https://raw.githubusercontent.com/Yuan1z0825/nature-skills/main/skills/nature-reader/SKILL.md"


def test_github_repo_url_is_converted_to_readme_raw_url(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return FakeResponse("# nature-skills\n\nRepository overview.")

    monkeypatch.setattr(skill_installer_tool.requests, "get", fake_get)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", local_tmp_path() / "skills" / "imported")

    result = skill_installer_tool.install_skill("https://github.com/Yuan1z0825/nature-skills", skill_id="nature_skills")

    assert result["ok"] is True
    assert captured["url"] == "https://raw.githubusercontent.com/Yuan1z0825/nature-skills/main/README.md"


def test_install_skill_rejects_invalid_url():
    result = execute_tool({"name": "install_skill", "arguments": {"url": "file:///tmp/SKILL.md"}})

    assert result["ok"] is False
    assert result["tool"] == "install_skill"
    assert result["error"]["code"] == "invalid_url"


def test_install_skill_rejects_invalid_markdown(monkeypatch):
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse("<html>not markdown</html>"))

    result = execute_tool({"name": "install_skill", "arguments": {"url": "https://example.test/not-skill"}})

    assert result["ok"] is False
    assert result["tool"] == "install_skill"
    assert result["error"]["code"] == "invalid_skill"


def test_installed_skill_can_be_matched(monkeypatch):
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    imported_dir = static_dir / "imported"
    generated_dir = tmp_path / "generated_skills"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(skill_markdown()))

    skill_installer_tool.install_skill("https://example.test/nature-reader.md")
    matches = SkillRegistry(static_dir=static_dir, generated_dir=generated_dir).match("帮我做原文对照 paper reader")

    assert matches[0]["skill_id"] == "nature_reader"


def test_skills_api_lists_and_installs(monkeypatch):
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    imported_dir = static_dir / "imported"
    static_dir.mkdir(parents=True)
    generated_dir.mkdir()
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", static_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", generated_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(skill_markdown()))

    client = TestClient(app)
    install_response = client.post("/skills/install", json={"url": "https://example.test/nature-reader.md"})
    list_response = client.get("/skills")

    assert install_response.status_code == 200
    assert install_response.json()["skill_id"] == "nature_reader"
    assert list_response.status_code == 200
    assert list_response.json()["skills"][0]["skill_id"] == "nature_reader"
