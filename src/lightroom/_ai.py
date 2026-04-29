"""AI sub-client: stage AI develop settings (Denoise, Masks, Generative Remove).

The Lightroom SDK lets us write the *settings* for AI features into a photo's
develop settings table, but **cannot trigger the actual AI compute**. The user
must click "Update AI Settings" in Lightroom for the model to run.

This sub-client exposes that limitation honestly: ``stage_*`` writes settings,
``prompt_update`` shows a dialog telling the user to run Update AI.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from ._core import ClientCore

logger = logging.getLogger(__name__)


class AIAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def stage_denoise(
        self,
        *,
        strength: int = 50,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Stage AI Denoise settings on the target photos.

        ``strength`` is 0..100, mapping to LR's AI Denoise amount slider.
        After staging, the user must run **Update AI Settings** in Lightroom
        for the actual denoise model to compute.
        """
        if not 0 <= strength <= 100:
            raise ValueError(f"strength must be 0..100, got {strength}")
        return await self._core.call(
            "ai.stage_denoise",
            {"strength": strength, "uuids": list(photo_uuids or [])},
        )

    async def prompt_update(self) -> dict:
        """Show a dialog in LR telling the user to click Update AI Settings.

        Blocks until the user dismisses the dialog.
        """
        return await self._core.call("ai.prompt_update", {})
