"""Wire-level tests for v0.5 typed Develop wrappers.

Verifies each typed method synthesizes the correct Adobe-key payload and
dispatches via ``develop.apply_settings``. None-valued args are dropped.
"""

from __future__ import annotations

import pytest

from .test_develop_api import _with_plugin


@pytest.mark.asyncio
async def test_crop_synthesizes_settings() -> None:
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.crop(
            top=0.05,
            left=0.05,
            right=0.95,
            bottom=0.95,
            angle=1.5,
            constrain_to_warp=True,
            photo_uuids=["u"],
        )

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    assert s["CropTop"] == 0.05
    assert s["CropLeft"] == 0.05
    assert s["CropRight"] == 0.95
    assert s["CropBottom"] == 0.95
    assert s["CropAngle"] == 1.5
    assert s["CropConstrainToWarp"] is True


@pytest.mark.asyncio
async def test_crop_drops_none_args() -> None:
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.crop(angle=2.0, photo_uuids=["u"])

    _, _ = await _with_plugin(handlers, go)
    # Only the one non-None field should be in the payload.
    assert set(captured["settings"].keys()) == {"CropAngle"}


@pytest.mark.asyncio
async def test_crop_noop_skips_dispatch() -> None:
    """All-None args should short-circuit without hitting the bridge."""
    handlers: dict = {}

    async def go(lr):
        return await lr.develop.crop(photo_uuids=["u"])

    result, calls = await _with_plugin(handlers, go)
    assert result.get("skipped") == "no settings"
    assert calls == []


@pytest.mark.asyncio
async def test_hsl_per_band() -> None:
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.hsl(
            saturation={"red": 20, "orange": -10},
            luminance={"blue": 15},
            photo_uuids=["u"],
        )

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    assert s["SaturationAdjustmentRed"] == 20.0
    assert s["SaturationAdjustmentOrange"] == -10.0
    assert s["LuminanceAdjustmentBlue"] == 15.0
    # Untouched bands should not be present.
    assert "HueAdjustmentRed" not in s
    assert "SaturationAdjustmentBlue" not in s


@pytest.mark.asyncio
async def test_hsl_rejects_unknown_band() -> None:
    async def go(lr):
        with pytest.raises(ValueError, match="unknown HSL band"):
            await lr.develop.hsl(saturation={"chartreuse": 5}, photo_uuids=["u"])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_color_grade_routes_shadow_highlight_to_split_toning() -> None:
    """LR 15.3 quirk: Shadow/Highlight Hue+Sat go through legacy SplitToning*.
    Midtone/Global/Lum stay on ColorGrade*. Auto-sets EnableSplitToning."""
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.color_grade(
            shadow_hue=215,
            shadow_sat=20,
            shadow_lum=5,
            midtone_hue=180,
            midtone_sat=15,
            highlight_hue=30,
            highlight_sat=25,
            highlight_lum=10,
            global_hue=90,
            balance=10,
            blending=60,
            photo_uuids=["u"],
        )

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    # Midtone + Global + Lum use new schema:
    assert s["ColorGradeMidtoneHue"] == 180
    assert s["ColorGradeMidtoneSat"] == 15
    assert s["ColorGradeShadowLum"] == 5
    assert s["ColorGradeHighlightLum"] == 10
    assert s["ColorGradeGlobalHue"] == 90
    assert s["ColorGradeBlending"] == 60
    # Shadow/Highlight Hue+Sat + Balance route to legacy SplitToning*:
    assert s["SplitToningShadowHue"] == 215
    assert s["SplitToningShadowSaturation"] == 20
    assert s["SplitToningHighlightHue"] == 30
    assert s["SplitToningHighlightSaturation"] == 25
    assert s["SplitToningBalance"] == 10
    # Auto-enable flag:
    assert s["EnableSplitToning"] is True


@pytest.mark.asyncio
async def test_color_grade_no_split_toning_when_only_midtone() -> None:
    """If only the new-schema keys are touched, don't auto-enable SplitToning."""
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.color_grade(midtone_hue=180, midtone_sat=15, photo_uuids=["u"])

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    assert "EnableSplitToning" not in s
    assert "SplitToningShadowHue" not in s


@pytest.mark.asyncio
async def test_transform_upright_modes() -> None:
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.transform(upright_mode="auto", rotate=2.0, photo_uuids=["u"])

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    assert s["PerspectiveUpright"] == 1
    assert s["PerspectiveRotate"] == 2.0


@pytest.mark.asyncio
async def test_transform_rejects_unknown_upright() -> None:
    async def go(lr):
        with pytest.raises(ValueError, match="upright_mode must be one of"):
            await lr.develop.transform(upright_mode="bogus", photo_uuids=["u"])

    await _with_plugin({}, go)


@pytest.mark.asyncio
async def test_lens_correction_bool_to_int() -> None:
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.lens_correction(
            enable_profile=True,
            auto_lateral_ca=False,
            remove_chromatic_aberration=True,
            distortion_amount=100,
            photo_uuids=["u"],
        )

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    assert s["LensProfileEnable"] == 1
    assert s["AutoLateralCA"] == 0
    assert s["RemoveChromaticAberration"] is True
    assert s["LensProfileDistortionScale"] == 100


@pytest.mark.asyncio
async def test_calibration_profile_string() -> None:
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.calibration(
            camera_profile="Adobe Color",
            red_hue=-5,
            blue_sat=12,
            photo_uuids=["u"],
        )

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    assert s["CameraProfile"] == "Adobe Color"
    assert s["RedHue"] == -5
    assert s["BlueSaturation"] == 12


@pytest.mark.asyncio
async def test_detail_sliders() -> None:
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.detail(
            sharpness=70,
            sharpen_radius=1.2,
            luminance_nr=25,
            color_nr=30,
            photo_uuids=["u"],
        )

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    assert s["Sharpness"] == 70
    assert s["SharpenRadius"] == 1.2
    assert s["LuminanceSmoothing"] == 25
    assert s["ColorNoiseReduction"] == 30


@pytest.mark.asyncio
async def test_effects_vignette_grain() -> None:
    captured: dict = {}
    handlers = {
        "develop.apply_settings": lambda p: captured.update(p) or {"touched": 1},
    }

    async def go(lr):
        await lr.develop.effects(
            vignette_amount=-25,
            vignette_midpoint=50,
            grain_amount=12,
            grain_size=25,
            photo_uuids=["u"],
        )

    _, _ = await _with_plugin(handlers, go)
    s = captured["settings"]
    assert s["PostCropVignetteAmount"] == -25
    assert s["PostCropVignetteMidpoint"] == 50
    assert s["GrainAmount"] == 12
    assert s["GrainSize"] == 25
