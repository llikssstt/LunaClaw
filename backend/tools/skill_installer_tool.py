import hashlib
import json
import re
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import requests

from agent.skill_registry import DEFAULT_GENERATED_SKILLS_DIR, DEFAULT_STATIC_SKILLS_DIR, SkillRegistry


DEFAULT_IMPORTED_SKILLS_DIR = DEFAULT_STATIC_SKILLS_DIR / "imported"
COMMON_SKILL_DIRS = ["skills", ".skills", "superpowers", "skill"]
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_FILES = 1000
MAX_FILE_BYTES = 5 * 1024 * 1024
ALLOWED_RESOURCE_EXTENSIONS = {
    ".css",
    ".csv",
    ".gif",
    ".html",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".md",
    ".pdf",
    ".png",
    ".py",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".webp",
    ".yaml",
    ".yml",
}
TEXT_RESOURCE_EXTENSIONS = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}


def install_skill(url, skill_id=None):
    url = str(url or "").strip()
    if not url:
        return _error("install_skill", "invalid_url", "url is required")
    if urlparse(url).scheme not in {"http", "https"}:
        return _error("install_skill", "invalid_url", "only http and https URLs are supported")

    github = _parse_github_url(url)
    if github and github["kind"] in {"repo", "tree"}:
        return install_skill_pack(url, pack_id=skill_id)

    try:
        response = requests.get(_normalize_download_url(url), timeout=20)
        response.raise_for_status()
    except Exception as exc:
        return _error("install_skill", "download_failed", str(exc), {"url": url})

    content = response.text or ""
    if not _looks_like_markdown_skill(content):
        return _error("install_skill", "invalid_skill", "downloaded content is not a markdown skill")

    meta, _body = _split_frontmatter(content)
    resolved_skill_id = _safe_skill_id(skill_id or meta.get("skill_id") or meta.get("name") or _stem_from_url(url))
    if not resolved_skill_id:
        return _error("install_skill", "invalid_skill_id", "skill_id could not be resolved")

    DEFAULT_IMPORTED_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_IMPORTED_SKILLS_DIR / f"{resolved_skill_id}.md"
    content = _ensure_skill_id(content, resolved_skill_id)
    path.write_text(content, encoding="utf-8")

    return {
        "ok": True,
        "mode": "single",
        "skill_id": resolved_skill_id,
        "name": meta.get("name") or resolved_skill_id,
        "description": meta.get("description", ""),
        "enabled": str(meta.get("enabled", "true")).lower() != "false",
        "path": str(path),
        "source_url": url,
    }


def install_skill_pack(url, pack_id=None):
    github = _parse_github_url(str(url or "").strip())
    if not github or github["kind"] not in {"repo", "tree"}:
        return _error("install_skill_pack", "invalid_url", "only GitHub repository or directory URLs are supported")

    resolved_pack_id = _safe_skill_id(pack_id or github["repo"])
    if not resolved_pack_id:
        return _error("install_skill_pack", "invalid_pack_id", "pack_id could not be resolved")

    errors = []
    try:
        downloaded, errors = _download_github_zip_files(github)
    except Exception as exc:
        return {
            "ok": True,
            "mode": "pack",
            "pack_id": resolved_pack_id,
            "installed_count": 0,
            "failed_count": 1,
            "installed_skills": [],
            "errors": [{"path": str(url), "error": str(exc)}],
        }

    scan_roots = [github["path"].strip("/")] if github["kind"] == "tree" else COMMON_SKILL_DIRS
    scanned = _filter_downloaded_roots(downloaded, scan_roots)
    skill_roots = _find_pack_skill_roots(scanned)
    installed_skills = []
    used_skill_ids = {skill.get("skill_id") for skill in list_skills().get("skills", [])}
    pack_dir = DEFAULT_IMPORTED_SKILLS_DIR / resolved_pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    for root in skill_roots:
        root_files = _files_for_skill_root(root, scanned)
        rel_slug = _safe_skill_id(root)
        skill_id = _unique_skill_id(f"{resolved_pack_id}_{rel_slug}", root, used_skill_ids)
        skill_path = "SKILL.md" if f"{root}/SKILL.md" in root_files else Path(root).name
        for rel_path, content in root_files.items():
            target = pack_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel_path == skill_path or rel_path.endswith("/SKILL.md") or rel_path == root:
                text = _ensure_skill_id(_decode_text(content), skill_id)
                target.write_text(text, encoding="utf-8")
            else:
                target.write_bytes(content)
        used_skill_ids.add(skill_id)
        final_skill_path = pack_dir / (f"{root}/SKILL.md" if f"{root}/SKILL.md" in root_files else root)
        meta, _body = _split_frontmatter(final_skill_path.read_text(encoding="utf-8"))
        installed_skills.append(
            {
                "skill_id": skill_id,
                "name": meta.get("name") or skill_id,
                "description": meta.get("description", ""),
                "path": str(final_skill_path),
            }
        )

    return {
        "ok": True,
        "mode": "pack",
        "pack_id": resolved_pack_id,
        "installed_count": len(installed_skills),
        "failed_count": len(errors),
        "installed_skills": installed_skills,
        "errors": errors,
    }


