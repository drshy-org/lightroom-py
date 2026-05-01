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
