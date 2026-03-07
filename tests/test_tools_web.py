# input: mindclaw.tools.web
# output: 网页工具测试
# pos: 工具层网页操作测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _async_iter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_web_fetch_returns_content():
    from mindclaw.tools.web import WebFetchTool

    tool = WebFetchTool()

    html_bytes = b"<html><body><p>Hello World</p></body></html>"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.aiter_bytes = lambda: _async_iter([html_bytes])

    @asynccontextmanager
    async def fake_stream(method, url):
        yield mock_resp

    with (
        patch("mindclaw.tools.web._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.stream = fake_stream
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await tool.execute({"url": "https://example.com"})

    assert "Hello World" in result


@pytest.mark.asyncio
async def test_web_fetch_truncates_long_content():
    from mindclaw.tools.web import WebFetchTool

    tool = WebFetchTool(max_chars=100)

    html_bytes = b"<html><body><p>" + b"x" * 1000 + b"</p></body></html>"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.aiter_bytes = lambda: _async_iter([html_bytes])

    @asynccontextmanager
    async def fake_stream(method, url):
        yield mock_resp

    with (
        patch("mindclaw.tools.web._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.stream = fake_stream
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await tool.execute({"url": "https://example.com"})

    assert len(result) <= 150


@pytest.mark.asyncio
async def test_web_fetch_rejects_private_url():
    """SSRF prevention: reject URLs resolving to private addresses."""
    from mindclaw.tools.web import WebFetchTool

    tool = WebFetchTool()

    with patch(
        "mindclaw.tools.web.socket.getaddrinfo",
        return_value=[(None, None, None, None, ("127.0.0.1", 0))],
    ):
        result = await tool.execute({"url": "https://internal.corp"})

    assert "private" in result.lower() or "internal" in result.lower()


@pytest.mark.asyncio
async def test_web_search_returns_results():
    from mindclaw.tools.web import WebSearchTool

    tool = WebSearchTool(api_key="test-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"title": "Result 1", "url": "https://a.com", "description": "Desc 1"},
                {"title": "Result 2", "url": "https://b.com", "description": "Desc 2"},
            ]
        }
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await tool.execute({"query": "python asyncio"})

    assert "Result 1" in result
    assert "https://a.com" in result
