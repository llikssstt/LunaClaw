import uuid
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from agent.skill_registry import SkillRegistry
from main import app
from tools import skill_installer_tool
from tools.registry import execute_tool, get_tool_names


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "skill_resources_contract" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def pack_skill_md():
    return """---
skill_id: nature_reader
name: Nature Reader
description: Read paper resources.
enabled: true
triggers:
  - reader trigger
---

# Nature Reader

## Instructions
- Use resources when relevant.
"""


def build_pack_zip():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pack-main/skills/nature-reader/SKILL.md", pack_skill_md())
        archive.writestr("pack-main/skills/nature-reader/references/guide.md", "# Guide\n\nResource note.")
        archive.writestr("pack-main/skills/nature-reader/static/icon.png", b"\x89PNG\r\n\x1a\n\x00\x00binary")
        archive.writestr("pack-main/skills/nature-reader/bin/tool.exe", b"MZnot allowed")
    return buffer.getvalue()


def install_pack(monkeypatch):
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    imported_dir = static_dir / "imported"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", static_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", generated_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_IMPORTED_SKILLS_DIR", imported_dir)
    monkeypatch.setattr(skill_installer_tool.requests, "get", lambda *args, **kwargs: FakeResponse(build_pack_zip()))
    result = skill_installer_tool.install_skill_pack("https://github.com/acme/pack", pack_id="demo_pack")
    return tmp_path, result


def test_build_context_includes_root_dir_and_available_resources(monkeypatch):
    tmp_path, result = install_pack(monkeypatch)
    registry = SkillRegistry(static_dir=tmp_path / "skills", generated_dir=tmp_path / "generated_skills")
    skill = registry.match("reader trigger")[0]

    context = registry.build_context([skill])

    assert "Root dir:" in context
    assert "Available resources:" in context
    assert "- references/guide.md" in context
    assert "- static/icon.png" in context


def test_list_skill_resources_returns_resources(monkeypatch):
    _tmp_path, result = install_pack(monkeypatch)
    skill_id = result["installed_skills"][0]["skill_id"]

    resources = skill_installer_tool.list_skill_resources(skill_id)

    assert resources["ok"] is True
    assert "references/guide.md" in resources["resources"]
    assert "static/icon.png" in resources["resources"]


def test_read_skill_resource_reads_text(monkeypatch):
    _tmp_path, result = install_pack(monkeypatch)
    skill_id = result["installed_skills"][0]["skill_id"]

    resource = skill_installer_tool.read_skill_resource(skill_id, "references/guide.md")

    assert resource["ok"] is True
    assert resource["resource_path"] == "references/guide.md"
    assert "Resource note." in resource["content"]
    assert resource["truncated"] is False


def test_read_skill_resource_blocks_path_escape(monkeypatch):
    _tmp_path, result = install_pack(monkeypatch)
    skill_id = result["installed_skills"][0]["skill_id"]

    resource = skill_installer_tool.read_skill_resource(skill_id, "../SKILL.md")

    assert resource["ok"] is False
    assert resource["error"]["code"] == "invalid_resource_path"


def test_read_skill_resource_returns_unsupported_binary(monkeypatch):
    _tmp_path, result = install_pack(monkeypatch)
    skill_id = result["installed_skills"][0]["skill_id"]

    resource = skill_installer_tool.read_skill_resource(skill_id, "static/icon.png")

    assert resource["ok"] is False
    assert resource["error"]["code"] == "unsupported_binary"
    assert resource["metadata"]["size"] > 0


def test_zipball_install_skips_disallowed_file_types(monkeypatch):
    _tmp_path, result = install_pack(monkeypatch)

    assert result["ok"] is True
    assert any(error["code"] == "unsupported_extension" for error in result["errors"])
    assert all("bin/tool.exe" not in skill.get("path", "") for skill in result["installed_skills"])
    assert not (skill_installer_tool.DEFAULT_IMPORTED_SKILLS_DIR / "demo_pack" / "skills" / "nature-reader" / "bin" / "tool.exe").exists()


def test_resource_tools_are_registered_and_api_can_read(monkeypatch):
    _tmp_path, result = install_pack(monkeypatch)
    skill_id = result["installed_skills"][0]["skill_id"]
    client = TestClient(app)

    tool_names = get_tool_names()
    tool_result = execute_tool({"name": "read_skill_resource", "arguments": {"skill_id": skill_id, "resource_path": "references/guide.md"}})
    list_response = client.get(f"/skills/{skill_id}/resources")
    read_response = client.get(f"/skills/{skill_id}/resources/references/guide.md")

    assert "list_skill_resources" in tool_names
    assert "read_skill_resource" in tool_names
    assert tool_result["ok"] is True
    assert list_response.status_code == 200
    assert read_response.status_code == 200
    assert "Resource note." in read_response.json()["content"]
