"""Async tests for CatalogAPI / PhotosAPI through LightroomClient (no bridge)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lightroom import LightroomClient
from lightroom.exceptions import CatalogError


@pytest.mark.asyncio
async def test_open_and_info(synthetic_lrcat: Path, lightroom_home: Path) -> None:
    del lightroom_home  # provided via fixture monkeypatch
    async with LightroomClient.connect(require_bridge=False) as lr:
        info = await lr.catalog.open(synthetic_lrcat)
    assert info.path == synthetic_lrcat.resolve()
    assert info.photo_count == 5
    assert info.extra["earliest_capture"] == "2026-04-01T10:00:00"


@pytest.mark.asyncio
async def test_stats(synthetic_lrcat: Path, lightroom_home: Path) -> None:
    del lightroom_home
    async with LightroomClient.connect(require_bridge=False) as lr:
        await lr.catalog.open(synthetic_lrcat)
        s = await lr.catalog.stats()
    assert s["photos"] == 5
    assert s["folders"] == 2
    assert s["keywords"] == 3


@pytest.mark.asyncio
async def test_photos_list_filters(synthetic_lrcat: Path, lightroom_home: Path) -> None:
    del lightroom_home
    async with LightroomClient.connect(require_bridge=False) as lr:
        await lr.catalog.open(synthetic_lrcat)
        rows = await lr.photos.list(rating_gte=4)
    assert {r.uuid for r in rows} == {"uuid-001", "uuid-002"}


@pytest.mark.asyncio
async def test_photos_count(synthetic_lrcat: Path, lightroom_home: Path) -> None:
    del lightroom_home
    async with LightroomClient.connect(require_bridge=False) as lr:
        await lr.catalog.open(synthetic_lrcat)
        n = await lr.photos.count(rating_gte=3)
    assert n == 3


@pytest.mark.asyncio
async def test_no_active_catalog_raises(lightroom_home: Path) -> None:
    del lightroom_home
    async with LightroomClient.connect(require_bridge=False) as lr:
        with pytest.raises(CatalogError):
            await lr.catalog.info()
        with pytest.raises(CatalogError):
            await lr.photos.list()
