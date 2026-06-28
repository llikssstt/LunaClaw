import uuid
import zipfile
from io import BytesIO
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
    def __init__(self, text, status_code=200, content=None):
        self.text = text
        self.content = content if content is not None else (text.encode("utf-8") if isinstance(text, str) else b"")
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


def test_github_repo_url_delegates_to_pack_installer(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return FakeResponse("# nature-skills\n\nRepository overview.")

    monkeypatch.setattr(skill_installer_tool.requests, "get", fake_get)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", local_tmp_path() / "skills" / "imported")

    result = skill_installer_tool.install_skill("https://github.com/Yuan1z0825/nature-skills", skill_id="nature_skills")

    assert result["ok"] is True
    assert result["mode"] == "pack"
    assert captured["url"] == "https://api.github.com/repos/Yuan1z0825/nature-skills/zipball/main"


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


def pack_skill_md(name, trigger):
    return f"""---
name: {name}
description: {name} workflow.
enabled: true
triggers:
  - {trigger}
---

# {name}

## Instructions
- Use the saved SKILL.md only.
"""


def build_pack_zip():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pack-main/skills/nature-reader/SKILL.md", pack_skill_md("Nature Reader", "reader trigger"))
        archive.writestr("pack-main/skills/nature-reader/helper.py", "print('helper is saved but not executed')\n")
        archive.writestr("pack-main/skills/nature-reader/references/guide.md", "# Guide\n\nResource note.")
        archive.writestr("pack-main/skills/nature-reader/static/icon.png", b"\x89PNG\r\n\x1a\n\x00\x00binary")
        archive.writestr("pack-main/skills/nature-figure/SKILL.md", pack_skill_md("Nature Figure", "figure trigger"))
        archive.writestr("pack-main/skills/nature-figure/manifest.yaml", "name: nature-figure\n")
        archive.writestr("pack-main/docs/readme.md", "# Not a scanned skill")
    return buffer.getvalue()


def test_install_skill_pack_uses_zipball_and_preserves_complete_directories(monkeypatch):
    tmp_path = local_tmp_path()
    imported_dir = tmp_path / "skills" / "imported"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        if url == "https://api.github.com/repos/acme/pack/zipball/main":
            return FakeResponse("", content=build_pack_zip())
        return FakeResponse({"message": "not found"}, status_code=404)

    monkeypatch.setattr(skill_installer_tool.requests, "get", fake_get)

    result = skill_installer_tool.install_skill_pack("https://github.com/acme/pack", pack_id="demo_pack")

    assert result["ok"] is True
    assert result["mode"] == "pack"
    assert captured["url"] == "https://api.github.com/repos/acme/pack/zipball/main"
    assert result["installed_count"] == 2
    assert result["failed_count"] == 0
    assert {skill["skill_id"] for skill in result["installed_skills"]} == {
        "demo_pack_skills_nature-reader",
        "demo_pack_skills_nature-figure",
    }
    assert (imported_dir / "demo_pack" / "skills" / "nature-reader" / "helper.py").exists()
    assert (imported_dir / "demo_pack" / "skills" / "nature-reader" / "references" / "guide.md").exists()
    assert (imported_dir / "demo_pack" / "skills" / "nature-reader" / "static" / "icon.png").read_bytes() == b"\x89PNG\r\n\x1a\n\x00\x00binary"

    registry = SkillRegistry(static_dir=tmp_path / "skills", generated_dir=tmp_path / "generated_skills")
    reader = next(skill for skill in registry.load_skills() if skill["skill_id"] == "demo_pack_skills_nature-reader")
    assert reader["path"].endswith("SKILL.md")
    assert "helper.py" in reader["resources"]
    assert "references/guide.md" in reader["resources"]
    assert "static/icon.png" in reader["resources"]
    assert registry.match("please use reader trigger")[0]["skill_id"] == "demo_pack_skills_nature-reader"


def test_lifecycle_enable_disable_preserves_metadata_and_controls_matching(monkeypatch):
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    imported_dir = static_dir / "imported"
    generated_dir = tmp_path / "generated_skills"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", static_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", generated_dir)
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(skill_markdown()))

    install_result = skill_installer_tool.install_skill("https://example.test/nature-reader.md")
    skill_id = install_result["skill_id"]
    registry = SkillRegistry(static_dir=static_dir, generated_dir=generated_dir)

    assert registry.match("paper reader")[0]["skill_id"] == skill_id
    disabled = skill_installer_tool.disable_skill(skill_id)

    assert disabled["ok"] is True
    text_after_disable = Path(disabled["path"]).read_text(encoding="utf-8")
    assert "description: Build bilingual paper readers with figure-text alignment." in text_after_disable
    assert "# Nature Reader" in text_after_disable
    assert registry.match("paper reader") == []

    enabled = skill_installer_tool.enable_skill(skill_id)

    assert enabled["ok"] is True
    assert registry.match("paper reader")[0]["skill_id"] == skill_id


def test_lifecycle_rejects_ambiguous_skill_id(monkeypatch):
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", static_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", generated_dir)
    (static_dir / "imported" / "a").mkdir(parents=True)
    (static_dir / "imported" / "b").mkdir(parents=True)
    for folder in ["a", "b"]:
        (static_dir / "imported" / folder / "SKILL.md").write_text(
            """---
skill_id: duplicate_skill
name: Duplicate
enabled: true
triggers:
  - duplicate
---

# Duplicate
""",
            encoding="utf-8",
        )

    result = skill_installer_tool.disable_skill("duplicate_skill")

    assert result["ok"] is False
    assert result["error"]["code"] == "ambiguous_skill_id"


def test_delete_only_allows_imported_and_generated_can_disable(monkeypatch):
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", static_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", generated_dir)
    imported_skill = static_dir / "imported" / "demo" / "SKILL.md"
    generated_skill = generated_dir / "generated.md"
    imported_skill.parent.mkdir(parents=True)
    generated_dir.mkdir(parents=True)
    imported_skill.write_text(pack_skill_md("Imported Demo", "imported trigger"), encoding="utf-8")
    generated_skill.write_text(
        """---
skill_id: generated_demo
name: Generated Demo
enabled: true
triggers:
  - generated trigger
---

# Generated Demo
""",
        encoding="utf-8",
    )

    imported_id = "demo"
    generated_disable = skill_installer_tool.disable_skill("generated_demo")
    generated_delete = skill_installer_tool.delete_skill("generated_demo")
    imported_delete = skill_installer_tool.delete_skill(imported_id)

    assert generated_disable["ok"] is True
    assert generated_delete["ok"] is False
    assert generated_delete["error"]["code"] == "delete_not_allowed"
    assert imported_delete["ok"] is True
    assert not imported_skill.parent.exists()


def test_skill_lifecycle_api(monkeypatch):
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    imported_dir = static_dir / "imported"
    static_dir.mkdir(parents=True)
    generated_dir.mkdir(parents=True)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", static_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", generated_dir)
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(skill_markdown()))
    client = TestClient(app)

    install_response = client.post("/skills/install", json={"url": "https://example.test/nature-reader.md"})
    skill_id = install_response.json()["skill_id"]
    read_response = client.get(f"/skills/{skill_id}")
    disable_response = client.post(f"/skills/{skill_id}/disable")
    enable_response = client.post(f"/skills/{skill_id}/enable")
    delete_response = client.delete(f"/skills/{skill_id}")

    assert install_response.status_code == 200
    assert read_response.status_code == 200
    assert "content" in read_response.json()
    assert disable_response.status_code == 200
    assert enable_response.status_code == 200
    assert delete_response.status_code == 200
