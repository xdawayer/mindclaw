# input: tools/base.py, httpx (lazy), xml.etree.ElementTree, asyncio, time, re
# output: RedditFetchTool
# pos: Reddit 帖子抓取工具，OAuth API + 降级RSS feed模式
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import re
import time
import xml.etree.ElementTree as ET

from loguru import logger

from .base import RiskLevel, Tool

# ── Constants ──────────────────────────────────────────────

_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{1,50}$")
_MAX_SEARCH_QUERY_LEN = 200
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_OAUTH_BASE = "https://oauth.reddit.com"
_PUBLIC_BASE = "https://www.reddit.com"


# ── OAuth Token Manager ───────────────────────────────────


class _TokenManager:
    """Manages Reddit OAuth client_credentials tokens with auto-refresh."""

    def __init__(self, client_id: str, client_secret: str, user_agent: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._token: str = ""
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def has_credentials(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _is_expired(self) -> bool:
        return time.monotonic() >= self._expires_at

    async def get_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        async with self._lock:
            if self._token and not self._is_expired():
                return self._token
            return await self._refresh()

    async def invalidate_and_refresh(self) -> str:
        """Atomically invalidate current token and fetch a new one."""
        async with self._lock:
            self._token = ""
            self._expires_at = 0.0
            return await self._refresh()

    async def _refresh(self) -> str:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                headers={"User-Agent": self._user_agent},
                timeout=15,
            )
            resp.raise_for_status()
            body = resp.json()

        self._token = body["access_token"]
        expires_in = body.get("expires_in", 3600)
        # Refresh 60s before actual expiry
        self._expires_at = time.monotonic() + expires_in - 60
        logger.debug("Reddit OAuth token refreshed, expires_in={}s", expires_in)
        return self._token


# ── Rate Limiter ───────────────────────────────────────────


class _RateLimiter:
    """Simple async rate limiter based on minimum interval between requests."""

    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            remaining = self._interval - elapsed
            # Reserve our slot before releasing the lock
            self._last_request = now + max(remaining, 0.0)
        if remaining > 0:
            await asyncio.sleep(remaining)


# ── Helpers ────────────────────────────────────────────────


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


def _format_posts(subreddit: str, sort: str, posts: list[dict]) -> str:
    """Format posts into readable text."""
    if not posts:
        return f"## r/{subreddit} - {sort}\n\nNo posts found matching the criteria."

    lines = [f"## r/{subreddit} - {sort} ({len(posts)} posts)\n"]

    for i, p in enumerate(posts, 1):
        title = p.get("title", "")
        score = p.get("score", 0)
        num_comments = p.get("num_comments", 0)
        author = p.get("author", "[deleted]")
        permalink = p.get("permalink", "")
        created_utc = p.get("created_utc", 0)
        is_self = p.get("is_self", False)
        selftext = p.get("selftext", "")
        url = p.get("url", "")

        content_line = ""
        if is_self and selftext:
            preview = selftext[:200].replace("\n", " ").replace("\r", "").strip()
            if len(selftext) > 200:
                preview += "..."
            content_line = f"   {preview}"
        elif not is_self and url:
            content_line = f"   {url}"

        full_url = permalink if permalink.startswith("http") else f"https://reddit.com{permalink}"
        lines.append(
            f"{i}. **{title}** (score: {score}, comments: {num_comments})\n"
            f"{content_line}\n"
            f"   Posted by u/{author} | {_time_ago(created_utc)}\n"
            f"   {full_url}"
        )

    return "\n\n".join(lines)


# ── Main Tool ──────────────────────────────────────────────


class RedditFetchTool(Tool):
    name = "reddit_fetch"
    description = (
        "Fetch posts from a Reddit subreddit. Supports browsing (hot/new/top/rising) "
        "and searching within a subreddit. Filter by minimum score."
    )
    parameters = {
        "type": "object",
        "properties": {
            "subreddit": {
                "type": "string",
                "description": "Subreddit name without r/ prefix, e.g. 'MachineLearning'",
            },
            "sort": {
                "type": "string",
                "enum": ["hot", "new", "top", "rising"],
                "description": "Sort method (default: hot)",
            },
            "time_filter": {
                "type": "string",
                "enum": ["hour", "day", "week", "month", "year", "all"],
                "description": "Time filter for 'top' sort (default: day)",
            },
            "limit": {
                "type": "integer",
                "description": "Number of posts to fetch, 1-100 (default: 25)",
            },
            "min_score": {
                "type": "integer",
                "description": "Minimum upvote score filter (default: 0)",
            },
            "search_query": {
                "type": "string",
                "description": "Optional: search within the subreddit instead of browsing",
            },
        },
        "required": ["subreddit"],
    }
    risk_level = RiskLevel.MODERATE
    max_result_chars = 5000

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        user_agent: str = "mindclaw:bot:v1.0 (by /u/mindclaw-bot)",
        rate_limit: float = 2.0,
    ) -> None:
        self._token_mgr = _TokenManager(client_id, client_secret, user_agent)
        self._user_agent = user_agent

        has_id = bool(client_id)
        has_secret = bool(client_secret)
        if has_id != has_secret:
            logger.warning(
                "RedditFetchTool: only one of client_id/client_secret provided; "
                "falling back to unauthenticated mode"
            )
        self._use_oauth = has_id and has_secret

        # Degraded mode uses more conservative rate limit
        interval = rate_limit if self._use_oauth else max(rate_limit, 5.0)
        self._limiter = _RateLimiter(interval)

    async def execute(self, params: dict) -> str:
        # ── Validate inputs ───────────────────────────────
        subreddit = params.get("subreddit", "").strip()
        if not subreddit:
            return "Error: 'subreddit' parameter is required"
        # Strip leading r/ if present
        if subreddit.startswith("r/"):
            subreddit = subreddit[2:]
        if not _SUBREDDIT_RE.match(subreddit):
            return "Error: invalid subreddit name (alphanumeric and underscore only, max 50 chars)"

        sort = params.get("sort", "hot")
        if sort not in ("hot", "new", "top", "rising"):
            sort = "hot"

        time_filter = params.get("time_filter", "day")
        if time_filter not in ("hour", "day", "week", "month", "year", "all"):
            time_filter = "day"

        limit = params.get("limit", 25)
        try:
            limit = max(1, min(100, int(limit)))
        except (TypeError, ValueError):
            limit = 25

        min_score = params.get("min_score", 0)
        try:
            min_score = max(0, int(min_score))
        except (TypeError, ValueError):
            min_score = 0

        search_query = params.get("search_query", "").strip()
        if search_query and len(search_query) > _MAX_SEARCH_QUERY_LEN:
            return f"Error: search_query too long (max {_MAX_SEARCH_QUERY_LEN} chars)"

        # ── Rate limit ────────────────────────────────────
        await self._limiter.wait()

        # ── Fetch ─────────────────────────────────────────
        try:
            import httpx as _httpx
            _network_errors = (_httpx.HTTPError, OSError)
        except ImportError:
            _network_errors = (OSError,)

        try:
            posts = await self._fetch(
                subreddit=subreddit,
                sort=sort,
                time_filter=time_filter,
                limit=limit,
                search_query=search_query,
            )
        except _network_errors as exc:
            logger.warning("Reddit fetch failed for r/{}: {}", subreddit, exc)
            return f"Error: Reddit fetch failed - {exc}"

        # ── Filter by min_score ───────────────────────────
        if min_score > 0:
            posts = [p for p in posts if p.get("score", 0) >= min_score]

        # ── Format output ─────────────────────────────────
        label = f"{sort}" if not search_query else f"search: {search_query}"
        result = _format_posts(subreddit, label, posts)

        if self.max_result_chars and len(result) > self.max_result_chars:
            result = result[: self.max_result_chars] + "\n[truncated]"

        return result

    async def _fetch(
        self,
        subreddit: str,
        sort: str,
        time_filter: str,
        limit: int,
        search_query: str,
    ) -> list[dict]:
        """Fetch posts via OAuth API or degraded public .json endpoint."""
        if self._use_oauth:
            return await self._fetch_oauth(
                subreddit, sort, time_filter, limit, search_query
            )
        return await self._fetch_public(
            subreddit, sort, time_filter, limit, search_query
        )

    async def _fetch_oauth(
        self,
        subreddit: str,
        sort: str,
        time_filter: str,
        limit: int,
        search_query: str,
    ) -> list[dict]:
        """Fetch via OAuth API with auto-retry on 401."""
        import httpx

        token = await self._token_mgr.get_token()

        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": self._user_agent,
            }

            if search_query:
                url = f"{_OAUTH_BASE}/r/{subreddit}/search.json"
                query_params = {
                    "q": search_query,
                    "restrict_sr": "on",
                    "sort": "relevance",
                    "t": time_filter,
                    "limit": str(limit),
                }
            else:
                url = f"{_OAUTH_BASE}/r/{subreddit}/{sort}.json"
                query_params = {"limit": str(limit), "t": time_filter}

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, headers=headers, params=query_params, timeout=20
                )

            if resp.status_code == 401 and attempt == 0:
                logger.warning("Reddit OAuth 401, refreshing token")
                token = await self._token_mgr.invalidate_and_refresh()
                continue

            resp.raise_for_status()
            return self._parse_listing(resp.json())

        return []

    async def _fetch_public(
        self,
        subreddit: str,
        sort: str,
        time_filter: str,
        limit: int,
        search_query: str,
    ) -> list[dict]:
        """Degraded mode: fetch via RSS/Atom feed (public, no auth needed).

        Reddit blocks unauthenticated JSON API but RSS feeds remain public.
        RSS feeds do not support search_query — returns empty list with a note.
        RSS does not include score/num_comments; those default to 0.
        """
        import httpx

        if search_query:
            logger.info("RSS mode does not support search_query, skipping")
            return []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/atom+xml",
        }

        url = f"{_PUBLIC_BASE}/r/{subreddit}/{sort}/.rss"
        query_params = {"limit": str(limit)}
        if sort == "top":
            query_params["t"] = time_filter

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=headers, params=query_params,
                timeout=20, follow_redirects=True,
            )

        resp.raise_for_status()
        return self._parse_atom_feed(resp.text, subreddit)

    @staticmethod
    def _parse_listing(data: dict) -> list[dict]:
        """Parse Reddit listing JSON into list of post dicts."""
        children = data.get("data", {}).get("children", [])
        posts = []
        for child in children:
            post = child.get("data", {})
            if not post:
                continue
            posts.append({
                "title": post.get("title", ""),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "author": post.get("author", "[deleted]"),
                "permalink": post.get("permalink", ""),
                "created_utc": post.get("created_utc", 0),
                "is_self": post.get("is_self", False),
                "selftext": post.get("selftext", ""),
                "url": post.get("url", ""),
                "subreddit": post.get("subreddit", ""),
            })
        return posts

    @staticmethod
    def _parse_atom_feed(xml_text: str, subreddit: str) -> list[dict]:
        """Parse Reddit Atom/RSS feed into list of post dicts.

        RSS feeds lack score/num_comments, so those default to 0.
        """
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        posts = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("Failed to parse Reddit RSS feed XML")
            return []

        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            author_el = entry.find("atom:author/atom:name", ns)
            updated_el = entry.find("atom:updated", ns)
            content_el = entry.find("atom:content", ns)

            title = title_el.text if title_el is not None and title_el.text else ""
            link = link_el.get("href", "") if link_el is not None else ""
            author = author_el.text if author_el is not None and author_el.text else ""
            # Strip /u/ prefix from author
            if author.startswith("/u/"):
                author = author[3:]

            # Extract permalink from link
            permalink = ""
            if link and "reddit.com" in link:
                idx = link.find("/r/")
                if idx >= 0:
                    permalink = link[idx:]

            # Parse updated time to unix timestamp
            created_utc = 0.0
            if updated_el is not None and updated_el.text:
                try:
                    from datetime import datetime, timezone
                    dt = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
                    created_utc = dt.replace(tzinfo=timezone.utc).timestamp()
                except (ValueError, TypeError):
                    pass

            # Extract text content (HTML) — strip tags for preview
            selftext = ""
            if content_el is not None and content_el.text:
                raw = content_el.text
                # Simple HTML tag stripping
                selftext = re.sub(r"<[^>]+>", " ", raw).strip()
                selftext = re.sub(r"\s+", " ", selftext)

            is_self = not link or "reddit.com/r/" in link

            posts.append({
                "title": title,
                "score": 0,
                "num_comments": 0,
                "author": author,
                "permalink": permalink,
                "created_utc": created_utc,
                "is_self": bool(selftext),
                "selftext": selftext,
                "url": link if not is_self else "",
                "subreddit": subreddit,
            })

        return posts
