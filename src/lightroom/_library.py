"""Library sub-client: import, export, stacks, virtual copies, folders."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from ._core import ClientCore

logger = logging.getLogger(__name__)


class LibraryAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def list_folders(self) -> list[dict]:
        """Return the catalog's folder tree as a flat list with depth markers."""
        result = await self._core.call("library.list_folders", {})
        return list(result.get("folders") or [])

    async def export(
        self,
        out_dir: str | Path,
        *,
        photo_uuids: Iterable[str] | None = None,
        format: str = "TIFF",
        quality: int = 95,
        color_space: str = "AdobeRGB",
    ) -> list[dict]:
        """Export selected photos.

        Backed by the same Lua handler as :meth:`EditInAPI.export`, just
        re-exposed under ``library`` for ergonomic mapping with PLAN.md.
        """
        result = await self._core.call(
            "edit_in.export",
            {
                "uuids": list(photo_uuids or []),
                "out_dir": str(Path(out_dir).expanduser().resolve()),
                "format": format,
                "quality": quality,
                "color_space": color_space,
            },
        )
        return list(result.get("exported") or [])

    async def make_virtual_copy(
        self,
        photo_uuid: str,
        *,
        copy_name: str | None = None,
    ) -> dict:
        """Create a virtual copy of a photo.

        ⚠️ **Not implementable in v0.3.0** (verified against LR Classic 15.3).
        The Lightroom SDK does not expose a public API for creating virtual
        copies — neither ``catalog:createVirtualCopies`` nor
        ``photo:createVirtualCopy`` exists. Virtual copies remain a UI-only
        feature. Use **Photo → Create Virtual Copy** in the LR UI manually.

        Calling this method raises :class:`CommandFailedError` from the
        bridge plugin with a clear message.
        """
        return await self._core.call(
            "library.make_virtual_copy",
            {"uuids": [photo_uuid], "copy_name": copy_name},
        )

    async def stack(self, photo_uuids: list[str]) -> dict:
        """Stack photos together. First photo becomes the top of the stack."""
        if len(photo_uuids) < 2:
            raise ValueError("stack requires at least 2 photos")
        return await self._core.call(
            "library.stack",
            {"uuids": list(photo_uuids)},
        )

    async def import_photos(
        self,
        paths: list[str | Path],
        *,
        copy: bool = False,
        collection: str | None = None,
    ) -> list[str]:
        """Import the given files / folders into the catalog.

        ⚠️ **Not implemented in v0.3.0.** ``catalog:addPhoto`` has the same
        yieldability issue as ``edit_in.import_as_stack`` against LR
        Classic 15.3 — see notes in :mod:`lightroom._edit_in`. Punted to a
        future release once the canonical Adobe pattern is verified.
        """
        del paths, copy, collection
        raise NotImplementedError(
            "library.import_photos is not implemented in v0.3.0 — see "
            "edit_in.import_as_stack for the same underlying yieldability "
            "issue. Use Lightroom's File → Import Photos UI for now."
        )
