import importlib.util
import time
from pathlib import Path

from tool_system.registry_store import ToolRegistryStore


ALLOWED_LOCAL_TOOLS = {"web_reader"}
MAX_OUTPUT_CHARS = 12000


def run_installed_tool(tool_id, tool_name, arguments):
    started = time.time()
    tool = ToolRegistryStore().get(tool_id)
    if not tool:
        return _error(tool_id, "tool_not_installed", "tool is not installed")
    if not tool.get("enabled", True):
        return _error(tool_id, "tool_disabled", "tool is disabled")
    if tool_id not in ALLOWED_LOCAL_TOOLS:
        return _error(tool_id, "execution_not_allowed", "only whitelisted demo tools can execute in this MVP")
    try:
        module = _load_tool_module(Path(tool["path"]) / "tool_impl.py", tool_id)
        result = module.run(tool_name, arguments or {})
    except Exception as exc:
        return _error(tool_id, "execution_failed", str(exc))
    if isinstance(result, dict) and result.get("ok") is False:
        return {
            "ok": False,
            "tool": f"{tool_id}.{tool_name}",
            "error": result.get("error") or {"code": "tool_returned_error", "message": "tool returned ok=false"},
            "result": result,
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    text = str(result)
    if len(text) > MAX_OUTPUT_CHARS:
        result = {"truncated": True, "content": text[:MAX_OUTPUT_CHARS]}
    return {"ok": True, "tool": f"{tool_id}.{tool_name}", "result": result, "elapsed_ms": int((time.time() - started) * 1000)}


def _load_tool_module(path, tool_id):
    spec = importlib.util.spec_from_file_location(f"vagent_tool_{tool_id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _error(tool, code, message):
    return {"ok": False, "tool": tool, "error": {"code": code, "message": message}}
