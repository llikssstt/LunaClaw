import re

from agent_graph.nodes.common import flow_step
from agent_graph.task_runtime import TaskRuntime


def planner_node(state):
    message = state.get("user_message", "")
    planner_result = _plan(message, state)
    state["planner_result"] = planner_result
    state["tool_intent"] = planner_result.get("tool_intent", {"name": "none", "arguments": {}})
    state["route"] = planner_result.get("route", state.get("route", "response"))
    state["current_task"] = planner_result.get("task_title", message)

    runtime = TaskRuntime()
    task = state.get("task") or runtime.create_task(state["current_task"], state.get("session_id", "default"))
    task = runtime.set_plan(task["task_id"], planner_result.get("steps", []), state["tool_intent"])
    state["task"] = task
    state["task_id"] = task["task_id"]
    state.setdefault("agent_flow", []).append(
        flow_step("Planner Agent", f"plan:{state['route']}", reason=planner_result.get("reason", "structured plan"))
    )
    return state


def _plan(message, state):
    if state.get("route") == "multimodal":
        return _result("Analyze uploaded image", "multimodal", "image attachment detected", [{"title": "Analyze image input"}])
    lower = str(message or "").lower()
    expression = _extract_expression(message)
    if expression:
        return _result(
            "Calculate expression",
            "execute_tool",
            "calculation request",
            [{"title": "Parse expression"}, {"title": "Run calculator"}, {"title": "Explain result"}],
            {"name": "calculator", "arguments": {"expression": expression}},
        )
    if "web_reader" in lower:
        url_match = re.search(r"https?://\S+", message)
        return _result(
            "Read web page with web_reader",
            "execute_tool",
            "explicit installed web_reader request",
            [{"title": "Extract URL"}, {"title": "Run web_reader"}, {"title": "Summarize result"}],
            {"name": "web_reader.fetch_page", "arguments": {"url": url_match.group(0).rstrip(".,)") if url_match else ""}},
        )
    if re.search(r"https?://", message):
        url_match = re.search(r"https?://\S+", message)
        return _result(
            "Read web page",
            "execute_tool",
            "URL/tool execution request",
            [{"title": "Extract URL"}, {"title": "Run web fetch tool"}, {"title": "Summarize result"}],
            {"name": "web_fetch", "arguments": {"url": url_match.group(0).rstrip(".,)") if url_match else ""}},
        )
    if state.get("route") == "tool_search":
        return _result("Find installable tool", "tool_search", "tool discovery request", [{"title": "Search tool market"}, {"title": "Review permissions"}])
    return _result("Answer user request", "response", "no tool required", [{"title": "Review context"}, {"title": "Compose response"}])


def _result(task_title, route, reason, steps, tool_intent=None):
    return {
        "task_title": task_title,
        "route": route,
        "reason": reason,
        "steps": steps,
        "tool_intent": tool_intent or {"name": "none", "arguments": {}},
    }


def _extract_expression(message):
    matches = re.findall(r"[0-9][0-9\.\s\+\-\*\/\(\)]{1,}[0-9\)]", str(message or ""))
    return matches[0].strip() if matches else ""
