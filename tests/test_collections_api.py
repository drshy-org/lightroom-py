"""Wire-level tests for CollectionsAPI."""

from __future__ import annotations

import pytest

from .test_develop_api import _with_plugin


@pytest.mark.asyncio
async def test_list() -> None:
    fake = [
        {"name": "Picks", "kind": "collection", "parent": None, "id": "1", "photo_count": 10},
        {
            "name": "5-star",
            "kind": "smart",
            "parent": "Smart Collections",
            "id": "2",
            "photo_count": 3,
        },
    ]
    handlers = {"collections.list": lambda _p: {"collections": fake, "count": 2}}

    async def go(lr):
        return await lr.collections.list()

    colls, _ = await _with_plugin(handlers, go)
    assert colls == fake


@pytest.mark.asyncio
async def test_create() -> None:
    handlers = {
        "collections.create": lambda p: {
            "name": p["name"],
            "kind": "collection",
            "parent": p.get("parent"),
            "id": "999",
            "photo_count": 0,
        }
    }

    async def go(lr):
        return await lr.collections.create("New Album", parent="2026 Sets")

    result, calls = await _with_plugin(handlers, go)
    assert result["name"] == "New Album"
    method, params = calls[-1]
    assert method == "collections.create"
    assert params == {"name": "New Album", "parent": "2026 Sets"}


@pytest.mark.asyncio
async def test_create_validates_name() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.collections.create("")

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_add_remove_validate_uuids() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.collections.add("Picks", [])
        with pytest.raises(ValueError):
            await lr.collections.remove("Picks", [])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_get_photos_returns_uuids() -> None:
    handlers = {"collections.get_photos": lambda _p: {"uuids": ["a", "b", "c"], "count": 3}}

    async def go(lr):
        return await lr.collections.get_photos("Picks")

    uuids, _ = await _with_plugin(handlers, go)
    assert uuids == ["a", "b", "c"]
