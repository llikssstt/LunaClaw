import re

from agent_graph.nodes.common import flow_step
from tool_system.sandbox_runner import run_installed_tool


def execution_node(state):
    message = state.get("user_message", "")
    url_match = re.search(r"https?://\S+", message)
    tool_id = "web_reader"
    tool_name = "fetch_page"
    arguments = {"url": url_match.group(0).rstrip("。.,)") if url_match else ""}
    result = run_installed_tool(tool_id, tool_name, arguments)
    trace = {
        "step": len(state.get("tool_trace", [])) + 1,
        "agent_name": "Execution Agent",
        "tool_call": {"name": f"{tool_id}.{tool_name}", "arguments": arguments},
        "tool_result": result,
    }
    state.setdefault("tool_trace", []).append(trace)
    state["execution_result"] = result
    if result.get("ok") and isinstance(result.get("result"), dict):
        fetched = result["result"]
        state["sources"] = [{"title": fetched.get("title"), "url": fetched.get("url"), "snippet": fetched.get("content", "")[:240], "source": tool_id}]
    state["route"] = "response"
    state.setdefault("agent_flow", []).append(flow_step("Execution Agent", "run_tool", status="ok" if result.get("ok") else "error", reason=tool_id))
    return state

