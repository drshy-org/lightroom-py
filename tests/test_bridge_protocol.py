"""End-to-end bridge protocol tests with a mock plugin (Python) on the
client side. Validates handshake → poll → respond → result roundtrip."""

from __future__ import annotations

import asyncio
import socket

import httpx
import pytest

from lightroom import LightroomClient
from lightroom.bridge.server import LocalBridgeServer
from lightroom.exceptions import CommandFailedError


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MockPlugin:
    """A Python stand-in for the Lua plugin: handshakes, polls, responds."""

    def __init__(self, base_url: str, token: str, handlers: dict) -> None:
        self.base_url = base_url
        self.token = token
        self.handlers = handlers
        self.session_id: str | None = None
        self._task: asyncio.Task | None = None
        self._http: httpx.AsyncClient | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
        resp = await self._http.post(
            "/handshake",
            json={"token": self.token, "plugin_version": "test", "lr_version": "test"},
        )
        resp.raise_for_status()
        self.session_id = resp.json()["session_id"]
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._http is not None:
            await self._http.aclose()

    async def _loop(self) -> None:
        assert self._http is not None
        while not self._stop.is_set():
            try:
                resp = await self._http.get(
                    "/poll",
                    params={"token": self.token, "session_id": self.session_id, "wait": 2},
                    timeout=10.0,
                )
            except (httpx.HTTPError, asyncio.CancelledError):
                if self._stop.is_set():
                    return
                await asyncio.sleep(0.1)
                continue

            if resp.status_code == 204:
                continue
            if resp.status_code != 200:
                await asyncio.sleep(0.1)
                continue

            cmd = resp.json()
            handler = self.handlers.get(cmd["method"])
            if handler is None:
                payload = {
                    "id": cmd["id"],
                    "ok": False,
                    "error": {"code": "unknown_method", "message": cmd["method"]},
                }
            else:
                try:
                    result = handler(cmd.get("params") or {})
                    payload = {"id": cmd["id"], "ok": True, "result": result}
                except Exception as exc:  # noqa: BLE001
                    payload = {
                        "id": cmd["id"],
                        "ok": False,
                        "error": {"code": "handler_error", "message": str(exc)},
                    }
            await self._http.post(
                "/respond",
                params={"token": self.token, "session_id": self.session_id},
                json=payload,
            )


@pytest.mark.asyncio
async def test_ping_roundtrip() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="test-token")
    await server.start()
    plugin = MockPlugin(
        f"http://127.0.0.1:{port}",
        token="test-token",
        handlers={"ping": lambda _p: {"pong": True, "lr_version": "13.0"}},
    )
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="test-token") as lr:
            reply = await lr.ping(timeout=5)
        assert reply == {"pong": True, "lr_version": "13.0"}
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_handler_error_translated() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()

    def boom(_p):
        raise RuntimeError("nope")

    plugin = MockPlugin(f"http://127.0.0.1:{port}", token="t", handlers={"ping": boom})
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            with pytest.raises(CommandFailedError) as ei:
                await lr.ping(timeout=5)
        assert "nope" in str(ei.value)
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_health_reflects_plugin_state() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = MockPlugin(f"http://127.0.0.1:{port}", token="t", handlers={})
    try:
        async with httpx.AsyncClient() as http:
            r = await http.get(f"http://127.0.0.1:{port}/health")
            assert r.json()["plugin_session_id"] is None

            await plugin.start()
            r = await http.get(f"http://127.0.0.1:{port}/health")
            body = r.json()
            assert body["plugin_session_id"] == plugin.session_id
            assert body["plugin_version"] == "test"
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_handshake_rejects_bad_token() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="correct")
    await server.start()
    try:
        async with httpx.AsyncClient() as http:
            r = await http.post(
                f"http://127.0.0.1:{port}/handshake",
                json={"token": "wrong", "plugin_version": "x", "lr_version": "x"},
            )
            assert r.status_code == 401
    finally:
        await server.stop()
