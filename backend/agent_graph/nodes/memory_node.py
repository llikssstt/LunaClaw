from agent.memory_core import MemoryCore
from agent_graph.nodes.common import flow_step


def memory_node(state, memory_core=None):
    core = memory_core or MemoryCore()
    message = state.get("user_message", "")
    try:
        rag_result = core.retriever.retrieve(message)
        memories = rag_result.get("memories", []) or []
        state["memory_result"] = {
            "ok": True,
            "memory_action": "read",
            "retrieved_memories": memories,
            "profile": rag_result.get("profile", {}),
            "conversation_hits": rag_result.get("conversation_hits", []),
        }
        state["memory_context"] = _memory_context(memories)
        status = "ok"
        reason = f"{len(memories)} memory item(s) retrieved"
    except Exception as exc:
        state["memory_result"] = {"ok": False, "memory_action": "read", "retrieved_memories": [], "error": str(exc)}
        state["memory_context"] = ""
        status = "error"
        reason = str(exc)
    state.setdefault("agent_flow", []).append(flow_step("Memory Agent", "memory_context", status=status, reason=reason))
    return state


def _memory_context(memories):
    lines = []
    for item in memories[:5]:
        content = item.get("content", "")
        if content:
            lines.append(f"- {item.get('category', 'memory')}: {content}")
    return "\n".join(lines)
