# input: mindclaw.oauth.manager
# output: OAuth 管理器测试
# pos: OAuth 流程管理测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindclaw.oauth.manager import OAuthManager
from mindclaw.oauth.token_store import OAuthTokenInfo, OAuthTokenStore


@pytest.fixture
def token_store(tmp_path):
    store = OAuthTokenStore(
        store_path=tmp_path / "tokens.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    return store


@pytest.fixture
def manager(token_store):
    return OAuthManager(token_store=token_store)


class TestOAuthManagerGetAccessToken:
    @pytest.mark.asyncio
    async def test_returns_valid_token(self, manager, token_store):
        token_store.set_token(
            "openai",
            OAuthTokenInfo(
                access_token="valid_token",
                refresh_token="refresh_t",
                token_type="Bearer",
                expires_at=time.time() + 3600,
            ),
        )
        result = await manager.get_access_token("openai")
        assert result == "valid_token"

    @pytest.mark.asyncio
    async def test_raises_if_no_token(self, manager):
        with pytest.raises(ValueError, match="No OAuth token"):
            await manager.get_access_token("openai")

    @pytest.mark.asyncio
    async def test_refreshes_expired_token(self, manager, token_store):
        token_store.set_token(
            "openai",
            OAuthTokenInfo(
                access_token="old_token",
                refresh_token="refresh_t",
                token_type="Bearer",
                expires_at=time.time() - 100,
            ),
        )
        new_token = OAuthTokenInfo(
            access_token="new_token",
            refresh_token="new_refresh",
            token_type="Bearer",
            expires_at=time.time() + 3600,
        )
        with patch.object(manager, "refresh_token", new_callable=AsyncMock, return_value=new_token):
            result = await manager.get_access_token("openai")
        assert result == "new_token"


class TestOAuthManagerRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_posts_to_token_url(self, manager, token_store):
        token_store.set_token(
            "openai",
            OAuthTokenInfo(
                access_token="old",
                refresh_token="refresh_abc",
                token_type="Bearer",
                expires_at=time.time() - 100,
            ),
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_token",
            "refresh_token": "new_refresh",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        with patch("httpx.AsyncClient.post", return_value=mock_response):
            result = await manager.refresh_token("openai")
        assert result.access_token == "refreshed_token"
        # Should also be saved in store
        stored = token_store.get_token("openai")
        assert stored is not None
        assert stored.access_token == "refreshed_token"

    @pytest.mark.asyncio
    async def test_refresh_raises_without_refresh_token(self, manager, token_store):
        token_store.set_token(
            "openai",
            OAuthTokenInfo(
                access_token="old",
                refresh_token=None,
                token_type="Bearer",
                expires_at=time.time() - 100,
            ),
        )
        with pytest.raises(ValueError, match="No refresh token"):
            await manager.refresh_token("openai")


class TestOAuthManagerAuthorizationUrl:
    def test_generates_url(self, manager):
        url, state, verifier = manager.build_authorization_url("openai")
        assert "https://auth.openai.com/oauth/authorize" in url
        assert "client_id=app_EMoamEEZ73f0CkXaXp7hrann" in url
        assert "code_challenge_method=S256" in url
        assert f"state={state}" in url
        assert len(verifier) >= 43
