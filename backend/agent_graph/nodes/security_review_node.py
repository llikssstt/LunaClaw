from pathlib import Path

from agent_graph.nodes.common import flow_step
from tool_system.installer import DEMO_TOOLS_DIR, create_install_approval
from tool_system.manifest import load_manifest
from tool_system.security import review_manifest


def security_review_node(state):
    selected = state.get("selected_tool") or {}
    tool_id = selected.get("tool_id")
    manifest = load_manifest(Path(DEMO_TOOLS_DIR) / tool_id / "manifest.json")
    review = review_manifest(manifest)
    state["security_review"] = review
    state["approval_required"] = review["approval_required"]
    if review["approval_required"]:
        approval = create_install_approval(tool_id, selected.get("install_source", "demo"), selected.get("source_url"), review)
        state["approval_id"] = approval["approval_id"]
        state["route"] = "response"
    else:
        state["approval_id"] = None
        state["route"] = "tool_install"
    state.setdefault("agent_flow", []).append(
        flow_step("Security Review Agent", "review_manifest", reason=f"{tool_id} risk={review['risk_level']}")
    )
    return state
