# input: asyncio, hmac, json, uuid, time, pathlib
# output: 导出 GatewayAuthManager, PairedDevice, PairingRequest
# pos: Gateway 认证层，Token 验证 + 设备配对管理
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import hmac
import json
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class PairedDevice:
    device_id: str
    device_name: str
    paired_at: float
    last_seen: float


@dataclass
class PairingRequest:
    pairing_id: str
    device_id: str
    device_name: str
    created_at: float = field(default_factory=time.time)
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False


class GatewayAuthManager:
    """Token authentication and device pairing for Gateway WebSocket connections."""

    def __init__(self, token: str, paired_devices_path: Path) -> None:
        self._token = token
        self._paired_devices_path = paired_devices_path
        self._paired: dict[str, PairedDevice] = {}
        self._pending_pairings: dict[str, PairingRequest] = {}
        self._load_devices()

    def verify_token(self, token: str) -> bool:
        return hmac.compare_digest(self._token, token)

    def is_paired(self, device_id: str) -> bool:
        return device_id in self._paired

    def update_last_seen(self, device_id: str) -> None:
        if device_id in self._paired:
            self._paired[device_id].last_seen = time.time()

    async def request_pairing(
        self,
        device_id: str,
        device_name: str,
        notify_callback: Callable[[str], Coroutine[Any, Any, None]],
    ) -> str:
        pairing_id = f"pair_{uuid.uuid4().hex[:8]}"
        self._pending_pairings[pairing_id] = PairingRequest(
            pairing_id=pairing_id,
            device_id=device_id,
            device_name=device_name,
        )
        logger.info(f"Pairing requested: {pairing_id} for device '{device_name}' ({device_id})")
        await notify_callback(
            f"New device pairing request:\n"
            f"  Device: {device_name}\n"
            f"  ID: {device_id}\n\n"
            f"Reply 'pair {pairing_id}' to approve, 'reject {pairing_id}' to deny."
        )
        return pairing_id

    async def await_pairing(self, pairing_id: str, timeout: float = 300.0) -> bool:
        req = self._pending_pairings.get(pairing_id)
        if req is None:
            return False
        try:
            await asyncio.wait_for(req.event.wait(), timeout=timeout)
            if req.approved:
                self._paired[req.device_id] = PairedDevice(
                    device_id=req.device_id,
                    device_name=req.device_name,
                    paired_at=time.time(),
                    last_seen=time.time(),
                )
                self._save_devices()
                logger.info(f"Device paired: {req.device_id}")
            return req.approved
        except asyncio.TimeoutError:
            logger.warning(f"Pairing timeout: {pairing_id}")
            return False
        finally:
            self._pending_pairings.pop(pairing_id, None)

    def resolve_pairing(self, pairing_id: str, approved: bool) -> None:
        req = self._pending_pairings.get(pairing_id)
        if req is None:
            return
        req.approved = approved
        req.event.set()

    def is_pairing_reply(self, text: str) -> bool:
        parts = text.strip().lower().split()
        if len(parts) != 2:
            return False
        cmd, pairing_id = parts
        if cmd not in ("pair", "reject"):
            return False
        return pairing_id in self._pending_pairings

    def handle_pairing_reply(self, text: str) -> None:
        parts = text.strip().lower().split()
        if len(parts) != 2:
            return
        cmd, pairing_id = parts
        self.resolve_pairing(pairing_id, approved=(cmd == "pair"))

    def _save_devices(self) -> None:
        data = {
            did: {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "paired_at": d.paired_at,
                "last_seen": d.last_seen,
            }
            for did, d in self._paired.items()
        }
        self._paired_devices_path.parent.mkdir(parents=True, exist_ok=True)
        self._paired_devices_path.write_text(json.dumps(data, indent=2))
        self._paired_devices_path.chmod(0o600)

    def _load_devices(self) -> None:
        if not self._paired_devices_path.exists():
            return
        try:
            data = json.loads(self._paired_devices_path.read_text())
            for did, info in data.items():
                self._paired[did] = PairedDevice(**info)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to load paired devices, starting fresh")
