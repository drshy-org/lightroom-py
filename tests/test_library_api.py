"""Wire-level tests for LibraryAPI."""

from __future__ import annotations

from pathlib import Path

import pytest

from .test_develop_api import _with_plugin


@pytest.mark.asyncio
async def test_list_folders() -> None:
    fake = [
        {"name": "Photos", "path": "/Volumes/Photos", "depth": 0},
        {"name": "2026", "path": "/Volumes/Photos/2026", "depth": 1},
    ]
    handlers = {"library.list_folders": lambda _p: {"folders": fake, "count": 2}}

    async def go(lr):
        return await lr.library.list_folders()

    folders, _ = await _with_plugin(handlers, go)
    assert folders == fake


@pytest.mark.asyncio
async def test_export_aliased_to_edit_in_export(tmp_path: Path) -> None:
    out_dir = tmp_path / "exports"
    handlers = {
        "edit_in.export": lambda p: {
            "exported": [{"uuid": "a", "path": str(out_dir / "a.tif")}],
            "missing": [],
            "out_dir": p["out_dir"],
        }
    }

    async def go(lr):
        return await lr.library.export(out_dir, photo_uuids=["a"], format="TIFF")

    result, calls = await _with_plugin(handlers, go)
    assert len(result) == 1
    method, params = calls[-1]
    assert method == "edit_in.export"
    assert params["format"] == "TIFF"


@pytest.mark.asyncio
async def test_make_virtual_copy() -> None:
    handlers = {
        "library.make_virtual_copy": lambda p: {
            "created": [{"src_uuid": p["uuids"][0], "new_uuid": "new-uuid"}],
            "missing": [],
        }
    }

    async def go(lr):
        return await lr.library.make_virtual_copy("orig-uuid", copy_name="Edit 1")

    result, calls = await _with_plugin(handlers, go)
    assert result["created"][0]["src_uuid"] == "orig-uuid"
    method, params = calls[-1]
    assert method == "library.make_virtual_copy"
    assert params == {"uuids": ["orig-uuid"], "copy_name": "Edit 1"}


@pytest.mark.asyncio
async def test_stack_validates() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.library.stack(["just-one"])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_import_photos_not_implemented() -> None:
    async def go(lr):
        with pytest.raises(NotImplementedError):
            await lr.library.import_photos(["/some/path.jpg"])

    await _with_plugin({}, go)
