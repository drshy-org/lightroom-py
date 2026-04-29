"""AI sub-client: stage AI develop settings (Denoise, Masks, Generative Remove).

The Lightroom SDK lets us write the *settings* for AI features into a photo's
develop settings table, but **cannot trigger the actual AI compute**. The user
must click "Update AI Settings" in Lightroom for the model to run.

This sub-client exposes that limitation honestly: ``stage_*`` writes settings,
``prompt_update`` shows a dialog telling the user to run Update AI.
"""

from __future__ import annotations

import logging

from ._core import ClientCore

logger = logging.getLogger(__name__)


class AIAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def stage_denoise(
        self, *, strength: int = 50, photo_uuids: list[str] | None = None
    ) -> None:
        """Stage AI Denoise settings. User must run Update AI to actually denoise."""
        del strength, photo_uuids
        raise NotImplementedError

    async def stage_select_subject(self, *, photo_uuids: list[str] | None = None) -> None:
        del photo_uuids
        raise NotImplementedError

    async def stage_select_sky(self, *, photo_uuids: list[str] | None = None) -> None:
        del photo_uuids
        raise NotImplementedError

    async def prompt_update(self) -> None:
        """Show a dialog in LR telling the user to click Update AI Settings."""
        raise NotImplementedError
