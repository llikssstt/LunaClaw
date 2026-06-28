from agent_graph.nodes.common import flow_step
from agent_graph.task_runtime import TaskRuntime
from agent_graph.tool_intent_runner import run_tool_intent


def execution_node(state):
    tool_call = state.get("tool_intent") or {"name": "none", "arguments": {}}
    result = run_tool_intent(tool_call)

    trace = {
        "step": len(state.get("tool_trace", [])) + 1,
        "agent_name": "Execution Agent",
        "tool_call": tool_call,
        "tool_result": result,
    }
    state.setdefault("tool_trace", []).append(trace)
    state["execution_result"] = result
    _extract_sources(state, tool_call, result)
    _record_task_artifact(state, result)
    state["route"] = "response"
    state.setdefault("agent_flow", []).append(
        flow_step("Execution Agent", "run_tool", status="ok" if result.get("ok") else "error", reason=tool_call.get("name", "none"))
    )
    return state


def _extract_sources(state, tool_call, result):
    payload = result.get("result") if isinstance(result, dict) else None
    if not result.get("ok") or not isinstance(payload, dict):
        return
    tool_name = tool_call.get("name", "")
    if tool_name in {"web_fetch", "web_reader.fetch_page"}:
        state["sources"] = [
            {
                "title": payload.get("title"),
                "url": payload.get("url") or (tool_call.get("arguments") or {}).get("url"),
                "snippet": payload.get("content", "")[:240],
                "source": tool_name,
            }
        ]
    elif tool_name == "web_search":
        state["sources"] = [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("snippet", ""),
                "source": "web_search",
            }
            for item in payload.get("results", [])[:5]
        ]


def _record_task_artifact(state, result):
    task = state.get("task") or {}
    task_id = task.get("task_id")
    if not task_id:
        return
    runtime = TaskRuntime()
    runtime.add_artifact(task_id, "tool_result", {"ok": result.get("ok"), "tool": result.get("tool"), "result": result.get("result")})
    task = runtime.finish_task(task_id, "completed" if result.get("ok") else "failed")
    state["task"] = task
