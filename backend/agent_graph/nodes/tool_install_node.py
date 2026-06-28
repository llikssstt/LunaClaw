from agent_graph.nodes.common import flow_step
from tool_system.installer import install_tool


def tool_install_node(state):
    selected = state.get("selected_tool") or {}
    result = install_tool(selected.get("tool_id"), selected.get("install_source", "demo"), approved=state.get("approved", False))
    state["install_result"] = result
    state["route"] = "response"
    state.setdefault("agent_flow", []).append(flow_step("Tool Install Agent", "install_tool", reason=selected.get("tool_id", "")))
    return state

