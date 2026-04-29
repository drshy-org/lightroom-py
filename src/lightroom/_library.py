"""Library sub-client: import, export, stacks, virtual copies, folders."""

from __future__ import annotations

import logging
from pathlib import Path

from ._core import ClientCore

logger = logging.getLogger(__name__)


class LibraryAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def import_photos(
        self,
        paths: list[str | Path],
        *,
        copy: bool = False,
        collection: str | None = None,
    ) -> list[str]:
        """Import the given files / folders into the catalog. Returns photo UUIDs."""
        del paths, copy, collection
        raise NotImplementedError

    async def export(
        self,
        photo_uuids: list[str],
        out_dir: str | Path,
        *,
        preset: str | None = None,
    ) -> list[Path]:
        del photo_uuids, out_dir, preset
        raise NotImplementedError

    async def list_folders(self) -> list[dict]:
        raise NotImplementedError

    async def stack(self, photo_uuids: list[str]) -> None:
        del photo_uuids
        raise NotImplementedError

    async def make_virtual_copy(self, photo_uuid: str) -> str:
        del photo_uuid
        raise NotImplementedError
