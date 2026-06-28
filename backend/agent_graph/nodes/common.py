from datetime import datetime, timezone


def flow_step(agent_name, action, status="ok", reason=""):
    return {
        "agent_name": agent_name,
        "action": action,
        "status": status,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

