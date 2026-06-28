import json
from pathlib import Path

from tools.registry import AVAILABLE_TOOLS
from tool_system.registry_store import ToolRegistryStore


DEFAULT_TOOL_MARKET_INDEX = Path(__file__).resolve().parents[1] / "tool_market" / "tools_index.json"


class ToolManager:
    def __init__(self, registry=None, market_index=DEFAULT_TOOL_MARKET_INDEX):
        self.registry = registry or ToolRegistryStore()
        self.market_index = Path(market_index)

    def list_builtin_tools(self):
        return [{"tool_id": item["name"], "source": "built_in", **item} for item in AVAILABLE_TOOLS]

    def list_market_tools(self):
        if not self.market_index.exists():
            return []
        data = json.loads(self.market_index.read_text(encoding="utf-8"))
        return data.get("tools", [])

    def list_installed_tools(self):
        return self.registry.list()

    def list_available_tools(self):
        return {
            "built_in": self.list_builtin_tools(),
            "market": self.list_market_tools(),
            "installed": self.list_installed_tools(),
        }

    def search_tools(self, query):
        text = str(query or "").lower()
        candidates = []
        for tool in self.list_market_tools() + self.list_installed_tools():
            haystack = " ".join(str(tool.get(key, "")) for key in ["tool_id", "name", "description"]).lower()
            if not text or any(token in haystack for token in text.split()):
                candidates.append(tool)
        if any(word in text for word in ["网页", "web", "url", "读取", "reader", "fetch"]):
            if not any(item.get("tool_id") == "web_reader" for item in candidates):
                web_reader = next((tool for tool in self.list_market_tools() if tool.get("tool_id") == "web_reader"), None)
                if web_reader:
                    candidates.insert(0, web_reader)
            candidates = sorted(candidates, key=lambda item: 0 if item.get("tool_id") == "web_reader" else 1)
        return candidates

    def get_tool(self, tool_id):
        return self.registry.get(tool_id)

    def enable_tool(self, tool_id):
        return self.registry.set_enabled(tool_id, True)

    def disable_tool(self, tool_id):
        return self.registry.set_enabled(tool_id, False)
