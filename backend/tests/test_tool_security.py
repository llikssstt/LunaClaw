from tool_system.security import review_manifest


def base_manifest(permissions):
    return {"permissions": permissions}


def test_shell_permission_is_high_risk():
    review = review_manifest(base_manifest({"network": [], "filesystem": "none", "shell": True, "env": [], "timeout_seconds": 10}))

    assert review["risk_level"] == "high"
    assert review["approval_required"] is True


def test_https_network_only_requires_medium_approval():
    review = review_manifest(base_manifest({"network": ["https"], "filesystem": "none", "shell": False, "env": [], "timeout_seconds": 10}))

    assert review["risk_level"] == "medium"
    assert review["approval_required"] is True

