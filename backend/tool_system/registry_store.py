import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "storage" / "installed_tools.json"


class ToolRegistryStore:
    def __init__(self, path=None):
        self.path = Path(path or DEFAULT_REGISTRY_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self):
        return self._read().get("tools", [])

    def get(self, tool_id):
        return next((tool for tool in self.list() if tool.get("tool_id") == tool_id), None)

    def upsert(self, tool):
        data = self._read()
        tools = [item for item in data.get("tools", []) if item.get("tool_id") != tool.get("tool_id")]
        tool = {**tool, "installed_at": tool.get("installed_at") or datetime.now(timezone.utc).isoformat()}
        tools.append(tool)
        data["tools"] = sorted(tools, key=lambda item: item.get("tool_id", ""))
        self._write(data)
        return tool

    def set_enabled(self, tool_id, enabled):
        data = self._read()
        for tool in data.get("tools", []):
            if tool.get("tool_id") == tool_id:
                tool["enabled"] = bool(enabled)
                self._write(data)
                return tool
        raise KeyError(tool_id)

    def _read(self):
        if not self.path.exists():
            return {"tools": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"tools": []}

    def _write(self, data):
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
