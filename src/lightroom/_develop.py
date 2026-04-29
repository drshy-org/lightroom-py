"""Develop sub-client: presets, slider settings, settings-table application.

Two paths:

- ``apply_settings`` / ``apply_preset`` — works on any photo from a task,
  doesn't require the Develop module to be focused.
- ``set`` — drives ``LrDevelopController`` live; only works while the user is
  in the Develop module on the target photo.
"""

from __future__ import annotations

import logging
from typing import Any

from ._core import ClientCore

logger = logging.getLogger(__name__)


class DevelopAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def apply_preset(self, preset: str, *, photo_uuids: list[str] | None = None) -> None:
        """Apply a develop preset by name (or path) to the given photos.

        ``photo_uuids=None`` applies to LR's current selection.
        """
        del preset, photo_uuids
        raise NotImplementedError

    async def apply_settings(
        self,
        settings: dict[str, Any],
        *,
        photo_uuids: list[str] | None = None,
    ) -> None:
        """Apply a raw develop-settings dictionary."""
        del settings, photo_uuids
        raise NotImplementedError

    async def get_settings(self, photo_uuid: str) -> dict[str, Any]:
        del photo_uuid
        raise NotImplementedError

    async def copy(self, src_uuid: str, dst_uuids: list[str]) -> None:
        del src_uuid, dst_uuids
        raise NotImplementedError

    async def reset(self, *, photo_uuids: list[str] | None = None) -> None:
        del photo_uuids
        raise NotImplementedError

    async def set(self, **slider_values: float) -> None:
        """Live-drive sliders via ``LrDevelopController`` (Develop module only)."""
        del slider_values
        raise NotImplementedError
