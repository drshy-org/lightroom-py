"""End-to-end tests for MetadataAPI through a mock plugin."""

from __future__ import annotations

import asyncio
import socket

import httpx
import pytest

from lightroom import LightroomClient
from lightroom.bridge.server import LocalBridgeServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class CapturingPlugin:
    """Plugin double that records every command it received."""

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token
        self.calls: list[tuple[str, dict]] = []
        self._http: httpx.AsyncClient | None = None
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._sid: str | None = None
        self._handlers: dict = {}

    def on(self, method: str, fn) -> None:
        self._handlers[method] = fn

    async def start(self) -> None:
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
        r = await self._http.post(
            "/handshake",
            json={"token": self.token, "plugin_version": "test", "lr_version": "14.0"},
        )
        r.raise_for_status()
        self._sid = r.json()["session_id"]
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
                    params={"token": self.token, "session_id": self._sid, "wait": 2},
                    timeout=10.0,
                )
            except (httpx.HTTPError, asyncio.CancelledError):
                if self._stop.is_set():
                    return
                await asyncio.sleep(0.05)
                continue
            if resp.status_code == 204:
                continue
            if resp.status_code != 200:
                await asyncio.sleep(0.05)
                continue

            cmd = resp.json()
            self.calls.append((cmd["method"], cmd.get("params") or {}))
            handler = self._handlers.get(cmd["method"])
            if handler is None:
                # Default: echo a touched=N counter based on uuids passed.
                params = cmd.get("params") or {}
                touched = len(params.get("uuids") or []) or 1
                payload = {
                    "id": cmd["id"],
                    "ok": True,
                    "result": {"touched": touched, "missing": []},
                }
            else:
                try:
                    result = handler(cmd.get("params") or {})
                    payload = {"id": cmd["id"], "ok": True, "result": result}
                except Exception as exc:
                    payload = {
                        "id": cmd["id"],
                        "ok": False,
                        "error": {"code": "handler_error", "message": str(exc)},
                    }
            await self._http.post(
                "/respond",
                params={"token": self.token, "session_id": self._sid},
                json=payload,
            )


@pytest.mark.asyncio
async def test_add_keywords_round_trip() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            result = await lr.metadata.add_keywords(
                ["wedding", "bride"], photo_uuids=["uuid-1", "uuid-2"]
            )
        assert result["touched"] == 2
        assert plugin.calls == [
            (
                "metadata.add_keywords",
                {"keywords": ["wedding", "bride"], "uuids": ["uuid-1", "uuid-2"]},
            )
        ]
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_set_rating_validates_range() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            with pytest.raises(ValueError):
                await lr.metadata.set_rating(7, photo_uuids=["uuid-1"])
            with pytest.raises(ValueError):
                await lr.metadata.set_rating(-1, photo_uuids=["uuid-1"])
            ok = await lr.metadata.set_rating(5, photo_uuids=["uuid-1"])
            assert ok["touched"] == 1
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_set_color_label_validates() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            with pytest.raises(ValueError):
                await lr.metadata.set_color_label("orange", photo_uuids=["uuid-1"])
            ok = await lr.metadata.set_color_label("red", photo_uuids=["uuid-1"])
            assert ok["touched"] == 1
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_set_iptc_passthrough() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            with pytest.raises(ValueError):
                await lr.metadata.set_iptc({}, photo_uuids=["u"])
            await lr.metadata.set_iptc({"caption": "Sunset", "city": "Paris"}, photo_uuids=["u"])
        method, params = plugin.calls[-1]
        assert method == "metadata.set_iptc"
        assert params["fields"] == {"caption": "Sunset", "city": "Paris"}
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_xmp_read_write() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            await lr.metadata.write_xmp(photo_uuids=["a", "b"])
            await lr.metadata.read_xmp(photo_uuids=["a", "b"])
        methods = [m for m, _ in plugin.calls]
        assert methods == ["metadata.write_xmp", "metadata.read_xmp"]
    finally:
        await plugin.stop()
        await server.stop()
