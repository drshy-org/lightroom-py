"""Wire-level tests for v0.4 PhotosAPI additions: rich find filters,
selection ops, flags, rating-step, color-step."""

from __future__ import annotations

from pathlib import Path

import pytest

from lightroom._sqlite import list_photos

from .test_develop_api import _with_plugin

# ---------- new SQLite filters ----------


def test_list_photos_file_format_filter(synthetic_lrcat: Path) -> None:
    # Synthetic catalog has all photos with fileFormat='RAW'
    raw = list_photos(synthetic_lrcat, file_format="RAW")
    assert len(raw) == 5
    none_match = list_photos(synthetic_lrcat, file_format="JPG")
    assert len(none_match) == 0


def test_list_photos_color_label_filter(synthetic_lrcat: Path) -> None:
    red = list_photos(synthetic_lrcat, color_label="red")
    assert {r.uuid for r in red} == {"uuid-001"}
    yellow = list_photos(synthetic_lrcat, color_label="yellow")
    assert {r.uuid for r in yellow} == {"uuid-003"}
    none = list_photos(synthetic_lrcat, color_label="")
    # uuid-002, uuid-004, uuid-005 have empty color
    assert {r.uuid for r in none} == {"uuid-002", "uuid-004", "uuid-005"}


def test_list_photos_path_substring_filter(synthetic_lrcat: Path) -> None:
    rows = list_photos(synthetic_lrcat, path_substring="2026/04")
    # Folder 10 = "2026/04/" contains files 100, 101 → uuids 001, 002
    assert {r.uuid for r in rows} == {"uuid-001", "uuid-002"}

    rows = list_photos(synthetic_lrcat, path_substring="DSC_0003")
    assert {r.uuid for r in rows} == {"uuid-003"}


# ---------- selection ops ----------


@pytest.mark.asyncio
async def test_select_extend() -> None:
    async def go(lr):
        return await lr.photos.select_extend("uuid-a", "uuid-b")

    _, calls = await _with_plugin({}, go)
    method, params = calls[-1]
    assert method == "photos.select_extend"
    assert params["uuids"] == ["uuid-a", "uuid-b"]


@pytest.mark.asyncio
async def test_select_all_none_inverse_dispatch() -> None:
    async def go(lr):
        await lr.photos.select_all()
        await lr.photos.select_none()
        await lr.photos.select_inverse()

    _, calls = await _with_plugin({}, go)
    methods = [m for m, _ in calls]
    assert methods == ["photos.select_all", "photos.select_none", "photos.select_inverse"]


@pytest.mark.asyncio
async def test_next_previous_dispatch() -> None:
    async def go(lr):
        await lr.photos.next_photo()
        await lr.photos.previous_photo()

    _, calls = await _with_plugin({}, go)
    methods = [m for m, _ in calls]
    assert methods == ["photos.next", "photos.previous"]


# ---------- flags ----------


@pytest.mark.asyncio
async def test_flag_pick_reject_clear() -> None:
    async def go(lr):
        await lr.photos.flag_pick(photo_uuids=["u1"])
        await lr.photos.flag_reject(photo_uuids=["u1"])
        await lr.photos.flag_clear(photo_uuids=["u1"])

    _, calls = await _with_plugin({}, go)
    statuses = [params["status"] for _, params in calls]
    assert statuses == [1, -1, 0]


# ---------- rating step + color step ----------


@pytest.mark.asyncio
async def test_rating_step() -> None:
    async def go(lr):
        await lr.photos.rating_step(1, photo_uuids=["u1"])
        await lr.photos.rating_step(-2, photo_uuids=["u1"])

    _, calls = await _with_plugin({}, go)
    deltas = [params["delta"] for _, params in calls]
    assert deltas == [1, -2]


@pytest.mark.asyncio
async def test_color_step() -> None:
    async def go(lr):
        await lr.photos.color_step(1, photo_uuids=["u1"])
        await lr.photos.color_step(-1, photo_uuids=["u1"])

    _, calls = await _with_plugin({}, go)
    dirs = [params["direction"] for _, params in calls]
    assert dirs == [1, -1]


# ---------- find-by-path ----------


@pytest.mark.asyncio
async def test_find_by_path_uses_list(synthetic_lrcat: Path, lightroom_home: Path) -> None:
    """find_by_path is a thin wrapper around list — runs through SQLite, no bridge needed."""
    del lightroom_home
    from lightroom import LightroomClient

    async with LightroomClient.connect(require_bridge=False) as lr:
        await lr.catalog.open(synthetic_lrcat)
        rows = await lr.photos.find_by_path("DSC_0003", limit=10)
    assert {r.uuid for r in rows} == {"uuid-003"}
