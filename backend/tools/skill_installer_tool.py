import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import requests

from agent.skill_registry import DEFAULT_GENERATED_SKILLS_DIR, DEFAULT_STATIC_SKILLS_DIR, SkillRegistry


DEFAULT_IMPORTED_SKILLS_DIR = DEFAULT_STATIC_SKILLS_DIR / "imported"
COMMON_SKILL_DIRS = ["skills", ".skills", "superpowers", "skill"]


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

    scan_roots = [github["path"]] if github["kind"] == "tree" else COMMON_SKILL_DIRS
    file_entries = []
    errors = []
    for root in scan_roots:
        try:
            file_entries.extend(_github_collect_files(github["owner"], github["repo"], github["branch"], root.strip("/"), errors))
        except Exception as exc:
            errors.append({"path": root, "error": str(exc)})

    downloaded = {}
    for entry in file_entries:
        try:
            downloaded[entry["path"]] = _download_text(entry["download_url"])
        except Exception as exc:
            errors.append({"path": entry.get("path"), "error": str(exc)})

    skill_roots = _find_pack_skill_roots(downloaded)
    installed_skills = []
    used_skill_ids = {skill.get("skill_id") for skill in list_skills().get("skills", [])}
    pack_dir = DEFAULT_IMPORTED_SKILLS_DIR / resolved_pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    for root in skill_roots:
        root_files = _files_for_skill_root(root, downloaded)
        rel_slug = _safe_skill_id(root)
        skill_id = _unique_skill_id(f"{resolved_pack_id}_{rel_slug}", root, used_skill_ids)
        skill_path = "SKILL.md" if f"{root}/SKILL.md" in root_files else Path(root).name
        for rel_path, content in root_files.items():
            target = pack_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel_path == skill_path or rel_path.endswith("/SKILL.md") or rel_path == root:
                content = _ensure_skill_id(content, skill_id)
            target.write_text(content, encoding="utf-8")
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
        meta, _body = _split_frontmatter(content)
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
    text = str(content or "").lstrip()
    return text.startswith("---") or text.startswith("#")


def _split_frontmatter(text):
    if not str(text or "").startswith("---"):
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
    meta, body = _split_frontmatter(text)
    if not meta:
        return f"---\nskill_id: {skill_id}\nenabled: true\n---\n{text}"
    if str(meta.get("skill_id") or "").strip() == skill_id:
        return text
    return _set_frontmatter_value(text, "skill_id", skill_id)


def _set_frontmatter_value(text, key, value):
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
