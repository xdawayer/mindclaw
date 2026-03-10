# input: mindclaw.gateway.auth
# output: GatewayAuthManager 测试
# pos: Gateway 认证 + 设备配对测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import time

import pytest


def test_verify_token_correct(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="secret123", paired_devices_path=tmp_path / "devices.json")
    assert mgr.verify_token("secret123") is True


def test_verify_token_incorrect(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="secret123", paired_devices_path=tmp_path / "devices.json")
    assert mgr.verify_token("wrong") is False


def test_is_paired_initially_empty(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")
    assert mgr.is_paired("device1") is False


@pytest.mark.asyncio
async def test_pairing_approved(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")
    notifications = []

    async def notify(text):
        notifications.append(text)

    async def approve():
        await asyncio.sleep(0.05)
        pairing_id = list(mgr._pending_pairings.keys())[0]
        mgr.resolve_pairing(pairing_id, approved=True)

    asyncio.create_task(approve())
    pairing_id = await mgr.request_pairing("dev1", "My Phone", notify)
    result = await mgr.await_pairing(pairing_id, timeout=5.0)

    assert result is True
    assert mgr.is_paired("dev1")
    assert len(notifications) == 1


@pytest.mark.asyncio
async def test_pairing_rejected(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")

    async def notify(text):
        pass

    async def reject():
        await asyncio.sleep(0.05)
        pairing_id = list(mgr._pending_pairings.keys())[0]
        mgr.resolve_pairing(pairing_id, approved=False)

    asyncio.create_task(reject())
    pairing_id = await mgr.request_pairing("dev1", "My Phone", notify)
    result = await mgr.await_pairing(pairing_id, timeout=5.0)

    assert result is False
    assert not mgr.is_paired("dev1")


@pytest.mark.asyncio
async def test_pairing_timeout(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")

    async def notify(text):
        pass

    pairing_id = await mgr.request_pairing("dev1", "My Phone", notify)
    result = await mgr.await_pairing(pairing_id, timeout=0.1)

    assert result is False
    assert not mgr.is_paired("dev1")


def test_pairing_persistence(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice

    devices_path = tmp_path / "devices.json"
    mgr1 = GatewayAuthManager(token="t", paired_devices_path=devices_path)
    mgr1._paired["dev1"] = PairedDevice(
        device_id="dev1", device_name="Phone",
        paired_at=time.time(), last_seen=time.time(),
    )
    mgr1._save_devices()

    mgr2 = GatewayAuthManager(token="t", paired_devices_path=devices_path)
    assert mgr2.is_paired("dev1")


def test_resolve_pairing_unknown_id(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")
    mgr.resolve_pairing("nonexistent", approved=True)


def test_is_pairing_reply(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")
    # No pending pairings
    assert mgr.is_pairing_reply("pair abc") is False

    # Add a pending pairing manually
    from mindclaw.gateway.auth import PairingRequest
    mgr._pending_pairings["pair_abc"] = PairingRequest(
        pairing_id="pair_abc", device_id="dev1", device_name="Phone",
    )
    assert mgr.is_pairing_reply("pair pair_abc") is True
    assert mgr.is_pairing_reply("reject pair_abc") is True
    assert mgr.is_pairing_reply("pair unknown") is False
    assert mgr.is_pairing_reply("hello") is False


def test_handle_pairing_reply(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairingRequest

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")
    req = PairingRequest(pairing_id="pair_abc", device_id="dev1", device_name="Phone")
    mgr._pending_pairings["pair_abc"] = req

    mgr.handle_pairing_reply("pair pair_abc")
    assert req.approved is True
    assert req.event.is_set()
