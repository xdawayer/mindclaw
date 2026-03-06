# input: tools/base.py, httpx
# output: 导出 WebSearchTool, WebFetchTool
# pos: 网页搜索和抓取工具
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import re

import httpx
from loguru import logger

from .base import RiskLevel, Tool


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch a web page and return its text content."
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "URL to fetch"}},
        "required": ["url"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, max_chars: int = 5000) -> None:
        self.max_chars = max_chars

    async def execute(self, params: dict) -> str:
        url = params["url"]
        logger.info(f"Fetching: {url}")
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                return f"Error: HTTP {resp.status_code}"
            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type:
                text = _html_to_text(resp.text)
            else:
                text = resp.text
            if len(text) > self.max_chars:
                text = text[: self.max_chars] + "\n...(truncated)"
            return text
        except Exception as e:
            return f"Error fetching URL: {e}"


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web using Brave Search API."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Number of results (default: 5)"},
        },
        "required": ["query"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    async def execute(self, params: dict) -> str:
        query = params["query"]
        count = params.get("count", 5)
        if not self.api_key:
            return "Error: web search API key not configured"
        logger.info(f"Searching: {query}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": count},
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": self.api_key,
                    },
                )
            if resp.status_code != 200:
                return f"Error: search API returned HTTP {resp.status_code}"
            data = resp.json()
            results = data.get("web", {}).get("results", [])
            if not results:
                return "No results found."
            lines = []
            for r in results:
                lines.append(f"**{r['title']}**")
                lines.append(f"  URL: {r['url']}")
                lines.append(f"  {r.get('description', '')}")
                lines.append("")
            return "\n".join(lines).strip()
        except Exception as e:
            return f"Error searching: {e}"
