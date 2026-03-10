# input: tools/base.py, tools/_ssrf.py, httpx, knowledge/_text_utils.py
# output: 导出 WebSearchTool, WebFetchTool
# pos: 网页搜索和抓取工具，含 SSRF 防护
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from urllib.parse import urljoin

import httpx
from loguru import logger

from mindclaw.knowledge._text_utils import html_to_text

from ._ssrf import is_safe_url as _is_safe_url
from .base import RiskLevel, Tool

MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 5
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch a web page and return its text content."
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "URL to fetch"}},
        "required": ["url"],
    }
    risk_level = RiskLevel.MODERATE
    max_result_chars = 5000

    def __init__(self, max_chars: int = 5000) -> None:
        self.max_result_chars = max_chars

    async def execute(self, params: dict) -> str:
        url = params["url"]
        if not _is_safe_url(url):
            return "Error: URL targets a private/internal address"
        logger.info(f"Fetching: {url}")
        try:
            async with httpx.AsyncClient(
                follow_redirects=False, timeout=15.0, trust_env=False,
            ) as client:
                current_url = url
                content_type = ""
                body = bytearray()
                for _ in range(MAX_REDIRECTS):
                    async with client.stream("GET", current_url) as resp:
                        if resp.status_code in _REDIRECT_CODES:
                            location = resp.headers.get("location")
                            if not location:
                                return "Error: redirect with no Location header"
                            current_url = urljoin(current_url, location)
                            if not _is_safe_url(current_url):
                                return "Error: redirect targets a private/internal address"
                            continue
                        if resp.status_code != 200:
                            return f"Error: HTTP {resp.status_code}"
                        content_type = resp.headers.get("content-type", "")
                        async for chunk in resp.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_RESPONSE_BYTES:
                                break
                    break
                else:
                    return "Error: too many redirects"
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            text_content = bytes(body).decode(charset, errors="replace")
            if "text/html" in content_type:
                text = html_to_text(text_content)
            else:
                text = text_content
            if len(text) > self.max_result_chars:
                text = text[: self.max_result_chars] + "\n...(truncated)"
            return text
        except Exception as e:
            return f"Error fetching URL: {e}"


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web using Tavily Search API."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Number of results (default: 5)"},
        },
        "required": ["query"],
    }
    risk_level = RiskLevel.SAFE
    max_result_chars = 3000

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    async def execute(self, params: dict) -> str:
        query = params["query"]
        count = params.get("count", 5)
        if not self.api_key:
            return "Error: web search API key not configured"
        logger.info(f"Searching: {query}")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": count,
                        "include_answer": False,
                    },
                )
            if resp.status_code != 200:
                return f"Error: search API returned HTTP {resp.status_code}"
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return "No results found."
            lines = []
            for r in results:
                lines.append(f"**{r['title']}**")
                lines.append(f"  URL: {r['url']}")
                lines.append(f"  {r.get('content', '')[:200]}")
                lines.append("")
            return "\n".join(lines).strip()
        except Exception as e:
            return f"Error searching: {e}"
