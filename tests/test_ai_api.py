"""Wire-level tests for AIAPI through CapturingPlugin."""

from __future__ import annotations

import socket

import pytest

from lightroom import LightroomClient
from lightroom.bridge.server import LocalBridgeServer

from .test_metadata_api import CapturingPlugin


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_stage_denoise_validates_strength() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            with pytest.raises(ValueError):
                await lr.ai.stage_denoise(strength=150, photo_uuids=["a"])
            with pytest.raises(ValueError):
                await lr.ai.stage_denoise(strength=-5, photo_uuids=["a"])
            await lr.ai.stage_denoise(strength=50, photo_uuids=["a"])
        method, params = plugin.calls[-1]
        assert method == "ai.stage_denoise"
        assert params == {"strength": 50, "uuids": ["a"]}
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_prompt_update_round_trip() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    plugin.on("ai.prompt_update", lambda _p: {"acknowledged": True})
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            result = await lr.ai.prompt_update()
        assert result == {"acknowledged": True}
    finally:
        await plugin.stop()
        await server.stop()
