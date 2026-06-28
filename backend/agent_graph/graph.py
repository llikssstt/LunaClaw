from agent_graph.nodes.execution_node import execution_node
from agent_graph.nodes.memory_node import memory_node
from agent_graph.nodes.multimodal_node import multimodal_node
from agent_graph.nodes.response_node import response_node
from agent_graph.nodes.security_review_node import security_review_node
from agent_graph.nodes.supervisor_node import supervisor_node
from agent_graph.nodes.tool_search_node import tool_search_node


class GraphCore:
    def chat(self, message: str, session_id: str = "default", attachments=None) -> dict:
        state = {
            "session_id": session_id,
            "user_message": message,
            "input_type": "multimodal" if attachments else "text",
            "attachments": attachments or [],
            "tool_trace": [],
            "agent_flow": [],
            "sources": [],
        }
        state = supervisor_node(state)
        state = memory_node(state)
        if state.get("route") == "multimodal":
            state = multimodal_node(state)
        if state.get("route") == "tool_search":
            state = tool_search_node(state)
        if state.get("route") == "security_review":
            state = security_review_node(state)
        if state.get("route") == "execute_tool":
            state = execution_node(state)
        state = response_node(state)
        return self._response(state)

    def _response(self, state):
        execution_tool = "none"
        if state.get("tool_trace"):
            execution_tool = state["tool_trace"][-1].get("tool_call", {}).get("name", "none")
        return {
            "reply": state.get("final_reply", ""),
            "emotion": state.get("emotion", "thinking"),
            "tool_used": execution_tool,
            "skills_used": [],
            "memory_action": (state.get("memory_result") or {}).get("memory_action", "none"),
            "retrieved_memories": (state.get("memory_result") or {}).get("retrieved_memories", []),
            "evolution_events": [],
            "active_skills": [],
            "evolution_summary": "",
            "tool_trace": state.get("tool_trace", []),
            "sources": state.get("sources", []),
            "agent_flow": state.get("agent_flow", []),
            "approval_required": state.get("approval_required", False),
            "approval_id": state.get("approval_id"),
            "security_review": state.get("security_review", {}),
            "candidate_tools": state.get("candidate_tools", []),
        }

