import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from agent.skill_registry import DEFAULT_GENERATED_SKILLS_DIR, DEFAULT_STATIC_SKILLS_DIR, SkillRegistry


DEFAULT_IMPORTED_SKILLS_DIR = DEFAULT_STATIC_SKILLS_DIR / "imported"


def install_skill(url, skill_id=None):
    url = str(url or "").strip()
    if not url:
        return _error("invalid_url", "url is required")
    if urlparse(url).scheme not in {"http", "https"}:
        return _error("invalid_url", "only http and https URLs are supported")

    try:
        response = requests.get(_normalize_download_url(url), timeout=20)
        response.raise_for_status()
    except Exception as exc:
        return _error("download_failed", str(exc), {"url": url})

    content = response.text or ""
    if not _looks_like_markdown_skill(content):
        return _error("invalid_skill", "downloaded content is not a markdown skill")

    meta, _body = _split_frontmatter(content)
    resolved_skill_id = _safe_skill_id(skill_id or meta.get("skill_id") or meta.get("name") or _stem_from_url(url))
    if not resolved_skill_id:
        return _error("invalid_skill_id", "skill_id could not be resolved")

    DEFAULT_IMPORTED_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_IMPORTED_SKILLS_DIR / f"{resolved_skill_id}.md"
    path.write_text(content, encoding="utf-8")

    return {
        "ok": True,
        "skill_id": resolved_skill_id,
        "name": meta.get("name") or resolved_skill_id,
        "description": meta.get("description", ""),
        "enabled": str(meta.get("enabled", "true")).lower() != "false",
        "path": str(path),
        "source_url": url,
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
            }
        )
    return {"ok": True, "skills": skills}


def _normalize_download_url(url):
    parsed = urlparse(url)
    if parsed.netloc.lower() == "github.com" and "/blob/" in parsed.path:
        owner_repo, path_part = parsed.path.lstrip("/").split("/blob/", 1)
        return f"https://raw.githubusercontent.com/{owner_repo}/{path_part}"
    return url


def _looks_like_markdown_skill(content):
    text = content.lstrip()
    return text.startswith("---") or text.startswith("#")


def _split_frontmatter(text):
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


def _safe_skill_id(value):
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    normalized = re.sub(r"_+", "_", normalized).strip("._-")
    return normalized[:80]


def _stem_from_url(url):
    stem = Path(urlparse(url).path).stem
    return stem or "imported_skill"


def _error(code, message, details=None):
    return {"ok": False, "tool": "install_skill", "error": {"code": code, "message": message, "details": details or {}}}
