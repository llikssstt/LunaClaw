import re
from html import unescape
from urllib.parse import urlparse

import requests


def run(tool_name, arguments):
    if tool_name != "fetch_page":
        return {"ok": False, "error": {"code": "unknown_tool", "message": tool_name}}
    url = str((arguments or {}).get("url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"ok": False, "error": {"code": "invalid_url", "message": "Only http/https URLs are allowed"}}
    response = requests.get(url, headers={"User-Agent": "V-Agent-WebReader/0.1"}, timeout=10)
    response.raise_for_status()
    html = response.text
    text = _html_to_text(html)
    max_chars = 8000
    return {
        "ok": True,
        "url": url,
        "title": _extract_title(html),
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
    }


def _extract_title(html):
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", unescape(match.group(1))).strip()


def _html_to_text(html):
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()

