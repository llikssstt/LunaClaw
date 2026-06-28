import uuid
from pathlib import Path

from agent_graph.graph import GraphCore
from agent_graph import uploads
from tool_system import installer, registry_store
from tool_system.installer import approve_install, install_tool


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "agent_graph_contract" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def isolate_tool_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(registry_store, "DEFAULT_REGISTRY_PATH", tmp_path / "installed_tools.json")
    monkeypatch.setattr(installer, "APPROVALS_PATH", tmp_path / "approvals.json")
    monkeypatch.setattr(installer, "INSTALLED_TOOLS_DIR", tmp_path / "installed_tool_packages")


class FakeResponse:
    text = "<html><title>Example</title><body>Hello graph execution.</body></html>"

    def raise_for_status(self):
        return None


def test_graph_chat_returns_compatible_fields_and_uses_langgraph():
    core = GraphCore()
    result = core.chat("hello", "test")

    for key in ["reply", "emotion", "tool_used", "tool_trace", "sources", "agent_flow", "active_skills"]:
        assert key in result
    assert result["agent_flow"][0]["agent_name"] == "Supervisor Agent"
    assert hasattr(core.graph, "invoke")
    assert core.graph.__class__.__name__ == "CompiledStateGraph"


def test_install_request_routes_to_tool_search_and_security(monkeypatch):
    tmp_path = local_tmp_path()
    isolate_tool_storage(monkeypatch, tmp_path)

    result = GraphCore().chat("install a tool that can read web pages", "test")

    assert result["approval_required"] is True
    assert result["approval_id"].startswith("approval_")
    assert any(step["agent_name"] == "Tool Search Agent" for step in result["agent_flow"])
    assert any(step["agent_name"] == "Security Review Agent" for step in result["agent_flow"])


def test_installed_tool_execution_adds_tool_trace(monkeypatch):
    tmp_path = local_tmp_path()
    isolate_tool_storage(monkeypatch, tmp_path)
    pending = install_tool("web_reader", "market")
    approve_install(pending["approval_id"], True)
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse())

    result = GraphCore().chat("use web_reader to summarize this page: https://example.com", "test")

    assert result["tool_used"] == "web_reader.fetch_page"
    assert result["tool_trace"][0]["tool_call"]["name"] == "web_reader.fetch_page"
    assert result["sources"][0]["url"] == "https://example.com"


def test_image_attachment_goes_through_multimodal_node(monkeypatch):
    tmp_path = local_tmp_path()
    image_path = tmp_path / "shot.png"
    image_path.write_bytes(b"fake image")
    monkeypatch.setattr(uploads, "DEFAULT_UPLOADS_INDEX_PATH", tmp_path / "uploads_index.json")
    uploads.register_upload(
        {
            "file_id": "img_1",
            "filename": "shot.png",
            "content_type": "image/png",
            "size": image_path.stat().st_size,
            "path": str(image_path),
            "type": "image",
        }
    )

    result = GraphCore().chat(
        "analyze this uploaded image",
        "test",
        attachments=[{"type": "image", "file_id": "img_1", "filename": "shot.png"}],
    )

    assert any(step["agent_name"] == "Multimodal Agent" for step in result["agent_flow"])
    assert "shot.png" in result["reply"]
