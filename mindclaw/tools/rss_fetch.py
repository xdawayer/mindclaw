# input: tools/base.py, tools/_ssrf.py, httpx, defusedxml, time, re
# output: RssFetchTool
# pos: 通用 RSS/Atom feed 抓取工具，支持任意 feed URL，SSRF 防护 + XXE 防护
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from defusedxml import ElementTree as SafeET
from loguru import logger

from ._ssrf import is_safe_url as _is_safe_url
from .base import RiskLevel, Tool

# ── Constants ──────────────────────────────────────────────

_MAX_URL_LEN = 500
_MAX_RESPONSE_BYTES = 2_000_000
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_NETWORK_ERRORS = (httpx.HTTPError, OSError)


# ── Parsers ────────────────────────────────────────────────


def _parse_rss2(root: ET.Element) -> list[dict]:
    """Parse RSS 2.0 <channel><item> elements."""
    posts = []
    channel = root.find("channel")
    if channel is None:
        return []

    for item in channel.findall("item"):
        title = _text(item, "title")
        link = _text(item, "link")
        desc = _text(item, "description")
        author = _text(item, "author") or _text(item, "{http://purl.org/dc/elements/1.1/}creator")
        pub_date = _text(item, "pubDate")

        created_utc = _parse_rss_date(pub_date) if pub_date else 0.0

        # Strip HTML from description
        content = re.sub(r"<[^>]+>", " ", desc).strip()
        content = re.sub(r"\s+", " ", content)

        posts.append({
            "title": title,
            "link": link,
            "content": content,
            "author": author,
            "created_utc": created_utc,
        })

    return posts


def _parse_atom(root: ET.Element) -> list[dict]:
    """Parse Atom <feed><entry> elements."""
    posts = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        title = _text_ns(entry, "atom:title")
        link_el = entry.find("atom:link", _ATOM_NS)
        link = link_el.get("href", "") if link_el is not None else ""
        author_el = entry.find("atom:author/atom:name", _ATOM_NS)
        author = author_el.text if author_el is not None and author_el.text else ""
        updated = _text_ns(entry, "atom:updated") or _text_ns(entry, "atom:published")
        content_el = entry.find("atom:content", _ATOM_NS)
        if content_el is None:
            content_el = entry.find("atom:summary", _ATOM_NS)

        created_utc = _parse_iso_date(updated) if updated else 0.0

        content = ""
        if content_el is not None and content_el.text:
            content = re.sub(r"<[^>]+>", " ", content_el.text).strip()
            content = re.sub(r"\s+", " ", content)

        posts.append({
            "title": title,
            "link": link,
            "content": content,
            "author": author,
            "created_utc": created_utc,
        })

    return posts


# ── Date parsing helpers ───────────────────────────────────


