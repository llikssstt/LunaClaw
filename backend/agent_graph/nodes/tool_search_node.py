from agent_graph.nodes.common import flow_step
from tool_system.manager import ToolManager


def tool_search_node(state):
    manager = ToolManager()
    candidates = manager.search_tools(state.get("user_message", ""))
    state["candidate_tools"] = candidates
    if candidates:
        state["selected_tool"] = candidates[0]
        installed = manager.get_tool(candidates[0].get("tool_id"))
        state["route"] = "execute_tool" if installed and installed.get("enabled", True) else "security_review"
        reason = f"selected {candidates[0].get('tool_id')}"
    else:
        state["route"] = "response"
        reason = "no matching tool found"
    state.setdefault("agent_flow", []).append(flow_step("Tool Search Agent", "search_tools", reason=reason))
    return state

