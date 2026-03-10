# input: re
# output: 导出 html_to_text, extract_snippet
# pos: 知识层共享文本工具 — HTML 转文本、snippet 提取
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Shared text utilities for knowledge modules.

Centralises HTML-to-text conversion and snippet extraction so that
obsidian.py, web_archive.py, and tools/web.py do not duplicate logic.
"""

from __future__ import annotations

import re

_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    """Strip HTML tags, scripts, and styles — returning plain text."""
    text = _SCRIPT_STYLE_RE.sub("", html)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def extract_snippet(text: str, query_lower: str, context_chars: int = 120) -> str:
    """Return a short snippet around the first occurrence of *query_lower*."""
    text_lower = text.lower()
    idx = text_lower.find(query_lower)
    if idx == -1:
        return ""
    start = max(0, idx - context_chars // 2)
    end = min(len(text), idx + len(query_lower) + context_chars // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet
