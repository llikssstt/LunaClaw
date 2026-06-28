import re

from agent_graph.nodes.common import flow_step


def supervisor_node(state):
    message = state.get("user_message", "")
    lower = message.lower()
    route = "response"
    reason = "general response"
    if any(item.get("type") == "image" for item in state.get("attachments", [])):
        route = "multimodal"
        reason = "image attachment detected"
    elif any(token in lower for token in ["安装", "找工具", "需要一个能", "install tool", "tool"]):
        route = "tool_search"
        reason = "tool discovery or install requested"
    elif "web_reader" in lower or re.search(r"https?://", message):
        route = "execute_tool"
        reason = "installed tool execution requested"
    state["route"] = route
    state.setdefault("agent_flow", []).append(flow_step("Supervisor Agent", f"route:{route}", reason=reason))
    return state