def _parse_rss_date(date_str: str) -> float:
    """Parse RFC 822 / RFC 2822 date to Unix timestamp."""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def _parse_iso_date(date_str: str) -> float:
    """Parse ISO 8601 date to Unix timestamp."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


# ── XML helpers ────────────────────────────────────────────


def _text(el: ET.Element, tag: str) -> str:
    """Get text of a child element, or empty string."""
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _text_ns(el: ET.Element, tag: str) -> str:
    """Get text of a namespaced child element."""
    child = el.find(tag, _ATOM_NS)
    return child.text.strip() if child is not None and child.text else ""


def _time_ago(created_utc: float) -> str:
    """Convert Unix timestamp to human-readable relative time."""
    diff = max(0.0, time.time() - created_utc)
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60:.0f}m ago"
    if diff < 86400:
        return f"{diff // 3600:.0f}h ago"
    return f"{diff // 86400:.0f}d ago"


# ── Formatter ──────────────────────────────────────────────


def _format_posts(feed_title: str, posts: list[dict]) -> str:
    """Format posts into readable text."""
    if not posts:
        return f"## {feed_title}\n\nNo recent posts found."

    lines = [f"## {feed_title} ({len(posts)} posts)\n"]

    for i, p in enumerate(posts, 1):
        title = p.get("title", "")
        link = p.get("link", "")
        author = p.get("author", "")
        content = p.get("content", "")
        created_utc = p.get("created_utc", 0)

        preview = ""
        if content:
            preview = content[:200].replace("\n", " ").replace("\r", "").strip()
            if len(content) > 200:
                preview += "..."

        author_str = f" by {author}" if author else ""
        time_str = f" | {_time_ago(created_utc)}" if created_utc else ""

        lines.append(
            f"{i}. **{title}**{author_str}{time_str}\n"
            f"   {preview}\n"
            f"   {link}"
        )

    return "\n\n".join(lines)


# ── Main Tool ──────────────────────────────────────────────


class RssFetchTool(Tool):
    name = "rss_fetch"
    description = (
        "Fetch and parse an RSS or Atom feed URL. Returns recent posts with "
        "title, content preview, author, and link. Supports any public RSS/Atom feed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "RSS or Atom feed URL",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of posts to return, 1-50 (default: 10)",
            },
            "hours": {
                "type": "integer",
                "description": "Only include posts from the last N hours (default: no filter)",
            },
        },
        "required": ["url"],
    }
    risk_level = RiskLevel.MODERATE
    max_result_chars = 5000

    async def execute(self, params: dict) -> str:
        # ── Validate inputs ───────────────────────────────
        url = params.get("url", "").strip()
        if not url:
            return "Error: 'url' parameter is required"
        if len(url) > _MAX_URL_LEN:
            return f"Error: URL too long (max {_MAX_URL_LEN} chars)"

        if not _is_safe_url(url):
            return "Error: URL targets a private/internal address"

        limit = params.get("limit", 10)
        try:
            limit = max(1, min(50, int(limit)))
        except (TypeError, ValueError):
            limit = 10

        hours = params.get("hours")
        cutoff = 0.0
        if hours is not None:
            try:
                hours = max(1, int(hours))
                cutoff = time.time() - hours * 3600
            except (TypeError, ValueError):
                pass

        # ── Fetch ─────────────────────────────────────────
        try:
            xml_text = await self._fetch_feed(url)
        except _NETWORK_ERRORS as exc:
            logger.warning("RSS fetch failed for {}: {}", url, exc)
            return f"Error: RSS fetch failed - {exc}"

        # ── Parse (defusedxml blocks XXE / Billion Laughs) ─
        try:
            root = SafeET.fromstring(xml_text)
        except (ET.ParseError, SafeET.DTDForbidden, SafeET.EntitiesForbidden) as exc:
            return f"Error: failed to parse feed XML - {exc}"

        # Detect feed type
        if root.tag == "rss" or root.find("channel") is not None:
            posts = _parse_rss2(root)
        elif root.tag.endswith("}feed") or root.tag == "feed":
            posts = _parse_atom(root)
        else:
            return f"Error: unrecognized feed format (root tag: {root.tag})"

        # ── Filter by time (undated posts always included) ─
        if cutoff > 0:
            posts = [
                p for p in posts
                if p.get("created_utc", 0) == 0.0 or p.get("created_utc", 0) >= cutoff
            ]

        # ── Limit ─────────────────────────────────────────
        posts = posts[:limit]

        # ── Format ────────────────────────────────────────
        # Extract feed title
        feed_title = self._extract_feed_title(root) or url
        result = _format_posts(feed_title, posts)

        if self.max_result_chars and len(result) > self.max_result_chars:
            result = result[: self.max_result_chars] + "\n[truncated]"

        return result

    @staticmethod
    async def _fetch_feed(url: str) -> str:
        """Fetch feed content with SSRF-safe redirect handling."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        }

        async with httpx.AsyncClient(follow_redirects=False, timeout=15.0) as client:
            current_url = url
            for _ in range(5):
                resp = await client.get(current_url, headers=headers)

                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        raise ValueError("Redirect with no Location header")
                    # Re-validate redirected URL for SSRF
                    if not _is_safe_url(location):
                        raise ValueError("Redirect targets a private/internal address")
                    current_url = location
                    continue

                resp.raise_for_status()

                # Post-response SSRF re-validation (mitigate DNS rebinding)
                if not _is_safe_url(str(resp.url)):
                    raise ValueError("Resolved URL targets a private/internal address")

                # Limit response size
                content = resp.content
                if len(content) > _MAX_RESPONSE_BYTES:
                    content = content[:_MAX_RESPONSE_BYTES]

                # Decode (strip quotes from charset per RFC 7231)
                charset = "utf-8"
                ct = resp.headers.get("content-type", "")
                if "charset=" in ct:
                    charset = ct.split("charset=")[-1].split(";")[0].strip().strip('"')
                return content.decode(charset, errors="replace")

            raise ValueError("Too many redirects")

    @staticmethod
    def _extract_feed_title(root: ET.Element) -> str:
        """Extract feed title from RSS or Atom root."""
        # RSS 2.0
        channel = root.find("channel")
        if channel is not None:
            title_el = channel.find("title")
            if title_el is not None and title_el.text:
                return title_el.text.strip()
        # Atom
        title_el = root.find("atom:title", _ATOM_NS)
        if title_el is not None and title_el.text:
            return title_el.text.strip()
        # Plain <title>
        title_el = root.find("title")
        if title_el is not None and title_el.text:
            return title_el.text.strip()
        return ""
