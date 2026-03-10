# input: mindclaw.oauth.token_store
# output: OAuth token 存储测试
# pos: OAuth token 持久化测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import time

import pytest

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
def sample_token():
    return OAuthTokenInfo(
        access_token="access_123",
        refresh_token="refresh_456",
        token_type="Bearer",
        expires_at=time.time() + 3600,
        scopes=["openid", "profile"],
    )


class TestOAuthTokenInfo:
    def test_is_expired_false(self):
        info = OAuthTokenInfo(
            access_token="t",
            refresh_token="r",
            token_type="Bearer",
            expires_at=time.time() + 3600,
        )
        assert not info.is_expired()

    def test_is_expired_true(self):
        info = OAuthTokenInfo(
            access_token="t",
            refresh_token="r",
            token_type="Bearer",
            expires_at=time.time() - 10,
        )
        assert info.is_expired()

    def test_is_expired_with_buffer(self):
        """Should be considered expired within buffer window."""
        info = OAuthTokenInfo(
            access_token="t",
            refresh_token="r",
            token_type="Bearer",
            expires_at=time.time() + 60,
        )
        assert info.is_expired(buffer_seconds=120)
        assert not info.is_expired(buffer_seconds=30)

    def test_is_expired_no_expiry(self):
        """No expiry means never expired."""
        info = OAuthTokenInfo(
            access_token="t",
            refresh_token=None,
            token_type="Bearer",
            expires_at=None,
        )
        assert not info.is_expired()


class TestOAuthTokenStore:
    def test_set_and_get(self, token_store, sample_token):
        token_store.set_token("openai", sample_token)
        retrieved = token_store.get_token("openai")
        assert retrieved is not None
        assert retrieved.access_token == "access_123"
        assert retrieved.refresh_token == "refresh_456"
        assert retrieved.scopes == ["openid", "profile"]

    def test_get_nonexistent(self, token_store):
        assert token_store.get_token("nonexistent") is None

    def test_delete_token(self, token_store, sample_token):
        token_store.set_token("openai", sample_token)
        token_store.delete_token("openai")
        assert token_store.get_token("openai") is None

    def test_list_providers(self, token_store, sample_token):
        token_store.set_token("openai", sample_token)
        token_store.set_token("google", sample_token)
        providers = token_store.list_providers()
        assert set(providers) == {"openai", "google"}

    def test_persistence(self, tmp_path, sample_token):
        """Tokens survive store re-creation."""
        paths = (tmp_path / "tokens.enc", tmp_path / "master.key")
        store1 = OAuthTokenStore(store_path=paths[0], master_key_path=paths[1])
        store1.init_or_load_key()
        store1.set_token("openai", sample_token)

        store2 = OAuthTokenStore(store_path=paths[0], master_key_path=paths[1])
        store2.init_or_load_key()
        retrieved = store2.get_token("openai")
        assert retrieved is not None
        assert retrieved.access_token == "access_123"