def list_skills():
    registry = SkillRegistry(static_dir=DEFAULT_STATIC_SKILLS_DIR, generated_dir=DEFAULT_GENERATED_SKILLS_DIR)
    skills = []
    for skill in registry.load_skills():
        skills.append(
            {
                "skill_id": skill.get("skill_id"),
                "name": skill.get("name"),
                "description": skill.get("description", ""),
                "triggers": skill.get("triggers", []),
                "enabled": skill.get("enabled", True),
                "path": skill.get("path"),
                "root_dir": skill.get("root_dir"),
                "resources": skill.get("resources", []),
                "mutable": _is_imported(skill.get("path")) or _is_generated(skill.get("path")),
                "delete_allowed": _is_imported(skill.get("path")),
            }
        )
    return {"ok": True, "skills": skills}


def read_skill(skill_id):
    resolved = _resolve_skill(skill_id)
    if not resolved["ok"]:
        return resolved
    skill = resolved["skill"]
    path = Path(skill["path"])
    meta, _body = _split_frontmatter(path.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "content": path.read_text(encoding="utf-8"),
        "metadata": meta,
        "skill": {
            **skill,
            "metadata": meta,
            "content": path.read_text(encoding="utf-8"),
            "mutable": _is_imported(path) or _is_generated(path),
            "delete_allowed": _is_imported(path),
        },
    }


def list_skill_resources(skill_id):
    resolved = _resolve_skill(skill_id)
    if not resolved["ok"]:
        return resolved
    skill = resolved["skill"]
    return {
        "ok": True,
        "skill_id": skill_id,
        "root_dir": skill.get("root_dir"),
        "resources": skill.get("resources", []),
    }


