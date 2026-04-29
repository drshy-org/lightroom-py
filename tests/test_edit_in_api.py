"""Wire-level tests for EditInAPI."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from lightroom import LightroomClient
from lightroom.bridge.server import LocalBridgeServer

from .test_metadata_api import CapturingPlugin


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_export_passes_params(tmp_path: Path) -> None:
    out_dir = tmp_path / "exports"
    fake = [{"uuid": "a", "path": str(out_dir / "a.tif")}]
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    plugin.on(
        "edit_in.export",
        lambda p: {"exported": fake, "missing": [], "out_dir": p["out_dir"]},
    )
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            exported = await lr.edit_in.export(out_dir, photo_uuids=["a"], format="JPEG")
        assert exported == fake
        method, params = plugin.calls[-1]
        assert method == "edit_in.export"
        assert params["uuids"] == ["a"]
        assert params["format"] == "JPEG"
        assert Path(params["out_dir"]).resolve() == out_dir.resolve()
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_import_as_stack_validates_empty() -> None:
    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            with pytest.raises(ValueError):
                await lr.edit_in.import_as_stack([])
    finally:
        await plugin.stop()
        await server.stop()


@pytest.mark.asyncio
async def test_run_full_round_trip(tmp_path: Path) -> None:
    """End-to-end: export → external command → import_as_stack."""
    out_dir = tmp_path / "exports"

    # Mock plugin: when export is called, write a fake input file and return its path.
    out_dir.mkdir(parents=True, exist_ok=True)
    fake_input = out_dir / "DSC_0001.tif"

    def fake_export(p):
        # Materialize a "rendered" file so the external command can run on it.
        fake_input.write_text("fake tiff content")
        return {
            "exported": [{"uuid": "uuid-a", "path": str(fake_input)}],
            "missing": [],
            "out_dir": p["out_dir"],
        }

    def fake_import(p):
        return {
            "imported": [
                {"src_uuid": pair["src_uuid"], "new_uuid": "new-" + pair["src_uuid"]}
                for pair in p["pairs"]
            ],
            "errors": [],
        }

    port = _free_port()
    server = LocalBridgeServer(host="127.0.0.1", port=port, token="t")
    await server.start()
    plugin = CapturingPlugin(f"http://127.0.0.1:{port}", token="t")
    plugin.on("edit_in.export", fake_export)
    plugin.on("edit_in.import_as_stack", fake_import)
    try:
        await plugin.start()
        async with LightroomClient.connect(port=port, token="t") as lr:
            # Use `cp` as a no-op external tool: copies input → output.
            result = await lr.edit_in.run(
                ["cp", "{input}", "{output}"],
                photo_uuids=["uuid-a"],
                out_dir=out_dir,
                cleanup_exports=False,
            )
        assert result["exported"] == 1
        assert result["processed"] == 1
        assert result["imported"] == 1
        assert result["errors"] == []
        # The output file should now exist (cp created it).
        edited = fake_input.with_stem(fake_input.stem + "-edited")
        assert edited.exists()
    finally:
        await plugin.stop()
        await server.stop()
