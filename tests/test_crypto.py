# input: mindclaw.security.crypto
# output: SecretStore 加密存储测试
# pos: 安全层加密存储测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest


def test_secret_store_init_creates_master_key(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    assert (tmp_path / "master.key").exists()
    mode = (tmp_path / "master.key").stat().st_mode & 0o777
    assert mode == 0o600


def test_secret_store_set_and_get(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    store.set("API_KEY", "sk-test-123")
    assert store.get("API_KEY") == "sk-test-123"


def test_secret_store_get_nonexistent(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    assert store.get("NONEXISTENT") is None


def test_secret_store_delete(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    store.set("KEY", "value")
    store.delete("KEY")
    assert store.get("KEY") is None


def test_secret_store_list_keys(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    store.set("A", "1")
    store.set("B", "2")
    keys = store.list_keys()
    assert sorted(keys) == ["A", "B"]


def test_secret_store_persistence(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store1 = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store1.init_or_load_key()
    store1.set("PERSIST", "hello")

    store2 = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store2.init_or_load_key()
    assert store2.get("PERSIST") == "hello"


def test_secret_store_file_permissions(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    store.set("KEY", "val")
    mode = (tmp_path / "secrets.enc").stat().st_mode & 0o777
    assert mode == 0o600
