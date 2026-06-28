SENSITIVE_ENV_MARKERS = ("API_KEY", "TOKEN", "SECRET", "PRIVATE_KEY", "PASSWORD")


def review_manifest(manifest):
    permissions = manifest.get("permissions") or {}
    reasons = []
    risk = "low"

    filesystem = permissions.get("filesystem", "none")
    shell = bool(permissions.get("shell", False))
    env = [str(item) for item in permissions.get("env", [])]
    network = permissions.get("network", [])

    if shell:
        risk = "high"
        reasons.append("shell execution requested")
    if filesystem == "write":
        risk = "high"
        reasons.append("filesystem write requested")
    elif filesystem == "read" and risk != "high":
        risk = "medium"
        reasons.append("filesystem read requested")
    if any(any(marker in item.upper() for marker in SENSITIVE_ENV_MARKERS) for item in env):
        risk = "high"
        reasons.append("sensitive environment variable requested")
    if network and risk == "low":
        if set(network).issubset({"https"}):
            risk = "medium"
            reasons.append("https network access requested")
        else:
            risk = "high"
            reasons.append("broad network access requested")

    approval_required = risk in {"medium", "high"}
    return {
        "allowed": True,
        "risk_level": risk,
        "approval_required": approval_required,
        "permissions": permissions,
        "reason": "; ".join(reasons) or "no elevated permissions requested",
    }

