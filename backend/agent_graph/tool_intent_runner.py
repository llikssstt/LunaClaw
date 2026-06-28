from tool_system.sandbox_runner import run_installed_tool
from tools import registry as tool_registry


def run_tool_intent(tool_call):
    tool_call = tool_call or {"name": "none", "arguments": {}}
    name = tool_call.get("name", "none")
    if not name or name == "none":
        return tool_registry.structured_error("none", "missing_tool_intent", "Planner did not select a tool")
    if "." in name:
        tool_id, tool_name = name.split(".", 1)
        return run_installed_tool(tool_id, tool_name, tool_call.get("arguments") or {})
    return tool_registry.execute_tool(tool_call)
