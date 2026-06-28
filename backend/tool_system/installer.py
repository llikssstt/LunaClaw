import json
import shutil
import uuid
from pathlib import Path

from agent_graph.nodes.common import flow_step
from tool_system.manifest import load_manifest, manifest_sha256
from tool_system.registry_store import ToolRegistryStore
from tool_system.security import review_manifest


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEMO_TOOLS_DIR = BACKEND_DIR / "tool_market" / "demo_tools"
INSTALLED_TOOLS_DIR = BACKEND_DIR / "storage" / "installed_tool_packages"
APPROVALS_PATH = BACKEND_DIR / "storage" / "tool_approvals.json"
ALLOWED_EXTENSIONS = {".json", ".md", ".py", ".txt"}
MAX_PACKAGE_FILES = 100
MAX_FILE_BYTES = 2 * 1024 * 1024


def install_tool(tool_id, source="market", approved=False, source_url=None):
    source_dir = _resolve_source_dir(tool_id, source)
    manifest = load_manifest(source_dir / "manifest.json")
    review = review_manifest(manifest)
    if review["approval_required"] and not approved:
        approval = create_install_approval(tool_id, source, source_url, review)
        return {"ok": True, "approval_required": True, "approval_id": approval["approval_id"], "security_review": review}
    result = _install_from_dir(source_dir, manifest, review, source, source_url)
    return {"ok": True, "approval_required": False, "install_result": result, "security_review": review}


def approve_install(approval_id, approved):
    approvals = _read_approvals()
    approval = approvals.get(approval_id)
    if not approval:
        return {"ok": False, "error": {"code": "approval_not_found", "message": "approval not found"}}
    approval["approved"] = bool(approved)
    if not approved:
        approval["status"] = "rejected"
        _write_approvals(approvals)
        return {
            "ok": True,
            "approved": False,
            "install_result": None,
            "agent_flow": [flow_step("User Approval", "reject_tool_install", status="rejected", reason=approval["tool_id"])],
        }
    result = install_tool(approval["tool_id"], approval.get("source", "market"), approved=True, source_url=approval.get("source_url"))
    approval["status"] = "approved"
    _write_approvals(approvals)
    return {
        "ok": True,
        "approved": True,
        **result,
        "agent_flow": [
            flow_step("User Approval", "approve_tool_install", reason=approval["tool_id"]),
            flow_step("Tool Install Agent", "install_tool", reason=approval["tool_id"]),
        ],
    }


def create_install_approval(tool_id, source, source_url, review):
    approvals = _read_approvals()
    approval_id = f"approval_{uuid.uuid4().hex[:12]}"
    approval = {
        "approval_id": approval_id,
        "tool_id": tool_id,
        "source": source,
        "source_url": source_url,
        "security_review": review,
        "status": "pending",
    }
    approvals[approval_id] = approval
    _write_approvals(approvals)
    return approval


def _install_from_dir(source_dir, manifest, review, source, source_url):
    _validate_package_files(source_dir)
    target_dir = INSTALLED_TOOLS_DIR / manifest["tool_id"]
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    enabled = review["risk_level"] != "high"
    tool = {
        "tool_id": manifest["tool_id"],
        "name": manifest["name"],
        "version": manifest["version"],
        "description": manifest["description"],
        "path": str(target_dir),
        "enabled": enabled,
        "permissions": manifest["permissions"],
        "tools": manifest["tools"],
        "source": source,
        "source_url": source_url,
        "sha256": manifest_sha256(target_dir),
    }
    ToolRegistryStore().upsert(tool)
    return tool


def _resolve_source_dir(tool_id, source):
    if source not in {"market", "demo"}:
        raise ValueError("only local market/demo tool install is enabled in this MVP")
    source_dir = (DEMO_TOOLS_DIR / tool_id).resolve()
    try:
        source_dir.relative_to(DEMO_TOOLS_DIR.resolve())
    except ValueError as exc:
        raise ValueError("invalid tool_id") from exc
    if not source_dir.exists():
        raise ValueError(f"tool not found: {tool_id}")
    return source_dir


def _validate_package_files(source_dir):
    files = [path for path in Path(source_dir).rglob("*") if path.is_file()]
    if len(files) > MAX_PACKAGE_FILES:
        raise ValueError("tool package has too many files")
    for path in files:
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError(f"unsupported tool package file extension: {path.name}")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"tool package file too large: {path.name}")


def _read_approvals():
    if not APPROVALS_PATH.exists():
        return {}
    try:
        return json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_approvals(data):
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