def read_skill_resource(skill_id, resource_path, max_chars=8000):
    resolved = _resolve_skill(skill_id)
    if not resolved["ok"]:
        return resolved
    skill = resolved["skill"]
    root_dir = Path(skill.get("root_dir") or "").resolve()
    requested = str(resource_path or "").replace("\\", "/").lstrip("/")
    try:
        path = (root_dir / requested).resolve()
        path.relative_to(root_dir)
    except Exception:
        return _error("read_skill_resource", "invalid_resource_path", "resource_path must stay within skill root_dir")
    if not path.exists() or not path.is_file():
        return _error("read_skill_resource", "resource_not_found", f"resource not found: {resource_path}")
    relative = path.relative_to(root_dir).as_posix()
    if relative not in set(skill.get("resources", [])):
        return _error("read_skill_resource", "resource_not_found", f"resource is not listed for skill: {resource_path}")

    size = path.stat().st_size
    suffix = path.suffix.lower()
    metadata = {"path": relative, "size": size, "extension": suffix}
    if suffix not in TEXT_RESOURCE_EXTENSIONS:
        return {
            "ok": False,
            "tool": "read_skill_resource",
            "error": {"code": "unsupported_binary", "message": "binary or unsupported resource cannot be read as text", "details": metadata},
            "metadata": metadata,
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    max_chars = max(0, int(max_chars or 8000))
    truncated = len(text) > max_chars
    return {
        "ok": True,
        "skill_id": skill_id,
        "resource_path": relative,
        "content": text[:max_chars],
        "truncated": truncated,
        "metadata": metadata,
    }


def enable_skill(skill_id):
    return _set_skill_enabled(skill_id, True)


def disable_skill(skill_id):
    return _set_skill_enabled(skill_id, False)


def delete_skill(skill_id):
    resolved = _resolve_skill(skill_id)
    if not resolved["ok"]:
        return resolved
    skill = resolved["skill"]
    path = Path(skill["path"])
    if not _is_imported(path):
        return _error("delete_skill", "delete_not_allowed", "only imported skills can be deleted")
    root_dir = Path(skill.get("root_dir") or path.parent)
    if root_dir.is_dir() and _is_imported(root_dir):
        shutil.rmtree(root_dir)
    elif path.exists():
        path.unlink()
    return {"ok": True, "skill_id": skill_id, "deleted": True}


def _set_skill_enabled(skill_id, enabled):
    resolved = _resolve_skill(skill_id)
    if not resolved["ok"]:
        return resolved
    skill = resolved["skill"]
    path = Path(skill["path"])
    if not (_is_imported(path) or _is_generated(path)):
        return _error("set_skill_enabled", "not_mutable", "static skills cannot be modified")
    text = path.read_text(encoding="utf-8")
    path.write_text(_set_frontmatter_value(text, "enabled", "true" if enabled else "false"), encoding="utf-8")
    return {"ok": True, "skill_id": skill_id, "enabled": enabled, "path": str(path)}


def _resolve_skill(skill_id):
    matches = [skill for skill in SkillRegistry(DEFAULT_STATIC_SKILLS_DIR, DEFAULT_GENERATED_SKILLS_DIR).load_skills() if skill.get("skill_id") == skill_id]
    if not matches:
        return _error("skill_lifecycle", "skill_not_found", f"skill not found: {skill_id}")
    if len(matches) > 1:
        return _error("skill_lifecycle", "ambiguous_skill_id", f"multiple skills use skill_id: {skill_id}", {"matches": [skill["path"] for skill in matches]})
    return {"ok": True, "skill": matches[0]}


def _parse_github_url(url):
    parsed = urlparse(url)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if len(parts) >= 5 and parts[2] in {"tree", "blob"}:
        return {"kind": parts[2], "owner": owner, "repo": repo, "branch": parts[3], "path": "/".join(parts[4:])}
    if len(parts) == 2:
        return {"kind": "repo", "owner": owner, "repo": repo, "branch": "main", "path": ""}
    return None


def _github_collect_files(owner, repo, branch, path, errors=None):
    errors = errors if errors is not None else []
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path)}?ref={quote(branch)}"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    payload = _response_json(response)
    if isinstance(payload, dict):
        payload = [payload]
    files = []
    for item in payload:
        if item.get("type") == "dir":
            try:
                files.extend(_github_collect_files(owner, repo, branch, item["path"], errors))
            except Exception as exc:
                errors.append({"path": item.get("path"), "error": str(exc)})
        elif item.get("type") == "file" and item.get("download_url"):
            files.append({"path": item["path"], "name": item.get("name", Path(item["path"]).name), "download_url": item["download_url"]})
    return files


def _download_github_zip_files(github):
    url = f"https://api.github.com/repos/{github['owner']}/{github['repo']}/zipball/{quote(github['branch'])}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    if len(response.content or b"") > MAX_ZIP_BYTES:
        raise ValueError(f"zipball exceeds MAX_ZIP_BYTES ({MAX_ZIP_BYTES})")
    files = {}
    errors = []
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if not members:
            return files, errors
        top_prefix = members[0].split("/", 1)[0] + "/"
        extracted_count = 0
        for member in members:
            if not member.startswith(top_prefix):
                continue
            rel_path = member[len(top_prefix) :]
            if not rel_path:
                continue
            suffix = Path(rel_path).suffix.lower()
            info = archive.getinfo(member)
            if suffix not in ALLOWED_RESOURCE_EXTENSIONS:
                errors.append({"path": rel_path, "code": "unsupported_extension", "error": f"unsupported extension: {suffix or '<none>'}"})
                continue
            if info.file_size > MAX_FILE_BYTES:
                errors.append({"path": rel_path, "code": "file_too_large", "error": f"file exceeds MAX_FILE_BYTES ({MAX_FILE_BYTES})"})
                continue
            if extracted_count >= MAX_EXTRACTED_FILES:
                errors.append({"path": rel_path, "code": "too_many_files", "error": f"zipball exceeds MAX_EXTRACTED_FILES ({MAX_EXTRACTED_FILES})"})
                continue
            files[rel_path] = archive.read(member)
            extracted_count += 1
    return files, errors


