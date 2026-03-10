# input: mindclaw.tools.api_call, mindclaw.config.schema
# output: ApiCallTool 安全 HTTP 调用工具测试
# pos: 验证 URL 白名单、SSRF 防护、Auth Profile 注入、响应截断
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ────────────────────────────────────────────────────────────────

def _make_tool(
    allowlist: list[str] | None = None,
    auth_profiles: dict | None = None,
    max_chars: int = 5000,
):
    from mindclaw.config.schema import AuthProfileConfig
    from mindclaw.tools.api_call import ApiCallTool

    profiles = {}
    if auth_profiles:
        for name, cfg in auth_profiles.items():
            profiles[name] = AuthProfileConfig(**cfg)

    return ApiCallTool(
        url_allowlist=allowlist or [],
        auth_profiles=profiles,
        max_chars=max_chars,
    )


def _mock_response(status: int = 200, body: str = "ok", headers: dict | None = None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = body
    resp.headers = headers or {"content-type": "application/json"}
    return resp


# ── Risk level ─────────────────────────────────────────────────────────────

def test_risk_level_dangerous():
    from mindclaw.tools.base import RiskLevel

    tool = _make_tool(allowlist=["https://api.example.com"])
    assert tool.risk_level == RiskLevel.DANGEROUS


# ── Basic GET ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_basic_get():
    """GET request is sent to the correct URL with no extra headers."""
    tool = _make_tool(allowlist=["https://api.example.com"])
    mock_resp = _mock_response(200, '{"data": 1}')

    with (
        patch("mindclaw.tools.api_call._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await tool.execute({"url": "https://api.example.com/v1/items"})

    mock_client.request.assert_called_once()
    call_kwargs = mock_client.request.call_args
    assert call_kwargs.args[0].upper() == "GET"
    assert call_kwargs.args[1] == "https://api.example.com/v1/items"
    assert "200" in result
    assert '{"data": 1}' in result


# ── POST with body ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_with_body():
    """POST body is forwarded as the request content."""
    tool = _make_tool(allowlist=["https://api.example.com"])
    mock_resp = _mock_response(201, "created")

    with (
        patch("mindclaw.tools.api_call._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await tool.execute({
            "url": "https://api.example.com/v1/items",
            "method": "POST",
            "body": '{"name": "thing"}',
        })

    call_kwargs = mock_client.request.call_args
    assert call_kwargs.args[0].upper() == "POST"
    assert call_kwargs.kwargs.get("content") == '{"name": "thing"}'
    assert "201" in result


# ── Bearer auth profile ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bearer_auth_profile():
    """Bearer profile injects 'Authorization: Bearer <token>' header."""
    tool = _make_tool(
        allowlist=["https://api.example.com"],
        auth_profiles={
            "myapi": {"profile_type": "bearer", "value": "secret-token-xyz"},
        },
    )
    mock_resp = _mock_response(200, "ok")

    with (
        patch("mindclaw.tools.api_call._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await tool.execute({
            "url": "https://api.example.com/protected",
            "auth_profile": "myapi",
        })

    call_kwargs = mock_client.request.call_args
    sent_headers = call_kwargs.kwargs.get("headers", {})
    assert sent_headers.get("Authorization") == "Bearer secret-token-xyz"
    # Token must NOT appear in result text (security requirement)
    assert "secret-token-xyz" not in result


# ── Header auth profile ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_header_auth_profile():
    """Custom-header profile injects the specified header."""
    tool = _make_tool(
        allowlist=["https://api.example.com"],
        auth_profiles={
            "custom": {
                "profile_type": "header",
                "header_name": "X-Api-Key",
                "value": "my-api-key-secret",
            },
        },
    )
    mock_resp = _mock_response(200, "ok")

    with (
        patch("mindclaw.tools.api_call._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await tool.execute({
            "url": "https://api.example.com/data",
            "auth_profile": "custom",
        })

    call_kwargs = mock_client.request.call_args
    sent_headers = call_kwargs.kwargs.get("headers", {})
    assert sent_headers.get("X-Api-Key") == "my-api-key-secret"
    assert "my-api-key-secret" not in result


# ── Basic auth profile ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_basic_auth_profile():
    """Basic auth profile injects 'Authorization: Basic <base64>' header."""
    import base64

    tool = _make_tool(
        allowlist=["https://api.example.com"],
        auth_profiles={
            "basicauth": {
                "profile_type": "basic",
                "value": "user:password123",
            },
        },
    )
    mock_resp = _mock_response(200, "ok")

    with (
        patch("mindclaw.tools.api_call._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await tool.execute({
            "url": "https://api.example.com/secure",
            "auth_profile": "basicauth",
        })

    call_kwargs = mock_client.request.call_args
    sent_headers = call_kwargs.kwargs.get("headers", {})
    expected = "Basic " + base64.b64encode(b"user:password123").decode()
    assert sent_headers.get("Authorization") == expected
    # Raw credential must NOT appear in result
    assert "password123" not in result
    assert "user:password123" not in result


# ── URL allowlist: blocks ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_url_allowlist_blocks():
    """URL not matching any allowlist prefix is rejected without making a request."""
    tool = _make_tool(allowlist=["https://api.example.com"])

    with patch("mindclaw.tools.api_call._is_safe_url", return_value=True):
        result = await tool.execute({"url": "https://evil.com/steal"})

    assert "not allowed" in result.lower()


# ── URL allowlist: allows ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_url_allowlist_allows():
    """URL matching an allowlist prefix (prefix check, not substring) proceeds."""
    tool = _make_tool(allowlist=["https://api.example.com/v1"])
    mock_resp = _mock_response(200, "allowed")

    with (
        patch("mindclaw.tools.api_call._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await tool.execute({"url": "https://api.example.com/v1/users"})

    assert "200" in result
    assert "allowed" in result


# ── Empty allowlist blocks all ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_allowlist_blocks_all():
    """When no allowlist entries are configured, ALL requests are blocked."""
    tool = _make_tool(allowlist=[])

    result = await tool.execute({"url": "https://api.example.com/anything"})

    assert "not allowed" in result.lower()


# ── SSRF: private IP ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ssrf_protection_blocks_private_ip():
    """SSRF: URLs that resolve to private IPs (127.0.0.1, 10.x, 192.168.x) are blocked."""
    tool = _make_tool(allowlist=["http://internal.corp"])

    with patch(
        "mindclaw.tools._ssrf.socket.getaddrinfo",
        return_value=[(None, None, None, None, ("192.168.1.1", 0))],
    ):
        result = await tool.execute({"url": "http://internal.corp/secret"})

    assert "private" in result.lower() or "internal" in result.lower()


# ── SSRF: localhost ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ssrf_protection_blocks_localhost():
    """SSRF: 'localhost' and loopback addresses are blocked."""
    tool = _make_tool(allowlist=["http://localhost:8080"])

    with patch(
        "mindclaw.tools._ssrf.socket.getaddrinfo",
        return_value=[(None, None, None, None, ("127.0.0.1", 0))],
    ):
        result = await tool.execute({"url": "http://localhost:8080/admin"})

    assert "private" in result.lower() or "internal" in result.lower()


# ── Response truncation ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_truncation():
    """Responses longer than max_chars are truncated with a marker."""
    long_body = "x" * 10_000
    tool = _make_tool(allowlist=["https://api.example.com"], max_chars=200)
    mock_resp = _mock_response(200, long_body)

    with (
        patch("mindclaw.tools.api_call._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await tool.execute({"url": "https://api.example.com/big"})

    # Result should be truncated (well under 10k + headers)
    assert len(result) < 1000
    assert "truncated" in result.lower()


# ── Unknown auth profile ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_auth_profile():
    """Referencing a non-existent auth profile returns an error without making a request."""
    tool = _make_tool(allowlist=["https://api.example.com"])

    with patch("mindclaw.tools.api_call._is_safe_url", return_value=True):
        result = await tool.execute({
            "url": "https://api.example.com/data",
            "auth_profile": "nonexistent",
        })

    assert "error" in result.lower() or "not found" in result.lower() or "unknown" in result.lower()
    # Should not have made any HTTP request (no mock needed)


# ── Method validation ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_method_validation():
    """Invalid HTTP method returns an error without making a request."""
    tool = _make_tool(allowlist=["https://api.example.com"])

    with patch("mindclaw.tools.api_call._is_safe_url", return_value=True):
        result = await tool.execute({
            "url": "https://api.example.com/data",
            "method": "INJECT; rm -rf /",
        })

    assert "error" in result.lower() or "invalid" in result.lower() or "method" in result.lower()


# ── Allowlist is prefix-matched, not substring ──────────────────────────────

@pytest.mark.asyncio
async def test_url_allowlist_prefix_not_substring():
    """An allowlist entry must match as a URL prefix, not an embedded substring.

    e.g., allowlist=['https://api.example.com'] must NOT allow
    'https://evil.com/https://api.example.com/bypass'.
    """
    tool = _make_tool(allowlist=["https://api.example.com"])

    result = await tool.execute({
        "url": "https://evil.com/https://api.example.com/bypass",
    })

    assert "not allowed" in result.lower() or "allowlist" in result.lower()


@pytest.mark.asyncio
async def test_url_allowlist_blocks_subdomain_spoof():
    """Allowlist 'https://api.example.com' must NOT allow 'https://api.example.comevil.tld'."""
    tool = _make_tool(allowlist=["https://api.example.com"])

    result = await tool.execute({
        "url": "https://api.example.comevil.tld/steal",
    })

    assert "not allowed" in result.lower()


# ── Path traversal bypass ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_url_allowlist_blocks_path_traversal():
    """Allowlist '/v1' must NOT allow '/v1/../../admin' after normalization."""
    tool = _make_tool(allowlist=["https://api.example.com/v1"])

    result = await tool.execute({
        "url": "https://api.example.com/v1/../../../admin",
    })

    assert "not allowed" in result.lower()


@pytest.mark.asyncio
async def test_url_allowlist_blocks_percent_encoded_traversal():
    """Allowlist '/v1' must NOT allow '/v1/%2e%2e/admin' after decoding."""
    tool = _make_tool(allowlist=["https://api.example.com/v1"])

    result = await tool.execute({
        "url": "https://api.example.com/v1/%2e%2e/admin",
    })

    assert "not allowed" in result.lower()


@pytest.mark.asyncio
async def test_url_allowlist_strips_userinfo_from_error():
    """Error messages must NOT leak userinfo (user:password) from the URL."""
    tool = _make_tool(allowlist=["https://api.example.com"])

    result = await tool.execute({
        "url": "https://user:secret@evil.com/steal",
    })

    assert "secret" not in result
    assert "user:" not in result


# ── No redirects ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_redirects_follow():
    """httpx client is always created with follow_redirects=False."""
    tool = _make_tool(allowlist=["https://api.example.com"])
    mock_resp = _mock_response(200, "ok")

    with (
        patch("mindclaw.tools.api_call._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        await tool.execute({"url": "https://api.example.com/data"})

    # Verify httpx.AsyncClient was constructed with follow_redirects=False
    init_kwargs = mock_cls.call_args.kwargs
    assert init_kwargs.get("follow_redirects") is False


# ── AuthProfileConfig schema ────────────────────────────────────────────────

def test_auth_profile_config_bearer():
    from mindclaw.config.schema import AuthProfileConfig

    cfg = AuthProfileConfig(profileType="bearer", value="tok")
    assert cfg.profile_type == "bearer"
    assert cfg.value == "tok"
    assert cfg.header_name == "Authorization"


def test_auth_profile_config_header_custom():
    from mindclaw.config.schema import AuthProfileConfig

    cfg = AuthProfileConfig(profileType="header", headerName="X-Secret", value="abc")
    assert cfg.header_name == "X-Secret"


def test_auth_profile_config_populate_by_name():
    """Fields can be set via snake_case names too."""
    from mindclaw.config.schema import AuthProfileConfig

    cfg = AuthProfileConfig(profile_type="bearer", value="tok")
    assert cfg.profile_type == "bearer"


def test_tools_config_api_call_fields():
    """ToolsConfig includes api_call_auth_profiles and api_call_url_allowlist."""
    from mindclaw.config.schema import ToolsConfig

    cfg = ToolsConfig()
    assert cfg.api_call_auth_profiles == {}
    assert cfg.api_call_url_allowlist == []


def test_tools_config_api_call_alias():
    """ToolsConfig fields accept camelCase aliases."""
    from mindclaw.config.schema import AuthProfileConfig, ToolsConfig

    profile = AuthProfileConfig(profileType="bearer", value="t")
    cfg = ToolsConfig(
        apiCallAuthProfiles={"svc": profile},
        apiCallUrlAllowlist=["https://example.com"],
    )
    assert "svc" in cfg.api_call_auth_profiles
    assert cfg.api_call_url_allowlist == ["https://example.com"]
