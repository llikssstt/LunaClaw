import os

from agent.env_loader import load_env_file


def runtime_mode():
    load_env_file()
    return os.getenv("AGENT_RUNTIME", "graph").strip().lower() or "graph"


def mock_mode_enabled():
    load_env_file()
    return os.getenv("MOCK_LLM", "true").strip().lower() != "false"

