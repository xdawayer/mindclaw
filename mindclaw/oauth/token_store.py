# input: security/crypto.py (SecretStore), pydantic, time
# output: 导出 OAuthTokenInfo, OAuthTokenStore
# pos: OAuth token 加密持久化，复用 SecretStore 加密机制
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field

from mindclaw.security.crypto import SecretStore


class OAuthTokenInfo(BaseModel):
    """OAuth token with metadata."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: float | None = None
    scopes: list[str] = Field(default_factory=list)

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired or will expire within buffer window."""
        if self.expires_at is None:
            return False
        return time.time() >= (self.expires_at - buffer_seconds)


class OAuthTokenStore:
    """Encrypted storage for OAuth tokens, built on SecretStore."""

    def __init__(self, store_path: Path, master_key_path: Path) -> None:
        self._secret_store = SecretStore(
            store_path=store_path,
            master_key_path=master_key_path,
        )

    def init_or_load_key(self) -> None:
        self._secret_store.init_or_load_key()

    def get_token(self, provider: str) -> OAuthTokenInfo | None:
        raw = self._secret_store.get(f"oauth:{provider}")
        if raw is None:
            return None
        return OAuthTokenInfo.model_validate(json.loads(raw))

    def set_token(self, provider: str, token: OAuthTokenInfo) -> None:
        self._secret_store.set(f"oauth:{provider}", token.model_dump_json())

    def delete_token(self, provider: str) -> None:
        self._secret_store.delete(f"oauth:{provider}")

    def list_providers(self) -> list[str]:
        keys = self._secret_store.list_keys()
        return [k.removeprefix("oauth:") for k in keys if k.startswith("oauth:")]
