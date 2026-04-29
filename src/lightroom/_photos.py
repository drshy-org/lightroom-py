"""Photos sub-client: find, filter, select, iterate.

Reads via the SQLite fast-path. Selection writes go through the bridge plugin
(coming in a Phase 2.1 / Phase 3 follow-up).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from . import _sqlite as sql
from ._context import load_active_catalog
from ._core import ClientCore
from .exceptions import CatalogError
from .types import Photo

logger = logging.getLogger(__name__)


class PhotosAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    def _path(self):
        path = load_active_catalog()
        if path is None or not path.exists():
            raise CatalogError(
                "no active catalog. Run `lightroom catalog open <path/to/Catalog.lrcat>`."
            )
        return path

    async def list(
        self,
        *,
        rating_gte: int | None = None,
        rating_lte: int | None = None,
        camera: str | None = None,
        lens: str | None = None,
        keyword: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int | None = None,
    ) -> list[Photo]:
        path = self._path()
        rows = sql.list_photos(
            path,
            rating_gte=rating_gte,
            rating_lte=rating_lte,
            camera=camera,
            lens=lens,
            keyword=keyword,
            since=since,
            until=until,
            limit=limit,
        )
        return [
            Photo(
                uuid=r.uuid,
                filename=r.filename,
                rating=r.rating,
                color_label=r.color_label,
                keywords=[],  # populated via bridge / SQLite expansion later
            )
            for r in rows
        ]

    async def iter(
        self,
        *,
        chunk_size: int = 500,
        **filters: object,
    ) -> AsyncIterator[Photo]:
        # Phase 2: not streaming yet; just yield from the eager list.
        all_rows = await self.list(**filters)  # type: ignore[arg-type]
        for r in all_rows:
            yield r
        del chunk_size

    async def count(
        self,
        *,
        rating_gte: int | None = None,
        rating_lte: int | None = None,
        camera: str | None = None,
        lens: str | None = None,
        keyword: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> int:
        path = self._path()
        return sql.count_photos(
            path,
            rating_gte=rating_gte,
            rating_lte=rating_lte,
            camera=camera,
            lens=lens,
            keyword=keyword,
            since=since,
            until=until,
        )

    async def select(self, *uuids: str) -> None:
        """Set Lightroom's active selection to the given photo UUIDs.

        Goes through the bridge plugin since the active selection is live UI state.
        """
        await self._core.call("photos.select", {"uuids": list(uuids)})
