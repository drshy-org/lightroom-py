"""Wire-level tests for DevelopAPI through CapturingPlugin."""

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


async def _with_plugin(plugin_handlers: dict, callable_):
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    for method, fn in plugin_handlers.items():
        plugin.on(method, fn)
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            return await callable_(lr), plugin.calls
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_list_presets() -> None:
    fake = [
        {"folder": "User", "name": "Warm Portrait", "uuid": "u1"},
        {"folder": "User", "name": "Cool Sky", "uuid": "u2"},
    ]
    handlers = {"develop.list_presets": lambda _p: {"presets": fake, "count": 2}}

    async def go(lr):
        return await lr.develop.list_presets()

    presets, calls = await _with_plugin(handlers, go)
    assert presets == fake
    assert calls[0][0] == "develop.list_presets"


@pytest.mark.asyncio
async def test_apply_preset_passes_folder() -> None:
    handlers = {
        "develop.apply_preset": lambda p: {
            "touched": len(p.get("uuids") or []),
            "preset": p["preset"],
        }
    }

    async def go(lr):
        await lr.develop.apply_preset("Warm", folder="User", photo_uuids=["a", "b"])

    _, calls = await _with_plugin(handlers, go)
    method, params = calls[-1]
    assert method == "develop.apply_preset"
    assert params == {"preset": "Warm", "folder": "User", "uuids": ["a", "b"]}


@pytest.mark.asyncio
async def test_apply_settings_validates_empty() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.apply_settings({}, photo_uuids=["a"])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_get_settings_unwraps_dict() -> None:
    fake = {"Exposure2012": 0.5, "Contrast2012": 25}
    handlers = {
        "develop.get_settings": lambda p: {
            "settings": {p["uuids"][0]: fake},
            "missing": [],
        }
    }

    async def go(lr):
        return await lr.develop.get_settings("uuid-1")

    settings, _ = await _with_plugin(handlers, go)
    assert settings == fake


@pytest.mark.asyncio
async def test_copy_validates() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.copy("src", [])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_set_passes_slider_values() -> None:
    handlers = {"develop.set": lambda p: {"applied": p["values"]}}

    async def go(lr):
        return await lr.develop.set(Exposure=0.5, Contrast=25)

    result, calls = await _with_plugin(handlers, go)
    assert calls[-1][1]["values"] == {"Exposure": 0.5, "Contrast": 25}
    assert result["applied"] == {"Exposure": 0.5, "Contrast": 25}


@pytest.mark.asyncio
async def test_set_requires_args() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.set()

    await _with_plugin({}, go)
