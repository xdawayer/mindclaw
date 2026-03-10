# input: asyncio, json, time
# output: 导出 HealthMonitor, HealthCheckServer
# pos: 健康检查 HTTP 服务，提供 /health 和 /ready 端点
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Lightweight health check HTTP server using asyncio stdlib."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from loguru import logger


class HealthMonitor:
    """Track system health metrics: uptime, channel activity."""

    def __init__(self, version: str = "0.0.0") -> None:
        self._version = version
        self._start_time = time.monotonic()
        self._channel_messages: dict[str, int] = {}

    def record_activity(self, channel: str) -> None:
        self._channel_messages[channel] = self._channel_messages.get(channel, 0) + 1

    def status(self) -> dict[str, Any]:
        uptime = time.monotonic() - self._start_time
        channels = {
            name: {"messages": count}
            for name, count in self._channel_messages.items()
        }
        return {
            "status": "healthy",
            "uptime_seconds": round(uptime, 1),
            "version": self._version,
            "channels": channels,
        }


class HealthCheckServer:
    """Minimal async HTTP server for /health and /ready endpoints."""

    def __init__(self, monitor: HealthMonitor, port: int = 8766) -> None:
        self._monitor = monitor
        self._requested_port = port
        self._server: asyncio.Server | None = None
        self._port: int | None = None

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._server.is_serving()

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError("Server not started")
        return self._port

    async def start(self) -> None:
        try:
            self._server = await asyncio.start_server(
                self._handle_connection,
                "127.0.0.1",
                self._requested_port,
            )
        except OSError as e:
            logger.warning(
                f"HealthCheck server failed to bind port {self._requested_port}: {e}. "
                "Health endpoints will be unavailable."
            )
            return
        # Resolve actual port (important when port=0)
        addr = self._server.sockets[0].getsockname()
        self._port = addr[1]
        logger.info(f"HealthCheck server listening on 127.0.0.1:{self._port}")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            self._port = None
            logger.info("HealthCheck server stopped")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            request = data.decode("utf-8", errors="replace")

            # Parse HTTP request line
            path = self._parse_path(request)

            if path == "/health":
                body = json.dumps(self._monitor.status())
                response = self._http_response(200, body, "application/json")
            elif path == "/ready":
                response = self._http_response(200, '{"ready": true}', "application/json")
            else:
                response = self._http_response(404, '{"error": "not found"}', "application/json")

            writer.write(response.encode("utf-8"))
            await writer.drain()
        except Exception:
            logger.debug("HealthCheck connection error")
        finally:
            writer.close()
            await writer.wait_closed()

    @staticmethod
    def _parse_path(request: str) -> str:
        lines = request.split("\r\n")
        if lines:
            parts = lines[0].split(" ")
            if len(parts) >= 2:
                return parts[1]
        return "/"

    @staticmethod
    def _http_response(status: int, body: str, content_type: str) -> str:
        status_text = {200: "OK", 404: "Not Found", 503: "Service Unavailable"}.get(
            status, "Unknown"
        )
        body_bytes = len(body.encode("utf-8"))
        return (
            f"HTTP/1.1 {status} {status_text}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {body_bytes}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{body}"
        )
