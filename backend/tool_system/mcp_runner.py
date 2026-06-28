def run_mcp_tool(*_args, **_kwargs):
    return {"ok": False, "error": {"code": "mcp_not_enabled", "message": "MCP runner is reserved for a later phase"}}
