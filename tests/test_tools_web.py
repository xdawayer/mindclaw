# input: mindclaw.tools.web
# output: 网页工具测试
# pos: 工具层网页操作测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_web_fetch_returns_content():
    from mindclaw.tools.web import WebFetchTool
    tool = WebFetchTool()

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>Hello World</p></body></html>"
    mock_response.headers = {"content-type": "text/html"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await tool.execute({"url": "https://example.com"})

    assert "Hello World" in result


@pytest.mark.asyncio
async def test_web_fetch_truncates_long_content():
    from mindclaw.tools.web import WebFetchTool
    tool = WebFetchTool(max_chars=100)

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>" + "x" * 1000 + "</p></body></html>"
    mock_response.headers = {"content-type": "text/html"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await tool.execute({"url": "https://example.com"})

    assert len(result) <= 150


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
