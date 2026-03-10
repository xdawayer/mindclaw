# input: mindclaw.health.check
# output: HealthCheckServer 测试
# pos: 验证健康检查 HTTP 端点的响应和渠道状态追踪
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json

import pytest


@pytest.mark.asyncio
async def test_health_status_returns_dict():
    """HealthMonitor.status() should return a dict with required fields."""
    from mindclaw.health.check import HealthMonitor

    monitor = HealthMonitor(version="0.1.0")
    status = monitor.status()

    assert status["status"] == "healthy"
    assert "uptime_seconds" in status
    assert status["version"] == "0.1.0"
    assert "channels" in status
    assert isinstance(status["channels"], dict)


@pytest.mark.asyncio
async def test_health_track_channel_activity():
    """HealthMonitor should track channel activity."""
    from mindclaw.health.check import HealthMonitor

    monitor = HealthMonitor(version="0.1.0")
    monitor.record_activity("telegram")
    monitor.record_activity("telegram")
    monitor.record_activity("slack")

    status = monitor.status()
    assert status["channels"]["telegram"]["messages"] == 2
    assert status["channels"]["slack"]["messages"] == 1


@pytest.mark.asyncio
async def test_health_status_uptime_increases():
    """Uptime should be >= 0."""
    from mindclaw.health.check import HealthMonitor

    monitor = HealthMonitor(version="0.1.0")
    status = monitor.status()

    assert status["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_health_server_starts_and_stops():
    """HealthCheckServer should start and stop cleanly."""
    from mindclaw.health.check import HealthCheckServer, HealthMonitor

    monitor = HealthMonitor(version="0.1.0")
    server = HealthCheckServer(monitor=monitor, port=0)  # port=0 for random available port

    await server.start()
    assert server.is_running
    actual_port = server.port

    # Fetch health endpoint
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://127.0.0.1:{actual_port}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    await server.stop()
    assert not server.is_running


@pytest.mark.asyncio
async def test_health_ready_endpoint():
    """GET /ready should return 200."""
    from mindclaw.health.check import HealthCheckServer, HealthMonitor

    monitor = HealthMonitor(version="0.1.0")
    server = HealthCheckServer(monitor=monitor, port=0)

    await server.start()
    actual_port = server.port

    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://127.0.0.1:{actual_port}/ready")
        assert resp.status_code == 200

    await server.stop()


@pytest.mark.asyncio
async def test_health_unknown_path():
    """Unknown paths should return 404."""
    from mindclaw.health.check import HealthCheckServer, HealthMonitor

    monitor = HealthMonitor(version="0.1.0")
    server = HealthCheckServer(monitor=monitor, port=0)

    await server.start()
    actual_port = server.port

    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://127.0.0.1:{actual_port}/unknown")
        assert resp.status_code == 404

    await server.stop()


def test_http_response_content_length_is_bytes():
    """Content-Length should count bytes, not characters."""
    from mindclaw.health.check import HealthCheckServer

    body = '{"status": "ok"}'
    response = HealthCheckServer._http_response(200, body, "application/json")
    expected_length = len(body.encode("utf-8"))
    assert f"Content-Length: {expected_length}" in response
