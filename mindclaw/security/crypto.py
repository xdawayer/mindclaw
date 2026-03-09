# input: cryptography (Fernet), json, pathlib
# output: 导出 SecretStore
# pos: 安全层加密存储，使用 Fernet 对称加密保存 API Key 等敏感信息
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
from pathlib import Path

from cryptography.fernet import Fernet


class SecretStore:
    """Encrypted storage for sensitive values (API keys, tokens, etc.).

    Uses Fernet symmetric encryption. Master key is stored in a separate file
    with 0600 permissions. The encrypted secrets file is also 0600.
    """

    def __init__(self, store_path: Path, master_key_path: Path) -> None:
        self._store_path = store_path
        self._master_key_path = master_key_path
        self._fernet: Fernet | None = None

    def init_or_load_key(self) -> None:
        if self._master_key_path.exists():
            key = self._master_key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self._master_key_path.parent.mkdir(parents=True, exist_ok=True)
            self._master_key_path.write_bytes(key)
            self._master_key_path.chmod(0o600)
        self._fernet = Fernet(key)

    def get(self, name: str) -> str | None:
        secrets = self._load_all()
        return secrets.get(name)

    def set(self, name: str, value: str) -> None:
        secrets = self._load_all()
        secrets[name] = value
        self._save_all(secrets)

    def delete(self, name: str) -> None:
        secrets = self._load_all()
        secrets.pop(name, None)
        self._save_all(secrets)

    def list_keys(self) -> list[str]:
        return list(self._load_all().keys())

    def _load_all(self) -> dict[str, str]:
        if not self._store_path.exists():
            return {}
        encrypted = self._store_path.read_bytes()
        decrypted = self._fernet.decrypt(encrypted)
        return json.loads(decrypted)

    def _save_all(self, secrets: dict[str, str]) -> None:
        raw = json.dumps(secrets).encode()
        encrypted = self._fernet.encrypt(raw)
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_bytes(encrypted)
        self._store_path.chmod(0o600)
