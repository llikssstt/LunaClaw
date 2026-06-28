from pathlib import Path
import uuid

from tool_system import installer, registry_store
from tool_system.installer import approve_install, install_tool
from tool_system.manager import ToolManager
from tool_system.sandbox_runner import run_installed_tool


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "tool_installer_contract" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse:
    text = "<html><title>Example</title><body>Hello from web reader.</body></html>"

    def raise_for_status(self):
        return None


def isolate_tool_storage(monkeypatch, tmp_path):
    registry_path = tmp_path / "installed_tools.json"
    approvals_path = tmp_path / "approvals.json"
    installed_dir = tmp_path / "installed_tool_packages"
    monkeypatch.setattr(registry_store, "DEFAULT_REGISTRY_PATH", registry_path)
    monkeypatch.setattr(installer, "APPROVALS_PATH", approvals_path)
    monkeypatch.setattr(installer, "INSTALLED_TOOLS_DIR", installed_dir)
    return registry_path


def test_unapproved_medium_risk_tool_returns_approval(monkeypatch):
    tmp_path = local_tmp_path()
    isolate_tool_storage(monkeypatch, tmp_path)

    result = install_tool("web_reader", "market")

    assert result["ok"] is True
    assert result["approval_required"] is True
    assert result["approval_id"].startswith("approval_")
    assert ToolManager().list_installed_tools() == []


def test_approval_installs_demo_tool_and_lists_it(monkeypatch):
    tmp_path = local_tmp_path()
    isolate_tool_storage(monkeypatch, tmp_path)
    pending = install_tool("web_reader", "market")

    result = approve_install(pending["approval_id"], True)

    assert result["ok"] is True
    installed = ToolManager().list_installed_tools()
    assert installed[0]["tool_id"] == "web_reader"
    assert installed[0]["enabled"] is True
    assert [step["agent_name"] for step in result["agent_flow"]] == ["User Approval", "Tool Install Agent"]


def test_installed_web_reader_executes_and_writes_result(monkeypatch):
    tmp_path = local_tmp_path()
    isolate_tool_storage(monkeypatch, tmp_path)
    pending = install_tool("web_reader", "market")
    approve_install(pending["approval_id"], True)
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse())

    result = run_installed_tool("web_reader", "fetch_page", {"url": "https://example.com"})

    assert result["ok"] is True
    assert result["tool"] == "web_reader.fetch_page"
    assert result["result"]["title"] == "Example"


def test_internal_tool_ok_false_propagates_to_outer_error(monkeypatch):
    tmp_path = local_tmp_path()
    isolate_tool_storage(monkeypatch, tmp_path)
    pending = install_tool("web_reader", "market")
    approve_install(pending["approval_id"], True)

    result = run_installed_tool("web_reader", "missing_tool", {"url": "https://example.com"})

    assert result["ok"] is False
    assert result["tool"] == "web_reader.missing_tool"
    assert result["error"]["code"] == "unknown_tool"
