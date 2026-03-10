# input: knowledge/notion.py
# output: NotionKnowledge 测试
# pos: Phase 9.2 Notion API 集成测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for NotionKnowledge — Notion API read/create/update/search via httpx."""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

from mindclaw.knowledge.notion import NotionKnowledge


@pytest.fixture
def notion() -> NotionKnowledge:
    return NotionKnowledge(api_key="test-secret-key")


# ---- Mock helpers ----


def _mock_response(status_code: int, data: dict) -> MagicMock:
    """Create a mock httpx.Response with .status_code, .json(), .raise_for_status()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def _patch_client(notion: NotionKnowledge, mock_client: MagicMock):
    """Patch _client to yield mock_client as an async context manager."""

    @asynccontextmanager
    async def fake_client():
        yield mock_client

    return patch.object(notion, "_client", fake_client)


_VALID_ID = "a" * 32
_VALID_ID_2 = "b" * 32


def _page_response(page_id: str = _VALID_ID, title: str = "Test Page") -> dict:
    return {
        "id": page_id,
        "object": "page",
        "properties": {"title": {"title": [{"plain_text": title}]}},
    }


def _block_children_response(blocks: list[dict] | None = None) -> dict:
    if blocks is None:
        blocks = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello world"}]}},
            {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Section"}]}},
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"plain_text": "Item one"}]},
            },
            {
                "type": "code",
                "code": {"rich_text": [{"plain_text": "print('hi')"}], "language": "python"},
            },
        ]
    return {"results": blocks, "has_more": False}


def _search_response(pages: list[dict] | None = None) -> dict:
    if pages is None:
        pages = [_page_response(_VALID_ID, "Result A"), _page_response(_VALID_ID_2, "Result B")]
    return {"results": pages, "has_more": False}


def _database_list_response() -> dict:
    return {
        "results": [
            {"id": "db-1", "object": "database", "title": [{"plain_text": "Tasks"}]},
            {"id": "db-2", "object": "database", "title": [{"plain_text": "Notes"}]},
        ],
        "has_more": False,
    }


# ---- read_page ----


class TestReadPage:
    @pytest.mark.asyncio
    async def test_read_page_returns_markdown(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_get(url, **kwargs):
            if "/pages/" in url:
                return _mock_response(200, _page_response())
            return _mock_response(200, _block_children_response())

        mock_client.get = mock_get

        with _patch_client(notion, mock_client):
            result = await notion.read_page(_VALID_ID)

        assert "Hello world" in result
        assert "## Section" in result
        assert "- Item one" in result

    @pytest.mark.asyncio
    async def test_read_page_not_found(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_get(url, **kwargs):
            return _mock_response(404, {"message": "Not found"})

        mock_client.get = mock_get

        with _patch_client(notion, mock_client):
            with pytest.raises(ValueError, match="not found"):
                await notion.read_page(_VALID_ID)

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self) -> None:
        notion = NotionKnowledge(api_key="")
        with pytest.raises(ValueError, match="API key"):
            await notion.read_page("page-123")


# ---- create_page ----


class TestCreatePage:
    @pytest.mark.asyncio
    async def test_create_page_returns_id(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_post(url, **kwargs):
            return _mock_response(200, {"id": "new-page-id", "object": "page"})

        mock_client.post = mock_post

        with _patch_client(notion, mock_client):
            page_id = await notion.create_page(
                parent_id=_VALID_ID,
                title="New Page",
                content="Some content here.",
            )

        assert page_id == "new-page-id"

    @pytest.mark.asyncio
    async def test_create_page_api_error(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_post(url, **kwargs):
            return _mock_response(400, {"message": "Invalid parent"})

        mock_client.post = mock_post

        with _patch_client(notion, mock_client):
            with pytest.raises(ValueError, match="Invalid parent"):
                await notion.create_page(
                    "a" * 32, "Title", "Content"
                )

    @pytest.mark.asyncio
    async def test_create_page_rejects_invalid_parent_id(
        self, notion: NotionKnowledge
    ) -> None:
        with pytest.raises(ValueError, match="Invalid Notion parent_id"):
            await notion.create_page("bad-parent", "Title", "Content")


# ---- update_page ----


class TestUpdatePage:
    @pytest.mark.asyncio
    async def test_update_page_success(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_patch(url, **kwargs):
            return _mock_response(200, {"id": "a" * 32, "object": "page"})

        mock_client.patch = mock_patch

        with _patch_client(notion, mock_client):
            await notion.update_page("a" * 32, {"title": {"title": []}})

    @pytest.mark.asyncio
    async def test_update_page_api_error(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_patch(url, **kwargs):
            return _mock_response(400, {"message": "Bad request"})

        mock_client.patch = mock_patch

        with _patch_client(notion, mock_client):
            with pytest.raises(ValueError, match="Bad request"):
                await notion.update_page("a" * 32, {})

    @pytest.mark.asyncio
    async def test_update_page_rejects_invalid_id(
        self, notion: NotionKnowledge
    ) -> None:
        with pytest.raises(ValueError, match="Invalid Notion page_id"):
            await notion.update_page("../../evil", {})


# ---- ID validation ----


class TestIdValidation:
    @pytest.mark.asyncio
    async def test_read_page_rejects_path_traversal(
        self, notion: NotionKnowledge
    ) -> None:
        with pytest.raises(ValueError, match="Invalid Notion page_id"):
            await notion.read_page("../../admin")

    @pytest.mark.asyncio
    async def test_valid_uuid_accepted(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_get(url, **kwargs):
            if "/pages/" in url:
                return _mock_response(200, _page_response())
            return _mock_response(200, _block_children_response())

        mock_client.get = mock_get

        with _patch_client(notion, mock_client):
            result = await notion.read_page("a" * 32)

        assert "Hello world" in result


# ---- search ----


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_post(url, **kwargs):
            return _mock_response(200, _search_response())

        mock_client.post = mock_post

        with _patch_client(notion, mock_client):
            results = await notion.search("test query")

        assert len(results) == 2
        assert results[0]["id"] == _VALID_ID
        assert results[0]["title"] == "Result A"

    @pytest.mark.asyncio
    async def test_search_empty_results(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_post(url, **kwargs):
            return _mock_response(200, _search_response(pages=[]))

        mock_client.post = mock_post

        with _patch_client(notion, mock_client):
            results = await notion.search("nothing here")

        assert results == []


# ---- list_databases ----


class TestListDatabases:
    @pytest.mark.asyncio
    async def test_list_databases_returns_dbs(self, notion: NotionKnowledge) -> None:
        mock_client = MagicMock()

        async def mock_post(url, **kwargs):
            return _mock_response(200, _database_list_response())

        mock_client.post = mock_post

        with _patch_client(notion, mock_client):
            dbs = await notion.list_databases()

        assert len(dbs) == 2
        assert dbs[0]["id"] == "db-1"
        assert dbs[0]["title"] == "Tasks"


# ---- blocks_to_markdown ----


class TestBlocksToMarkdown:
    def test_paragraph(self, notion: NotionKnowledge) -> None:
        blocks = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello"}]}}
        ]
        md = notion.blocks_to_markdown(blocks)
        assert md.strip() == "Hello"

    def test_heading(self, notion: NotionKnowledge) -> None:
        blocks = [
            {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title"}]}}
        ]
        md = notion.blocks_to_markdown(blocks)
        assert "# Title" in md

    def test_code_block(self, notion: NotionKnowledge) -> None:
        blocks = [
            {
                "type": "code",
                "code": {
                    "rich_text": [{"plain_text": "x = 1"}],
                    "language": "python",
                },
            }
        ]
        md = notion.blocks_to_markdown(blocks)
        assert "```python" in md
        assert "x = 1" in md

    def test_bulleted_list(self, notion: NotionKnowledge) -> None:
        blocks = [
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"plain_text": "item"}]},
            }
        ]
        md = notion.blocks_to_markdown(blocks)
        assert "- item" in md

    def test_numbered_list(self, notion: NotionKnowledge) -> None:
        blocks = [
            {
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"plain_text": "step"}]},
            }
        ]
        md = notion.blocks_to_markdown(blocks)
        assert "1. step" in md

    def test_quote(self, notion: NotionKnowledge) -> None:
        blocks = [
            {"type": "quote", "quote": {"rich_text": [{"plain_text": "wise words"}]}}
        ]
        md = notion.blocks_to_markdown(blocks)
        assert "> wise words" in md

    def test_unsupported_type_skipped(self, notion: NotionKnowledge) -> None:
        blocks = [
            {"type": "divider", "divider": {}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "text"}]}},
        ]
        md = notion.blocks_to_markdown(blocks)
        assert "text" in md

    def test_to_do_unchecked(self, notion: NotionKnowledge) -> None:
        blocks = [
            {
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"plain_text": "buy milk"}],
                    "checked": False,
                },
            }
        ]
        md = notion.blocks_to_markdown(blocks)
        assert "- [ ] buy milk" in md

    def test_to_do_checked(self, notion: NotionKnowledge) -> None:
        blocks = [
            {
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"plain_text": "done task"}],
                    "checked": True,
                },
            }
        ]
        md = notion.blocks_to_markdown(blocks)
        assert "- [x] done task" in md


# ---- create_page with page parent ----


class TestCreatePageParent:
    @pytest.mark.asyncio
    async def test_create_page_under_page_parent(
        self, notion: NotionKnowledge
    ) -> None:
        mock_client = MagicMock()
        captured_body = {}

        async def mock_post(url, **kwargs):
            captured_body.update(kwargs.get("json", {}))
            return _mock_response(200, {"id": "child-page-" + "a" * 24, "object": "page"})

        mock_client.post = mock_post

        with _patch_client(notion, mock_client):
            page_id = await notion.create_page(
                parent_id=_VALID_ID,
                title="Child Page",
                content="Under a page, not a database.",
                parent_type="page",
            )

        assert page_id.startswith("child-page-")
        assert "page_id" in captured_body["parent"]
        assert "database_id" not in captured_body["parent"]

    @pytest.mark.asyncio
    async def test_create_page_default_parent_is_database(
        self, notion: NotionKnowledge
    ) -> None:
        mock_client = MagicMock()
        captured_body = {}

        async def mock_post(url, **kwargs):
            captured_body.update(kwargs.get("json", {}))
            return _mock_response(200, {"id": "new-" + "a" * 29, "object": "page"})

        mock_client.post = mock_post

        with _patch_client(notion, mock_client):
            await notion.create_page(
                parent_id=_VALID_ID,
                title="DB Page",
                content="Under a database.",
            )

        assert "database_id" in captured_body["parent"]


# ---- API key warning ----


class TestApiKeyWarning:
    def test_empty_api_key_logs_warning(self) -> None:
        from loguru import logger

        messages: list[str] = []
        handler_id = logger.add(lambda msg: messages.append(str(msg)), level="WARNING")
        try:
            NotionKnowledge(api_key="")
        finally:
            logger.remove(handler_id)

        assert any("API key" in m for m in messages)
