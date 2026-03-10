# input: oauth/token_store, oauth/providers, oauth/pkce, httpx
# output: 导出 OAuthManager
# pos: OAuth 流程管理器，处理授权 URL 生成、token 交换、API token exchange 和自动刷新
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import secrets
import time
from urllib.parse import urlencode

import httpx
from loguru import logger

from .pkce import generate_pkce_pair
from .providers import OAUTH_PROVIDERS
from .token_store import OAuthTokenInfo, OAuthTokenStore

class OAuthManager:
    """Manages OAuth authorization flows, token exchange, and refresh."""

    def __init__(self, token_store: OAuthTokenStore) -> None:
        self._token_store = token_store
        self._refresh_lock: dict[str, asyncio.Lock] = {}

    async def get_access_token(self, provider: str) -> str:
        """Get a valid access token, refreshing if expired."""
        token_info = self._token_store.get_token(provider)
        if token_info is None:
            raise ValueError(f"No OAuth token found for provider '{provider}'")

        if token_info.is_expired():
            token_info = await self.refresh_token(provider)

        return token_info.access_token

    async def refresh_token(self, provider: str) -> OAuthTokenInfo:
        """Refresh an expired OAuth token."""
        lock = self._refresh_lock.setdefault(provider, asyncio.Lock())
        async with lock:
            # Re-check after acquiring lock (another coroutine may have refreshed)
            token_info = self._token_store.get_token(provider)
            if token_info is not None and not token_info.is_expired():
                return token_info

            if token_info is None or token_info.refresh_token is None:
                raise ValueError(
                    f"No refresh token available for provider '{provider}'"
                )

            provider_config = OAUTH_PROVIDERS.get(provider)
            if provider_config is None:
                raise ValueError(f"Unknown OAuth provider '{provider}'")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    provider_config.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": token_info.refresh_token,
                        "client_id": provider_config.client_id,
                    },
                )

            if response.status_code != 200:
                logger.error(
                    f"OAuth token refresh failed for {provider}: "
                    f"status={response.status_code}"
                )
                raise ValueError(
                    f"Token refresh failed for '{provider}': {response.status_code}"
                )

            data = response.json()

            new_token = OAuthTokenInfo(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", token_info.refresh_token),
                id_token=data.get("id_token"),
                token_type=data.get("token_type", "Bearer"),
                expires_at=time.time() + data.get("expires_in", 3600),
                scopes=token_info.scopes,
            )
            self._token_store.set_token(provider, new_token)
            logger.info(f"OAuth token refreshed for provider '{provider}'")
            return new_token

    def build_authorization_url(
        self, provider: str
    ) -> tuple[str, str, str]:
        """Build OAuth authorization URL with PKCE.

        Returns:
            (authorization_url, state, code_verifier) tuple.
        """
        provider_config = OAUTH_PROVIDERS.get(provider)
        if provider_config is None:
            raise ValueError(f"Unknown OAuth provider '{provider}'")

        state = secrets.token_urlsafe(32)
        verifier, challenge = generate_pkce_pair()

        params = {
            "response_type": "code",
            "client_id": provider_config.client_id,
            "redirect_uri": f"http://localhost:{provider_config.redirect_port}/auth/callback",
            "scope": " ".join(provider_config.scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
        }

        url = f"{provider_config.auth_url}?{urlencode(params)}"
        return url, state, verifier

    async def exchange_code(
        self,
        provider: str,
        code: str,
        verifier: str,
    ) -> OAuthTokenInfo:
        """Exchange authorization code for access/refresh tokens."""
        provider_config = OAUTH_PROVIDERS.get(provider)
        if provider_config is None:
            raise ValueError(f"Unknown OAuth provider '{provider}'")

        redirect_uri = (
            f"http://localhost:{provider_config.redirect_port}/auth/callback"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider_config.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": provider_config.client_id,
                    "code_verifier": verifier,
                },
            )

        if response.status_code != 200:
            raise ValueError(
                f"Code exchange failed for '{provider}': {response.status_code}"
            )

        data = response.json()

        token_info = OAuthTokenInfo(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            id_token=data.get("id_token"),
            token_type=data.get("token_type", "Bearer"),
            expires_at=time.time() + data.get("expires_in", 3600),
            scopes=provider_config.scopes,
        )
        self._token_store.set_token(provider, token_info)
        logger.info(f"OAuth authorization complete for provider '{provider}'")
        return token_info
