"""Bridge server lifecycle and /health endpoint."""

from __future__ import annotations

import socket

import httpx
import pytest

from lightroom.bridge.server import LocalBridgeServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port)
    await server.start()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:{port}/health", timeout=5)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "version" in body
    finally:
        await server.stop()
