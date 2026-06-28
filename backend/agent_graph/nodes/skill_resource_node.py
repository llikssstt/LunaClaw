from agent_graph.nodes.common import flow_step
from tools.skill_installer_tool import read_skill_resource, search_skill_resources


MIN_RESOURCE_SCORE = 1


def skill_resource_node(state):
    message = state.get("user_message", "")
    results = []
    tool_trace = state.setdefault("tool_trace", [])
    for skill in state.get("active_skills", []) or []:
        skill_id = skill.get("skill_id")
        if not skill_id or not skill.get("resources"):
            continue
        search_result = search_skill_resources(skill_id, message, top_k=3)
        tool_trace.append(
            {
                "step": len(tool_trace) + 1,
                "agent_name": "Skill Resource Agent",
                "tool_call": {"name": "search_skill_resources", "arguments": {"skill_id": skill_id, "query": message, "top_k": 3}},
                "tool_result": search_result,
            }
        )
        if not search_result.get("ok"):
            continue
        for hit in search_result.get("results", []):
            if hit.get("score", 0) < MIN_RESOURCE_SCORE:
                continue
            read_result = read_skill_resource(skill_id, hit["resource_path"], max_chars=4000)
            tool_trace.append(
                {
                    "step": len(tool_trace) + 1,
                    "agent_name": "Skill Resource Agent",
                    "tool_call": {"name": "read_skill_resource", "arguments": {"skill_id": skill_id, "resource_path": hit["resource_path"]}},
                    "tool_result": read_result,
                }
            )
            if read_result.get("ok"):
                results.append(
                    {
                        "skill_id": skill_id,
                        "skill_name": skill.get("name"),
                        "resource_path": read_result["resource_path"],
                        "content": read_result["content"],
                        "truncated": read_result["truncated"],
                        "score": hit.get("score", 0),
                        "metadata": read_result.get("metadata", {}),
                    }
                )
            break

    state["skill_resource_results"] = results
    state.setdefault("agent_flow", []).append(
        flow_step("Skill Resource Agent", "read_relevant_resources", reason=f"{len(results)} resource(s) loaded")
    )
    return state
