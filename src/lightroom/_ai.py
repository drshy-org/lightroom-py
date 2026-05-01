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
        """Stage AI Denoise settings on the target photos. **EXPERIMENTAL.**

        ``strength`` is 0..100. The handler writes
        ``EnableAIDenoise=true`` + ``AIDenoiseAmount=N`` into the photo's
        develop settings via ``applyDevelopSettings``.

        **Verified against LR 15.3: this is currently a no-op.** Those key
        names are ignored by ``applyDevelopSettings`` — LR silently drops
        keys it doesn't recognize, and Adobe hasn't documented a public AI
        Denoise key for plugin authors. The call returns ``touched: N`` but
        a follow-up ``develop get-settings`` shows no AI keys present. For
        real AI Denoise compute, the user must run "Enhance → Denoise…"
        from LR's UI manually.

        Kept in the API for shape parity with PLAN.md's Phase 5; revisit if
        Adobe documents the keys (or community reverse-engineers them).
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

    async def stage_select_subject(
        self,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Stage AI Select-Subject mask settings. **EXPERIMENTAL no-op (v0.4).**

        Same SDK gap as :meth:`stage_denoise` — LR Classic 15.3 doesn't
        expose a public API to trigger AI mask creation. The handler
        writes ``EnableSubjectSelectMask`` keys but LR appears to ignore
        them. Kept for surface parity with lightroom-cli; document the
        limitation honestly to your users.

        For real subject selection, use Lightroom's Develop module masking
        panel manually after :meth:`prompt_update`.
        """
        return await self._core.call(
            "ai.stage_select_subject",
            {"uuids": list(photo_uuids or [])},
        )

    async def stage_select_sky(
        self,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Stage AI Select-Sky mask settings. **EXPERIMENTAL no-op (v0.4).**

        Same caveat as :meth:`stage_select_subject` — writes the keys but
        LR likely ignores them. Use LR's UI for real sky masking.
        """
        return await self._core.call(
            "ai.stage_select_sky",
            {"uuids": list(photo_uuids or [])},
        )