def _filter_downloaded_roots(downloaded, scan_roots):
    normalized_roots = [root.strip("/") for root in scan_roots if root.strip("/")]
    if not normalized_roots:
        return dict(downloaded)
    filtered = {}
    for path, content in downloaded.items():
        if any(path == root or path.startswith(f"{root}/") for root in normalized_roots):
            filtered[path] = content
    return filtered


def _download_text(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.text or ""


def _response_json(response):
    if isinstance(response.text, (list, dict)):
        return response.text
    return json.loads(response.text)


def _find_pack_skill_roots(downloaded):
    roots = []
    for rel_path, content in downloaded.items():
        name = Path(rel_path).name.lower()
        meta, _body = _split_frontmatter(_decode_text(content))
        if name == "skill.md":
            roots.append(str(Path(rel_path).parent).replace("\\", "/"))
        elif rel_path.lower().endswith(".md") and meta:
            roots.append(rel_path)
    return sorted(set(root for root in roots if root and root != "."))


def _files_for_skill_root(root, downloaded):
    if root in downloaded:
        return {root: downloaded[root]}
    prefix = f"{root}/"
    return {path: content for path, content in downloaded.items() if path.startswith(prefix)}


def _unique_skill_id(base, relative_path, used):
    skill_id = _safe_skill_id(base)
    if skill_id not in used:
        return skill_id
    suffix = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:8]
    candidate = _safe_skill_id(f"{skill_id}_{suffix}")
    counter = 2
    while candidate in used:
        candidate = _safe_skill_id(f"{skill_id}_{suffix}_{counter}")
        counter += 1
    return candidate


def _normalize_download_url(url):
    parsed = urlparse(url)
    github = _parse_github_url(url)
    if github and github["kind"] == "blob":
        return f"https://raw.githubusercontent.com/{github['owner']}/{github['repo']}/{github['branch']}/{github['path']}"
    if parsed.netloc.lower() == "github.com" and "/blob/" in parsed.path:
        owner_repo, path_part = parsed.path.lstrip("/").split("/blob/", 1)
        return f"https://raw.githubusercontent.com/{owner_repo}/{path_part}"
    if github and github["kind"] == "repo":
        return f"https://raw.githubusercontent.com/{github['owner']}/{github['repo']}/main/README.md"
    return url


def _looks_like_markdown_skill(content):
    text = _decode_text(content).lstrip()
    return text.startswith("---") or text.startswith("#")


def _split_frontmatter(text):
    text = _decode_text(text)
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    current_key = None
    for raw in parts[1].splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            meta.setdefault(current_key, []).append(line[4:].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            meta[current_key] = value if value else []
    return meta, parts[2]


def _ensure_skill_id(text, skill_id):
    text = _decode_text(text)
    meta, body = _split_frontmatter(text)
    if not meta:
        return f"---\nskill_id: {skill_id}\nenabled: true\n---\n{text}"
    if str(meta.get("skill_id") or "").strip() == skill_id:
        return text
    return _set_frontmatter_value(text, "skill_id", skill_id)


def _set_frontmatter_value(text, key, value):
    text = _decode_text(text)
    if not text.startswith("---"):
        return f"---\n{key}: {value}\n---\n{text}"
    parts = text.split("---", 2)
    lines = parts[1].splitlines()
    output = []
    replaced = False
    for line in lines:
        if line.split(":", 1)[0].strip() == key and ":" in line:
            output.append(f"{key}: {value}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"{key}: {value}")
    return "---\n" + "\n".join(output) + "\n---" + parts[2]


def _safe_skill_id(value):
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    normalized = re.sub(r"_+", "_", normalized).strip("._-")
    return normalized[:120]


def _decode_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _stem_from_url(url):
    stem = Path(urlparse(url).path).stem
    return stem or "imported_skill"


def _is_imported(path):
    return _is_relative_to(Path(path), DEFAULT_IMPORTED_SKILLS_DIR) or _is_relative_to(Path(path), Path(DEFAULT_STATIC_SKILLS_DIR) / "imported")


def _is_generated(path):
    return _is_relative_to(Path(path), DEFAULT_GENERATED_SKILLS_DIR)


def _is_relative_to(path, parent):
    try:
        path.resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def _error(tool, code, message, details=None):
    return {"ok": False, "tool": tool, "error": {"code": code, "message": message, "details": details or {}}}
