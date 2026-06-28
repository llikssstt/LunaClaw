import json
from pathlib import Path


REQUIRED_FIELDS = {"tool_id", "name", "version", "description", "runtime", "entry", "transport", "permissions", "tools"}
PERMISSION_FIELDS = {"network", "filesystem", "shell", "env", "timeout_seconds"}
FILESYSTEM_VALUES = {"none", "read", "write"}


def load_manifest(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_manifest(data, path.parent)


def validate_manifest(manifest, tool_dir):
    missing = sorted(REQUIRED_FIELDS - set(manifest))
    if missing:
        raise ValueError(f"manifest missing fields: {', '.join(missing)}")
    permissions = manifest.get("permissions")
    if not isinstance(permissions, dict):
        raise ValueError("manifest permissions must be an object")
    unknown_permissions = sorted(set(permissions) - PERMISSION_FIELDS)
    if unknown_permissions:
        raise ValueError(f"unknown permission fields: {', '.join(unknown_permissions)}")
    filesystem = permissions.get("filesystem", "none")
    if filesystem not in FILESYSTEM_VALUES:
        raise ValueError(f"invalid filesystem permission: {filesystem}")
    if not isinstance(permissions.get("shell", False), bool):
        raise ValueError("permissions.shell must be boolean")
    entry = str(manifest.get("entry") or "")
    if not entry or Path(entry).is_absolute() or ".." in Path(entry).parts:
        raise ValueError("manifest entry must be a relative path inside the tool directory")
    entry_path = (Path(tool_dir) / entry).resolve()
    try:
        entry_path.relative_to(Path(tool_dir).resolve())
    except ValueError as exc:
        raise ValueError("manifest entry escapes tool directory") from exc
    if not isinstance(manifest.get("tools"), list) or not manifest["tools"]:
        raise ValueError("manifest tools must be a non-empty list")
    return manifest


def manifest_sha256(path):
    import hashlib

    path = Path(path)
    digest = hashlib.sha256()
    for file_path in sorted(path.rglob("*")):
        if file_path.is_file():
            digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
            digest.update(file_path.read_bytes())
    return digest.hexdigest()

