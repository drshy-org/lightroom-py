"""Metadata sub-client: keywords, ratings, color labels, IPTC, GPS.

Two paths:

- **Bridge plugin** (default): goes through the Lua plugin's
  ``metadata.*`` handlers. Works on photos by UUID or on the active
  selection. Honest cost: each call is one bridge round-trip.
- **ExifTool/XMP fast-path** (``via_xmp=True``): writes XMP sidecars (or
  in-place for JPEG/TIFF/PSD/DNG) using ExifTool, then asks the bridge to
  call ``photo:readMetadata()`` on those photos so the catalog re-syncs.
  Orders of magnitude faster for batches of thousands.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from . import _sqlite as sql
from ._context import load_active_catalog
from ._core import ClientCore
from .exceptions import CatalogError

logger = logging.getLogger(__name__)


VALID_COLOR_LABELS = {"", "red", "yellow", "green", "blue", "purple"}


class MetadataAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    # ---------- bridge path ----------

    async def add_keywords(
        self,
        keywords: list[str],
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        return await self._core.call(
            "metadata.add_keywords",
            {"keywords": list(keywords), "uuids": list(photo_uuids or [])},
        )

    async def remove_keywords(
        self,
        keywords: list[str],
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        return await self._core.call(
            "metadata.remove_keywords",
            {"keywords": list(keywords), "uuids": list(photo_uuids or [])},
        )

    async def set_rating(
        self,
        rating: int,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        """Set the rating (1..5) or clear it (0).

        Mirrors LR's keyboard-shortcut behaviour: 0 clears the rating
        (the underlying ``setRawMetadata`` call rejects 0 as a literal
        value, so the bridge plugin maps 0 → nil before calling LR).
        """
        if not 0 <= rating <= 5:
            raise ValueError(f"rating must be 0..5, got {rating}")
        return await self._core.call(
            "metadata.set_rating",
            {"rating": rating, "uuids": list(photo_uuids or [])},
        )

    async def set_color_label(
        self,
        label: str,
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        if label not in VALID_COLOR_LABELS:
            raise ValueError(f"label must be one of {sorted(VALID_COLOR_LABELS)}, got {label!r}")
        return await self._core.call(
            "metadata.set_color_label",
            {"label": label, "uuids": list(photo_uuids or [])},
        )

    async def set_iptc(
        self,
        fields: dict[str, str],
        *,
        photo_uuids: Iterable[str] | None = None,
    ) -> dict:
        if not fields:
            raise ValueError("fields must be a non-empty dict")
        return await self._core.call(
            "metadata.set_iptc",
            {"fields": fields, "uuids": list(photo_uuids or [])},
        )

    async def write_xmp(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Tell LR to write XMP sidecars (or embedded XMP) for the photos."""
        return await self._core.call(
            "metadata.write_xmp",
            {"uuids": list(photo_uuids or [])},
        )

    async def read_xmp(self, *, photo_uuids: Iterable[str] | None = None) -> dict:
        """Tell LR to re-read XMP from disk for the photos.

        Used after :meth:`fast_write_xmp` to sync external XMP changes back
        into the catalog.
        """
        return await self._core.call(
            "metadata.read_xmp",
            {"uuids": list(photo_uuids or [])},
        )

    # ---------- ExifTool fast-path ----------

    async def fast_write_xmp(
        self,
        tags_by_uuid: dict[str, dict],
        *,
        sync_back: bool = True,
    ) -> dict:
        """Write XMP for many photos via ExifTool, then optionally sync to LR.

        Resolves UUIDs to file paths via SQLite, runs a single batched
        ExifTool process, and (if ``sync_back``) calls ``metadata.read_xmp``
        on the bridge so LR re-reads the sidecars.

        Returns ``{"written": N, "missing": [...], "synced": N}``.
        """
        from ._exiftool import ExifTool, ExifToolNotFoundError

        catalog = load_active_catalog()
        if catalog is None or not Path(catalog).exists():
            raise CatalogError("no active catalog. Run `lightroom catalog open ...`.")

        paths = sql.resolve_paths(catalog, list(tags_by_uuid.keys()))
        missing = sorted(set(tags_by_uuid) - set(paths))

        by_path: dict[str | Path, dict] = {}
        synced_uuids: list[str] = []
        for uuid, tags in tags_by_uuid.items():
            p = paths.get(uuid)
            if p is None:
                continue
            by_path[p] = tags
            synced_uuids.append(uuid)

        if not by_path:
            return {"written": 0, "missing": missing, "synced": 0}

        try:
            with ExifTool() as et:
                written = et.write_tags_batch(by_path)
        except ExifToolNotFoundError as exc:
            raise CatalogError(str(exc)) from exc

        synced = 0
        if sync_back and synced_uuids:
            result = await self.read_xmp(photo_uuids=synced_uuids)
            synced = int(result.get("touched", 0)) if isinstance(result, dict) else 0

        return {"written": written, "missing": missing, "synced": synced}
