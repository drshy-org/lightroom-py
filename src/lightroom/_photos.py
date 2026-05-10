"""Photos sub-client: find, filter, select, iterate, navigate.

Reads via the SQLite fast-path. Selection writes go through the bridge plugin.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterable

from . import _sqlite as sql
from ._context import load_active_catalog
from ._core import ClientCore
from .exceptions import CatalogError
from .types import Photo

logger = logging.getLogger(__name__)

# Module-level alias because the `list` method in PhotosAPI shadows the
# builtin in class-scope annotation resolution (same gotcha as _collections.py).
_PhotoList = list[Photo]


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
        file_format: str | None = None,
        path_substring: str | None = None,
        color_label: str | None = None,
        iso_gte: int | None = None,
        iso_lte: int | None = None,
        aperture_gte: float | None = None,
        aperture_lte: float | None = None,
        focal_gte: float | None = None,
        focal_lte: float | None = None,
        has_gps: bool | None = None,
    ) -> _PhotoList:
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
            file_format=file_format,
            path_substring=path_substring,
            color_label=color_label,
            iso_gte=iso_gte,
            iso_lte=iso_lte,
            aperture_gte=aperture_gte,
            aperture_lte=aperture_lte,
            focal_gte=focal_gte,
            focal_lte=focal_lte,
            has_gps=has_gps,
        )
        return [
            Photo(
                uuid=r.uuid,
                filename=r.filename,
                rating=r.rating,
                color_label=r.color_label,
                keywords=[],
                iso=r.iso,
                aperture=r.aperture,
                shutter_speed=r.shutter_speed,
                focal_length=r.focal_length,
                camera=r.camera,
                lens=r.lens,
                has_gps=r.has_gps,
                capture_time=r.capture_time,
            )
            for r in rows
        ]

    async def iter(
        self,
        *,
        chunk_size: int = 500,
        **filters: object,
    ) -> AsyncIterator[Photo]:
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
        file_format: str | None = None,
        path_substring: str | None = None,
        color_label: str | None = None,
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
            file_format=file_format,
            path_substring=path_substring,
            color_label=color_label,
        )

    async def find_by_path(self, path_substring: str, *, limit: int = 50) -> _PhotoList:
        """Convenience: find photos whose absolute path contains substring."""
        return await self.list(path_substring=path_substring, limit=limit)

    async def select(self, *uuids: str) -> None:
        """Set Lightroom's active selection to the given photo UUIDs."""
        await self._core.call("photos.select", {"uuids": list(uuids)})

    async def select_extend(self, *uuids: str) -> dict:
        """Add UUIDs to the current selection (don't replace)."""
        return await self._core.call("photos.select_extend", {"uuids": list(uuids)})

    async def select_all(self) -> dict:
        """Select all photos in the active source (folder/collection)."""
        return await self._core.call("photos.select_all", {})

    async def select_none(self) -> dict:
        """Clear the selection."""
        return await self._core.call("photos.select_none", {})

    async def select_inverse(self) -> dict:
        """Invert the current selection."""
        return await self._core.call("photos.select_inverse", {})

    async def next_photo(self) -> dict:
        """Move selection to the next photo (Library/Develop module)."""
        return await self._core.call("photos.next", {})

    async def previous_photo(self) -> dict:
        """Move selection to the previous photo."""
        return await self._core.call("photos.previous", {})

    # ---------- flag / pickStatus (v0.4) ----------

    async def flag_pick(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Mark photos as Picked (flagStatus = 1)."""
        return await self._core.call(
            "photos.set_pick_status",
            {"status": 1, "uuids": list(photo_uuids or [])},
        )

    async def flag_reject(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Mark photos as Rejected (flagStatus = -1)."""
        return await self._core.call(
            "photos.set_pick_status",
            {"status": -1, "uuids": list(photo_uuids or [])},
        )

    async def flag_clear(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Clear pick/reject flag (flagStatus = 0)."""
        return await self._core.call(
            "photos.set_pick_status",
            {"status": 0, "uuids": list(photo_uuids or [])},
        )

    # ---------- step ratings / color (v0.4) ----------

    async def rating_step(
        self,
        delta: int,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Increment rating by ``delta`` (clamped 0..5). Use +1 / -1 for keyboard parity."""
        return await self._core.call(
            "photos.rating_step",
            {"delta": delta, "uuids": list(photo_uuids or [])},
        )

    async def color_step(
        self,
        direction: int,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Cycle color label forward (+1) or back (-1) through none→red→yellow→green→blue→purple."""
        return await self._core.call(
            "photos.color_step",
            {"direction": direction, "uuids": list(photo_uuids or [])},
        )
