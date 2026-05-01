"""Wire-level tests for v0.4 DevelopAPI additions: tone curve, snapshots,
process version, targeted resets, paste-settings, masks."""

from __future__ import annotations

import pytest

from .test_develop_api import _with_plugin


@pytest.mark.asyncio
async def test_curve_get() -> None:
    fake_curve = {
        "name": "Linear",
        "points": [0, 0, 128, 128, 255, 255],
        "channel": "rgb",
    }
    handlers = {"develop.curve_get": lambda p: {"curves": {p["uuids"][0]: fake_curve}}}

    async def go(lr):
        return await lr.develop.curve_get("uuid-1", channel="rgb")

    result, _ = await _with_plugin(handlers, go)
    assert result == fake_curve


@pytest.mark.asyncio
async def test_curve_set_validates() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.curve_set([0, 0, 255], photo_uuids=["u"])  # odd length
        with pytest.raises(ValueError):
            await lr.develop.curve_set([0, 0], photo_uuids=["u"])  # too short
        with pytest.raises(ValueError):
            await lr.develop.curve_set([0, 0, 255, 255], channel="weird", photo_uuids=["u"])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_curve_set_passes_payload() -> None:
    handlers = {
        "develop.curve_set": lambda p: {"touched": len(p["uuids"]), "channel": p["channel"]}
    }

    async def go(lr):
        return await lr.develop.curve_set(
            [0, 0, 128, 140, 255, 255], channel="rgb", photo_uuids=["a"]
        )

    _, calls = await _with_plugin(handlers, go)
    method, params = calls[-1]
    assert method == "develop.curve_set"
    assert params == {"points": [0, 0, 128, 140, 255, 255], "channel": "rgb", "uuids": ["a"]}


@pytest.mark.asyncio
async def test_curve_preset_validates_name() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.curve_preset("Bogus", photo_uuids=["u"])
        # valid names should not raise
        await lr.develop.curve_preset("Linear", photo_uuids=["u"])
        await lr.develop.curve_preset("Medium Contrast", photo_uuids=["u"])
        await lr.develop.curve_preset("Strong Contrast", photo_uuids=["u"])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_snapshot_create_validates_name() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.snapshot_create("", photo_uuids=["u"])
        await lr.develop.snapshot_create("My Snapshot", photo_uuids=["u"])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_snapshot_list_returns_dict() -> None:
    fake = {"u1": [{"name": "Before"}, {"name": "After"}]}
    handlers = {"develop.snapshot_list": lambda _p: {"snapshots": fake}}

    async def go(lr):
        return await lr.develop.snapshot_list(photo_uuids=["u1"])

    result, _ = await _with_plugin(handlers, go)
    assert result == fake


@pytest.mark.asyncio
async def test_process_version_get_set() -> None:
    handlers = {
        "develop.process_version_get": lambda p: {"versions": {p["uuids"][0]: "11.0"}},
        "develop.process_version_set": lambda p: {
            "touched": len(p["uuids"]),
            "version": p["version"],
        },
    }

    async def go(lr):
        v = await lr.develop.process_version_get("u1")
        await lr.develop.process_version_set("11.0", photo_uuids=["u1", "u2"])
        return v

    result, calls = await _with_plugin(handlers, go)
    assert result == "11.0"
    method, params = calls[-1]
    assert method == "develop.process_version_set"
    assert params == {"version": "11.0", "uuids": ["u1", "u2"]}


@pytest.mark.asyncio
async def test_process_version_set_validates() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.process_version_set("", photo_uuids=["u"])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_targeted_resets_dispatch() -> None:
    async def go(lr):
        await lr.develop.reset_crop(photo_uuids=["u"])
        await lr.develop.reset_masking(photo_uuids=["u"])
        await lr.develop.reset_spot(photo_uuids=["u"])
        await lr.develop.reset_redeye(photo_uuids=["u"])
        await lr.develop.reset_transforms(photo_uuids=["u"])

    _, calls = await _with_plugin({}, go)
    methods = [m for m, _ in calls]
    assert methods == [
        "develop.reset_crop",
        "develop.reset_masking",
        "develop.reset_spot",
        "develop.reset_redeye",
        "develop.reset_transforms",
    ]


@pytest.mark.asyncio
async def test_paste_settings_validates_and_passes_subset() -> None:
    handlers = {
        "develop.paste_settings": lambda p: {
            "touched": len(p["uuids"]),
            "applied_keys": list((p.get("settings") or {}).keys()),
        }
    }

    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.paste_settings({}, photo_uuids=["u"])
        await lr.develop.paste_settings(
            {"Exposure2012": 0.5, "Contrast2012": 25},
            subset=["Exposure2012"],
            photo_uuids=["u1", "u2"],
        )

    _, calls = await _with_plugin(handlers, go)
    method, params = calls[-1]
    assert method == "develop.paste_settings"
    assert params["subset"] == ["Exposure2012"]
    assert params["uuids"] == ["u1", "u2"]


@pytest.mark.asyncio
async def test_mask_list_unwraps() -> None:
    fake = {
        "u1": {
            "ai_masks": 2,
            "gradient": 0,
            "circular": 1,
            "paint": 0,
            "retouch_areas": 0,
            "red_eye": 0,
        }
    }
    handlers = {"develop.mask_list": lambda _p: {"masks": fake}}

    async def go(lr):
        return await lr.develop.mask_list(photo_uuids=["u1"])

    result, _ = await _with_plugin(handlers, go)
    assert result == fake


@pytest.mark.asyncio
async def test_mask_clear_validates_kind() -> None:
    async def go(lr):
        with pytest.raises(ValueError):
            await lr.develop.mask_clear(kind="bogus", photo_uuids=["u"])
        await lr.develop.mask_clear(kind="all", photo_uuids=["u"])
        await lr.develop.mask_clear(kind="ai", photo_uuids=["u"])
        await lr.develop.mask_clear(kind="gradient", photo_uuids=["u"])

    await _with_plugin({}, go)
