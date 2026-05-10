"""Develop sub-client: presets, slider settings, settings-table application.

Two paths into the Develop module:

- ``apply_settings`` / ``apply_preset`` — works on any photo from a task,
  doesn't require the Develop module to be focused.
- ``set`` — drives ``LrDevelopController`` live; only works while the user
  is in the Develop module on the target photo.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from ._core import ClientCore

logger = logging.getLogger(__name__)


class DevelopAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def list_presets(self) -> list[dict]:
        """Return all develop presets across all folders.

        Each entry is ``{"folder": str, "name": str, "uuid": str}``.
        """
        result = await self._core.call("develop.list_presets", {})
        return list(result.get("presets") or [])

    async def apply_preset(
        self,
        preset: str,
        *,
        folder: str | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Apply a develop preset by name to the given photos (or selection).

        Pass ``folder`` to disambiguate when the same preset name lives in
        multiple folders. Without it, the first match wins.
        """
        params: dict[str, Any] = {
            "preset": preset,
            "uuids": list(photo_uuids or []),
        }
        if folder:
            params["folder"] = folder
        return await self._core.call("develop.apply_preset", params)

    async def apply_settings(
        self,
        settings: dict[str, Any],
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Apply a raw develop-settings dictionary.

        Keys are LR's internal slider names (``Exposure2012``, ``Contrast2012``,
        ``Highlights2012``, ``Shadows2012``, ``Whites2012``, ``Blacks2012``,
        ``Clarity2012``, ``Dehaze``, ``Vibrance``, ``Saturation``,
        ``Temperature``, ``Tint``, …). See LR SDK docs for the full key set.
        """
        if not settings:
            raise ValueError("settings must be a non-empty dict")
        return await self._core.call(
            "develop.apply_settings",
            {"settings": settings, "uuids": list(photo_uuids or [])},
        )

    async def get_settings(self, photo_uuid: str) -> dict[str, Any]:
        """Return the raw develop-settings table for one photo."""
        result = await self._core.call(
            "develop.get_settings",
            {"uuids": [photo_uuid]},
        )
        return (result.get("settings") or {}).get(photo_uuid) or {}

    async def copy(self, src_uuid: str, dst_uuids: list[str]) -> dict:
        """Copy develop settings from one photo to many."""
        if not dst_uuids:
            raise ValueError("dst_uuids must be a non-empty list")
        return await self._core.call(
            "develop.copy",
            {"src": src_uuid, "dsts": list(dst_uuids)},
        )

    async def reset(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Reset develop settings to defaults for the given photos."""
        return await self._core.call(
            "develop.reset",
            {"uuids": list(photo_uuids or [])},
        )

    async def set(self, **slider_values: float) -> dict:
        """Live-drive sliders via ``LrDevelopController``.

        Only works while the user is in the **Develop module** on the target
        photo. The handler will switch to Develop module first, then push
        each slider value. Common sliders:

        - ``Exposure``, ``Contrast``, ``Highlights``, ``Shadows``,
          ``Whites``, ``Blacks``, ``Clarity``, ``Dehaze``, ``Vibrance``,
          ``Saturation``, ``Temperature``, ``Tint``, ``Sharpness``.
        """
        if not slider_values:
            raise ValueError("at least one slider=value pair required")
        return await self._core.call("develop.set", {"values": slider_values})

    # ---------- tone curve (v0.4) ----------

    async def curve_get(
        self,
        photo_uuid: str,
        *,
        channel: str = "rgb",
    ) -> dict[str, Any]:
        """Return the tone curve for one photo on the given channel.

        ``channel``: one of ``"rgb"``, ``"red"``, ``"green"``, ``"blue"``.
        Returns ``{"name": "Linear|Medium Contrast|...|Custom",
        "points": [x1, y1, x2, y2, ...], "channel": ...}``.
        """
        if channel not in {"rgb", "red", "green", "blue"}:
            raise ValueError(f"channel must be rgb/red/green/blue, got {channel!r}")
        result = await self._core.call(
            "develop.curve_get",
            {"uuids": [photo_uuid], "channel": channel},
        )
        return (result.get("curves") or {}).get(photo_uuid) or {}

    async def curve_set(
        self,
        points: list[float],
        *,
        channel: str = "rgb",
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Apply a custom tone curve.

        ``points`` is a flat list of ``[x1, y1, x2, y2, ...]`` where x and y
        are 0..255. Must have even length ≥ 4.
        """
        if channel not in {"rgb", "red", "green", "blue"}:
            raise ValueError(f"channel must be rgb/red/green/blue, got {channel!r}")
        if len(points) < 4 or len(points) % 2 != 0:
            raise ValueError("points must be a flat [x,y,...] list with even length ≥ 4")
        return await self._core.call(
            "develop.curve_set",
            {"points": list(points), "channel": channel, "uuids": list(photo_uuids or [])},
        )

    async def curve_preset(
        self,
        name: str,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Apply a named tone-curve preset.

        ``name``: one of ``"Linear"``, ``"Medium Contrast"``,
        ``"Strong Contrast"``, ``"Custom"``.
        """
        valid = {"Linear", "Medium Contrast", "Strong Contrast", "Custom"}
        if name not in valid:
            raise ValueError(f"name must be one of {sorted(valid)}, got {name!r}")
        return await self._core.call(
            "develop.curve_preset",
            {"name": name, "uuids": list(photo_uuids or [])},
        )

    # ---------- snapshots (v0.4) ----------

    async def snapshot_create(
        self,
        name: str,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Create a develop snapshot named ``name`` on each target photo."""
        if not name:
            raise ValueError("name must be non-empty")
        return await self._core.call(
            "develop.snapshot_create",
            {"name": name, "uuids": list(photo_uuids or [])},
        )

    async def snapshot_list(
        self,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict[str, list[dict]]:
        """List develop snapshots for the target photos.

        Returns ``{uuid: [{"name": "..."}, ...], ...}``.
        """
        result = await self._core.call(
            "develop.snapshot_list",
            {"uuids": list(photo_uuids or [])},
        )
        return result.get("snapshots") or {}

    # ---------- process version (v0.4) ----------

    async def process_version_get(self, photo_uuid: str) -> str:
        """Return the photo's process version (e.g. ``"11.0"`` for PV2012)."""
        result = await self._core.call(
            "develop.process_version_get",
            {"uuids": [photo_uuid]},
        )
        return (result.get("versions") or {}).get(photo_uuid, "unknown")

    async def process_version_set(
        self,
        version: str,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set the process version. Common values: ``"11.0"`` (PV2012),
        ``"6.7"`` (PV2010), ``"5.0"`` (PV2003)."""
        if not version:
            raise ValueError("version must be non-empty")
        return await self._core.call(
            "develop.process_version_set",
            {"version": version, "uuids": list(photo_uuids or [])},
        )

    # ---------- targeted resets (v0.4) ----------

    async def reset_crop(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Reset only the crop. (Switches to Develop module per photo.)"""
        return await self._core.call(
            "develop.reset_crop",
            {"uuids": list(photo_uuids or [])},
        )

    async def reset_masking(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Clear all masks (mask groups, gradient/circular/paint corrections)."""
        return await self._core.call(
            "develop.reset_masking",
            {"uuids": list(photo_uuids or [])},
        )

    async def reset_spot(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Clear spot-removal / healing edits."""
        return await self._core.call(
            "develop.reset_spot",
            {"uuids": list(photo_uuids or [])},
        )

    async def reset_redeye(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Clear red-eye corrections."""
        return await self._core.call(
            "develop.reset_redeye",
            {"uuids": list(photo_uuids or [])},
        )

    async def reset_transforms(
        self,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Reset upright / perspective / lens-correction transforms."""
        return await self._core.call(
            "develop.reset_transforms",
            {"uuids": list(photo_uuids or [])},
        )

    # ---------- paste-settings (v0.4) ----------

    async def paste_settings(
        self,
        settings: dict[str, Any],
        *,
        subset: list[str] | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Apply a settings dict to many photos, optionally filtered by ``subset``.

        Mirrors LR's "Paste Settings…" dialog: pass the source photo's
        :meth:`get_settings` output as ``settings`` and a ``subset`` list to
        only paste specific keys.
        """
        if not settings:
            raise ValueError("settings must be a non-empty dict")
        params: dict[str, Any] = {
            "settings": settings,
            "uuids": list(photo_uuids or []),
        }
        if subset:
            params["subset"] = list(subset)
        return await self._core.call("develop.paste_settings", params)

    # ---------- masks (v0.4) ----------

    async def mask_list(
        self,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict[str, dict[str, int]]:
        """Summarize masks present on each target photo.

        Returns ``{uuid: {ai_masks, gradient, circular, paint, retouch_areas, red_eye}}``
        — counts of each mask category. Use :meth:`get_settings` for the
        full per-mask geometry.

        Reads via SQLite-backed ``getDevelopSettings`` (no writes).
        """
        result = await self._core.call(
            "develop.mask_list",
            {"uuids": list(photo_uuids or [])},
        )
        return result.get("masks") or {}

    async def mask_clear(
        self,
        *,
        kind: str = "all",
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Clear masks of the given ``kind``.

        ``kind``: ``"all"`` (default) | ``"ai"`` | ``"gradient"`` | ``"circular"`` | ``"paint"``.
        """
        valid = {"all", "ai", "gradient", "circular", "paint"}
        if kind not in valid:
            raise ValueError(f"kind must be one of {sorted(valid)}, got {kind!r}")
        return await self._core.call(
            "develop.mask_clear",
            {"kind": kind, "uuids": list(photo_uuids or [])},
        )

    # ---------- Typed wrappers (v0.5) ----------
    # These are pure-Python convenience methods over apply_settings. They
    # accept typed parameters (None = leave alone), build the Adobe-key
    # settings dict, and dispatch through the same bridge handler. No new
    # Lua handlers needed; zero LR-side risk.

    async def crop(
        self,
        *,
        top: float | None = None,
        left: float | None = None,
        right: float | None = None,
        bottom: float | None = None,
        angle: float | None = None,
        constrain_to_warp: bool | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set crop rectangle (0..1 normalised) and rotation angle (degrees).

        ``top``/``left``/``right``/``bottom`` are 0..1 fractions of the photo's
        post-rotation bounding box. ``angle`` is degrees, positive = clockwise.
        ``constrain_to_warp`` shrinks the crop to stay inside Upright transforms.
        """
        return await self._apply_typed(
            {
                "CropTop": top,
                "CropLeft": left,
                "CropRight": right,
                "CropBottom": bottom,
                "CropAngle": angle,
                "CropConstrainToWarp": constrain_to_warp,
            },
            photo_uuids,
        )

    async def hsl(
        self,
        *,
        hue: dict[str, float] | None = None,
        saturation: dict[str, float] | None = None,
        luminance: dict[str, float] | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set HSL adjustments per color band.

        Each of ``hue`` / ``saturation`` / ``luminance`` is a dict mapping color
        band → value (-100..100). Bands: ``red``, ``orange``, ``yellow``,
        ``green``, ``aqua``, ``blue``, ``purple``, ``magenta``.

        Example: ``hsl(saturation={"red": -10, "orange": 5})``
        """
        bands = ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")
        s: dict[str, Any] = {}
        for src, prefix in (
            (hue, "HueAdjustment"),
            (saturation, "SaturationAdjustment"),
            (luminance, "LuminanceAdjustment"),
        ):
            if not src:
                continue
            for band, value in src.items():
                key = band.title()
                if key not in bands:
                    raise ValueError(f"unknown HSL band {band!r}; expected one of {bands}")
                s[f"{prefix}{key}"] = float(value)
        return await self._apply_typed(s, photo_uuids)

    async def color_grade(
        self,
        *,
        shadow_hue: float | None = None,
        shadow_sat: float | None = None,
        shadow_lum: float | None = None,
        midtone_hue: float | None = None,
        midtone_sat: float | None = None,
        midtone_lum: float | None = None,
        highlight_hue: float | None = None,
        highlight_sat: float | None = None,
        highlight_lum: float | None = None,
        global_hue: float | None = None,
        global_sat: float | None = None,
        global_lum: float | None = None,
        blending: float | None = None,
        balance: float | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set color-grading 3-way wheels + global wheel + blending/balance.

        Hues are 0..360, saturations 0..100, luminance -100..100.
        Blending 0..100 controls shadow↔highlight overlap.
        Balance -100..100 shifts the tonal break point.

        LR Classic 15.3 quirk: the new ``ColorGrade*`` schema works for
        Midtone / Global / all Lum keys, but **Shadow & Highlight Hue/Sat
        and the Balance slider are still routed through legacy
        ``SplitToning*`` keys**. This method translates transparently — you
        don't need to know which is which. Verified empirically against
        LR 15.3, 2026-05-10.
        """
        s: dict[str, Any] = {
            # New schema — works directly:
            "ColorGradeMidtoneHue": midtone_hue,
            "ColorGradeMidtoneSat": midtone_sat,
            "ColorGradeMidtoneLum": midtone_lum,
            "ColorGradeShadowLum": shadow_lum,
            "ColorGradeHighlightLum": highlight_lum,
            "ColorGradeGlobalHue": global_hue,
            "ColorGradeGlobalSat": global_sat,
            "ColorGradeGlobalLum": global_lum,
            "ColorGradeBlending": blending,
            # Legacy schema — required for Shadow/Highlight Hue+Sat + Balance:
            "SplitToningShadowHue": shadow_hue,
            "SplitToningShadowSaturation": shadow_sat,
            "SplitToningHighlightHue": highlight_hue,
            "SplitToningHighlightSaturation": highlight_sat,
            "SplitToningBalance": balance,
        }
        legacy_keys = (
            "SplitToningShadowHue",
            "SplitToningShadowSaturation",
            "SplitToningHighlightHue",
            "SplitToningHighlightSaturation",
            "SplitToningBalance",
        )
        if any(s.get(k) is not None for k in legacy_keys):
            s["EnableSplitToning"] = True
        return await self._apply_typed(s, photo_uuids)

    async def transform(
        self,
        *,
        vertical: float | None = None,
        horizontal: float | None = None,
        rotate: float | None = None,
        scale: float | None = None,
        x_offset: float | None = None,
        y_offset: float | None = None,
        aspect: float | None = None,
        upright_mode: str | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set Upright / Transform panel values.

        ``upright_mode``: ``"off"`` | ``"auto"`` | ``"level"`` | ``"vertical"`` | ``"full"``.
        Other params are -100..100 sliders (rotate is degrees).
        """
        upright_map = {"off": 0, "auto": 1, "level": 2, "vertical": 3, "full": 4}
        upright_value: int | None = None
        if upright_mode is not None:
            key = upright_mode.lower()
            if key not in upright_map:
                raise ValueError(
                    f"upright_mode must be one of {list(upright_map)}, got {upright_mode!r}"
                )
            upright_value = upright_map[key]
        return await self._apply_typed(
            {
                "PerspectiveVertical": vertical,
                "PerspectiveHorizontal": horizontal,
                "PerspectiveRotate": rotate,
                "PerspectiveScale": scale,
                "PerspectiveX": x_offset,
                "PerspectiveY": y_offset,
                "PerspectiveAspect": aspect,
                "PerspectiveUpright": upright_value,
            },
            photo_uuids,
        )

    async def lens_correction(
        self,
        *,
        enable_profile: bool | None = None,
        distortion_amount: float | None = None,
        vignetting_amount: float | None = None,
        chromatic_aberration_scale: float | None = None,
        remove_chromatic_aberration: bool | None = None,
        auto_lateral_ca: bool | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set Lens Correction panel values.

        ``enable_profile`` toggles "Enable Profile Corrections". Distortion
        amount and vignetting amount are 0..100 (percent of profile applied).
        """
        return await self._apply_typed(
            {
                "LensProfileEnable": (1 if enable_profile else 0)
                if enable_profile is not None
                else None,
                "LensProfileDistortionScale": distortion_amount,
                "LensProfileVignettingScale": vignetting_amount,
                "LensProfileChromaticAberrationScale": chromatic_aberration_scale,
                "RemoveChromaticAberration": remove_chromatic_aberration,
                "AutoLateralCA": (1 if auto_lateral_ca else 0)
                if auto_lateral_ca is not None
                else None,
            },
            photo_uuids,
        )

    async def calibration(
        self,
        *,
        camera_profile: str | None = None,
        shadow_tint: float | None = None,
        red_hue: float | None = None,
        red_sat: float | None = None,
        green_hue: float | None = None,
        green_sat: float | None = None,
        blue_hue: float | None = None,
        blue_sat: float | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set Camera Calibration panel values.

        ``camera_profile``: name of the embedded profile (e.g. "Adobe Color",
        "Adobe Standard", "Camera Neutral"). Hue/sat sliders are -100..100.
        """
        return await self._apply_typed(
            {
                "CameraProfile": camera_profile,
                "ShadowTint": shadow_tint,
                "RedHue": red_hue,
                "RedSaturation": red_sat,
                "GreenHue": green_hue,
                "GreenSaturation": green_sat,
                "BlueHue": blue_hue,
                "BlueSaturation": blue_sat,
            },
            photo_uuids,
        )

    async def detail(
        self,
        *,
        sharpness: float | None = None,
        sharpen_radius: float | None = None,
        sharpen_detail: float | None = None,
        sharpen_masking: float | None = None,
        luminance_nr: float | None = None,
        luminance_detail: float | None = None,
        luminance_contrast: float | None = None,
        color_nr: float | None = None,
        color_detail: float | None = None,
        color_smoothness: float | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set Detail panel values: sharpening + noise reduction.

        Sharpness 0..150, radius 0.5..3.0, detail 0..100, masking 0..100.
        Luminance/color NR 0..100. All -100..100 ranges follow LR's UI.
        """
        return await self._apply_typed(
            {
                "Sharpness": sharpness,
                "SharpenRadius": sharpen_radius,
                "SharpenDetail": sharpen_detail,
                "SharpenEdgeMasking": sharpen_masking,
                "LuminanceSmoothing": luminance_nr,
                "LuminanceNoiseReductionDetail": luminance_detail,
                "LuminanceNoiseReductionContrast": luminance_contrast,
                "ColorNoiseReduction": color_nr,
                "ColorNoiseReductionDetail": color_detail,
                "ColorNoiseReductionSmoothness": color_smoothness,
            },
            photo_uuids,
        )

    async def effects(
        self,
        *,
        vignette_amount: float | None = None,
        vignette_midpoint: float | None = None,
        vignette_feather: float | None = None,
        vignette_roundness: float | None = None,
        vignette_highlight_contrast: float | None = None,
        grain_amount: float | None = None,
        grain_size: float | None = None,
        grain_frequency: float | None = None,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set Effects panel values: post-crop vignette + grain.

        Vignette amount -100..100 (negative darkens). Grain amount 0..100.
        """
        return await self._apply_typed(
            {
                "PostCropVignetteAmount": vignette_amount,
                "PostCropVignetteMidpoint": vignette_midpoint,
                "PostCropVignetteFeather": vignette_feather,
                "PostCropVignetteRoundness": vignette_roundness,
                "PostCropVignetteHighlightContrast": vignette_highlight_contrast,
                "GrainAmount": grain_amount,
                "GrainSize": grain_size,
                "GrainFrequency": grain_frequency,
            },
            photo_uuids,
        )

    async def _apply_typed(
        self,
        keys: dict[str, Any],
        photo_uuids: Iterable[str] | None,
    ) -> dict:
        """Filter None values, apply via apply_settings.

        Returns a no-op result if no keys were specified (avoids round-tripping
        an empty settings dict to the bridge).
        """
        settings = {k: v for k, v in keys.items() if v is not None}
        if not settings:
            return {"touched": 0, "missing": [], "skipped": "no settings"}
        return await self.apply_settings(settings, photo_uuids=photo_uuids)
