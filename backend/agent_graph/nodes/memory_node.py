from agent_graph.nodes.common import flow_step


def memory_node(state):
    state["memory_result"] = {"retrieved_memories": [], "memory_action": "none"}
    state.setdefault("agent_flow", []).append(flow_step("Memory Agent", "memory_context", reason="non-blocking memory pass"))
    return state

