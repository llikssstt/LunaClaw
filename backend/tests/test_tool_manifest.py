from pathlib import Path
import uuid

import pytest

from tool_system.manifest import load_manifest, validate_manifest


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "tool_manifest_contract" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_web_reader_manifest_validates():
    manifest_path = Path(__file__).resolve().parents[1] / "tool_market" / "demo_tools" / "web_reader" / "manifest.json"

    manifest = load_manifest(manifest_path)

    assert manifest["tool_id"] == "web_reader"
    assert manifest["entry"] == "tool_impl.py"


def test_manifest_rejects_entry_path_escape():
    tmp_path = local_tmp_path()
    manifest = {
        "tool_id": "bad",
        "name": "Bad",
        "version": "0.1.0",
        "description": "bad",
        "runtime": "python",
        "entry": "../bad.py",
        "transport": "local_function",
        "permissions": {"network": [], "filesystem": "none", "shell": False, "env": [], "timeout_seconds": 10},
        "tools": [{"name": "bad", "input_schema": {}}],
    }

    with pytest.raises(ValueError, match="relative path"):
        validate_manifest(manifest, tmp_path)
