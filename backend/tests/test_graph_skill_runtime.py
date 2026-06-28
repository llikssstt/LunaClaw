import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from agent.memory_core import MemoryCore
from agent_graph.graph import GraphCore
from agent_graph.nodes.memory_node import memory_node
from agent_graph.nodes.response_node import response_node
from agent_graph.nodes.skill_node import skill_node
from agent_graph.nodes.skill_resource_node import skill_resource_node
from main import app
from tools import skill_installer_tool


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "graph_skill_runtime" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_skill(root, name="Demo Skill", trigger="demo trigger", resource_text="needle resource text"):
    skill_dir = root / "skills" / "imported" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
skill_id: demo_skill
name: {name}
description: Demo skill for graph runtime.
enabled: true
triggers:
  - {trigger}
---

# {name}

## Instructions
- Use resource evidence.
""",
        encoding="utf-8",
    )
    (skill_dir / "guide.md").write_text(f"# Guide\n\n{resource_text}\n", encoding="utf-8")
    (skill_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return skill_dir


def patch_skill_dirs(monkeypatch, tmp_path):
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", static_dir)
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", generated_dir)
    return static_dir, generated_dir


def test_skill_node_matches_static_skill_and_dedupes_evolution(monkeypatch):
    tmp_path = local_tmp_path()
    write_skill(tmp_path, trigger="demo trigger")
    static_dir, generated_dir = patch_skill_dirs(monkeypatch, tmp_path)

    class FakeEvolution:
        def load_active_skills(self, _message):
            return [{"skill_id": "demo_skill", "name": "Duplicate Generated", "enabled": True}]

    state = skill_node(
        {"user_message": "please use demo trigger", "agent_flow": []},
        skill_registry=None,
        evolution_core=FakeEvolution(),
    )

    assert [skill["skill_id"] for skill in state["active_skills"]] == ["demo_skill"]
    assert "Demo Skill" in state["skill_context"]
    assert state["skill_trace"][0]["source"] == "registry"
    assert state["agent_flow"][-1]["agent_name"] == "Skill Agent"


def test_search_skill_resources_hits_text_and_skips_binary(monkeypatch):
    tmp_path = local_tmp_path()
    write_skill(tmp_path, resource_text="needle resource text")
    patch_skill_dirs(monkeypatch, tmp_path)

    result = skill_installer_tool.search_skill_resources("demo_skill", "needle")

    assert result["ok"] is True
    assert result["results"][0]["resource_path"] == "guide.md"
    assert "needle resource text" in result["results"][0]["snippet"]
    assert all(item["resource_path"] != "image.png" for item in result["results"])


def test_skill_resource_node_reads_relevant_resource(monkeypatch):
    tmp_path = local_tmp_path()
    write_skill(tmp_path, trigger="demo trigger", resource_text="needle resource text")
    patch_skill_dirs(monkeypatch, tmp_path)
    state = skill_node({"user_message": "demo trigger needle", "agent_flow": [], "tool_trace": []})

    state = skill_resource_node(state)

    assert state["skill_resource_results"][0]["resource_path"] == "guide.md"
    assert "needle resource text" in state["skill_resource_results"][0]["content"]
    assert [entry["tool_call"]["name"] for entry in state["tool_trace"]] == [
        "search_skill_resources",
        "read_skill_resource",
    ]


def test_memory_node_returns_real_retrieved_memories():
    tmp_path = local_tmp_path()
    memory_core = MemoryCore(storage_dir=tmp_path)
    memory_core.write_memory("needle memory content", category="project", importance=0.9, source="test")

    state = memory_node({"user_message": "needle", "agent_flow": []}, memory_core=memory_core)

    assert state["memory_result"]["memory_action"] == "read"
    assert state["memory_result"]["retrieved_memories"]
    assert "needle memory content" in state["memory_context"]


def test_response_node_uses_skill_resource_results_with_mock_llm():
    class FakeLLM:
        mock_mode = True

    state = response_node(
        {
            "user_message": "answer with resource",
            "agent_flow": [],
            "skill_resource_results": [{"resource_path": "guide.md", "content": "resource backed answer"}],
            "active_skills": [{"skill_id": "demo_skill", "name": "Demo Skill"}],
        },
        llm_client=FakeLLM(),
    )

    assert "resource backed answer" in state["final_reply"]
    assert state["agent_flow"][-1]["agent_name"] == "Response Agent"


def test_chat_returns_skill_trace_and_runtime_fields(monkeypatch):
    tmp_path = local_tmp_path()
    write_skill(tmp_path, trigger="demo trigger", resource_text="needle resource text")
    patch_skill_dirs(monkeypatch, tmp_path)

    result = GraphCore().chat("demo trigger needle", "test")

    assert result["active_skills"]
    assert result["skill_trace"]
    assert result["skill_resource_results"]
    assert "agent_flow" in result
    assert "tool_trace" in result


def test_skill_resource_search_api(monkeypatch):
    tmp_path = local_tmp_path()
    write_skill(tmp_path, resource_text="needle resource text")
    patch_skill_dirs(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/skills/demo_skill/resources/search?query=needle&top_k=5")

    assert response.status_code == 200
    assert response.json()["results"][0]["resource_path"] == "guide.md"
