"""Catalog sub-client: open / info / stats.

Reads use the SQLite fast-path against the active catalog path saved in the
per-profile context. The bridge plugin is consulted only for live state (e.g.
the path of the catalog currently open in Lightroom).
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import _sqlite as sql
from ._context import load_active_catalog, save_active_catalog
from ._core import ClientCore
from .exceptions import CatalogError
from .types import CatalogInfo

logger = logging.getLogger(__name__)


class CatalogAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    def _resolve_path(self) -> Path:
        path = load_active_catalog()
        if path is None:
            raise CatalogError(
                "no active catalog. Run `lightroom catalog open <path/to/Catalog.lrcat>`."
            )
        if not path.exists():
            raise CatalogError(f"active catalog path does not exist: {path}")
        return path

    async def info(self) -> CatalogInfo:
        """Catalog summary via SQLite."""
        path = self._resolve_path()
        summary = sql.get_catalog_summary(path)
        return CatalogInfo(
            path=summary.path,
            lightroom_version=None,  # populated via bridge in Phase 4
            photo_count=summary.photos,
            extra={
                "sqlite_user_version": summary.sqlite_user_version,
                "earliest_capture": summary.earliest_capture,
                "latest_capture": summary.latest_capture,
            },
        )

    async def stats(self) -> dict[str, int]:
        path = self._resolve_path()
        s = sql.get_catalog_stats(path)
        return {
            "photos": s.photos,
            "folders": s.folders,
            "keywords": s.keywords,
            "collections": s.collections,
            "smart_collections": s.smart_collections,
        }

    async def open(self, path: str | Path) -> CatalogInfo:
        """Set this catalog as active for `lightroom-py` (does NOT switch LR)."""
        resolved = save_active_catalog(path)
        return await self.info() if resolved else CatalogInfo(path=resolved)

    async def active_path(self) -> Path | None:
        return load_active_catalog()
