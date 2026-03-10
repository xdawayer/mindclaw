# input: httpx, re
# output: 导出 NotionKnowledge
# pos: Notion API 集成 (读/写/搜索/列数据库)，Phase 9.2
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Notion API integration for MindClaw.

Uses httpx to call Notion API v1 directly — no extra SDK dependency.
Converts Notion blocks to Markdown for human-readable output.
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from loguru import logger

_NOTION_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_NOTION_ID_RE = re.compile(r"^[a-f0-9\-]{32,36}$")


def _validate_notion_id(value: str, label: str = "ID") -> None:
    """Reject IDs that don't match the expected UUID-like format."""
    if not _NOTION_ID_RE.match(value):
        raise ValueError(f"Invalid Notion {label}: {value}")


class NotionKnowledge:
    """Interact with Notion pages, databases, and search."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        if not api_key:
            logger.warning("Notion API key not configured — all API calls will fail")

    # ------------------------------------------------------------------
    # HTTP client
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        """Yield an httpx client with Notion headers."""
        async with httpx.AsyncClient(
            base_url=_NOTION_BASE,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Notion-Version": _NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=15.0,
        ) as client:
            yield client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def read_page(self, page_id: str) -> str:
        """Read a Notion page and return its content as Markdown.

        Note: only the first page of block children is returned (no pagination).
        """
        self._require_api_key()
        _validate_notion_id(page_id, "page_id")

        async with self._client() as client:
            # 1. Get page metadata
            resp = await client.get(f"/pages/{page_id}")
            if resp.status_code == 404:
                raise ValueError(f"Page not found: {page_id}")
            resp.raise_for_status()

            # 2. Get block children
            resp_blocks = await client.get(f"/blocks/{page_id}/children")
            resp_blocks.raise_for_status()

        blocks = resp_blocks.json().get("results", [])
        return self.blocks_to_markdown(blocks)

    async def create_page(
        self,
        parent_id: str,
        title: str,
        content: str,
        parent_type: str = "database",
    ) -> str:
        """Create a new page under *parent_id*.

        *parent_type* is ``"database"`` (default) or ``"page"``.
        Returns the new page ID.
        """
        self._require_api_key()
        _validate_notion_id(parent_id, "parent_id")

        if parent_type == "page":
            parent_key = "page_id"
        else:
            parent_key = "database_id"

        body = {
            "parent": {parent_key: parent_id},
            "properties": {
                "title": {"title": [{"text": {"content": title}}]},
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}],
                    },
                }
            ],
        }

        async with self._client() as client:
            resp = await client.post("/pages", json=body)

        data = resp.json()
        if resp.status_code not in (200, 201):
            raise ValueError(data.get("message", f"API error {resp.status_code}"))
        return data["id"]

    async def update_page(self, page_id: str, properties: dict) -> None:
        """Update page properties."""
        self._require_api_key()
        _validate_notion_id(page_id, "page_id")

        async with self._client() as client:
            resp = await client.patch(f"/pages/{page_id}", json={"properties": properties})

        if resp.status_code not in (200, 201):
            data = resp.json()
            raise ValueError(data.get("message", f"API error {resp.status_code}"))

    async def search(self, query: str) -> list[dict]:
        """Search Notion. Returns list of dicts with id and title."""
        self._require_api_key()

        async with self._client() as client:
            resp = await client.post("/search", json={"query": query})
        resp.raise_for_status()

        results: list[dict] = []
        for item in resp.json().get("results", []):
            title = _extract_title(item)
            results.append({"id": item["id"], "title": title})
        return results

    async def list_databases(self) -> list[dict]:
        """List databases accessible to the integration."""
        self._require_api_key()

        async with self._client() as client:
            resp = await client.post(
                "/search",
                json={"filter": {"value": "database", "property": "object"}},
            )
        resp.raise_for_status()

        dbs: list[dict] = []
        for item in resp.json().get("results", []):
            title_parts = item.get("title", [])
            title = title_parts[0].get("plain_text", "") if title_parts else ""
            dbs.append({"id": item["id"], "title": title})
        return dbs

    # ------------------------------------------------------------------
    # Block → Markdown conversion
    # ------------------------------------------------------------------

    @staticmethod
    def blocks_to_markdown(blocks: list[dict]) -> str:
        """Convert a list of Notion blocks to Markdown."""
        lines: list[str] = []
        numbered_counter = 0

        for block in blocks:
            block_type = block.get("type", "")
            data = block.get(block_type, {})
            text = _rich_text_to_plain(data.get("rich_text", []))

            if block_type == "paragraph":
                lines.append(text)
                numbered_counter = 0
            elif block_type.startswith("heading_"):
                level = int(block_type[-1])
                lines.append(f"{'#' * level} {text}")
                numbered_counter = 0
            elif block_type == "bulleted_list_item":
                lines.append(f"- {text}")
                numbered_counter = 0
            elif block_type == "numbered_list_item":
                numbered_counter += 1
                lines.append(f"{numbered_counter}. {text}")
            elif block_type == "quote":
                lines.append(f"> {text}")
                numbered_counter = 0
            elif block_type == "code":
                lang = data.get("language", "")
                lines.append(f"```{lang}")
                lines.append(text)
                lines.append("```")
                numbered_counter = 0
            elif block_type == "to_do":
                checked = data.get("checked", False)
                mark = "x" if checked else " "
                lines.append(f"- [{mark}] {text}")
                numbered_counter = 0
            else:
                # Skip unsupported blocks (divider, image, embed, etc.)
                logger.debug(f"Skipping unsupported Notion block type: {block_type}")
                numbered_counter = 0

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_api_key(self) -> None:
        if not self._api_key:
            raise ValueError("Notion API key not configured")


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _rich_text_to_plain(rich_text: list[dict]) -> str:
    """Extract plain text from Notion rich_text array."""
    return "".join(part.get("plain_text", "") for part in rich_text)


def _extract_title(page: dict) -> str:
    """Extract title from a Notion page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if "title" in prop:
            parts = prop["title"]
            if parts:
                return parts[0].get("plain_text", "")
    return ""
