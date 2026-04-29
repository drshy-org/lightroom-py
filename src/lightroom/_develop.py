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
