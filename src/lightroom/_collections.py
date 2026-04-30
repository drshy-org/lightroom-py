"""Collections sub-client: collections + smart collections."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from ._core import ClientCore

logger = logging.getLogger(__name__)

# Module-level aliases — needed because methods named `list` in the class
# below shadow the builtin in class-scope annotation resolution.
_UUIDs = list[str]
_Collection = dict[str, Any]


class CollectionsAPI:
    """Manage Lightroom collections (regular + smart).

    Read-side queries can also hit the SQLite fast-path via
    ``lightroom._sqlite``; bridge handlers are only needed for writes.
    """

    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def list(self) -> list[_Collection]:
        """List all collections in the active catalog.

        Returns ``[{"name", "kind": "collection"|"smart"|"group",
        "parent", "id", "photo_count"}, ...]``.
        """
        result = await self._core.call("collections.list", {})
        return list(result.get("collections") or [])

    async def create(
        self,
        name: str,
        *,
        parent: str | None = None,
    ) -> _Collection:
        """Create a new (regular) collection.

        ``parent`` is the name of an existing collection group, or None for
        top-level. Smart-collection creation is intentionally not exposed
        — that requires authoring an `LrCollectionSearchDescription` table,
        which is a much larger surface; punt to v0.4.
        """
        if not name:
            raise ValueError("name must be non-empty")
        return await self._core.call(
            "collections.create",
            {"name": name, "parent": parent},
        )

    async def add(
        self,
        collection: str,
        photo_uuids: Iterable[str],
    ) -> dict:
        """Add photos to a collection by name."""
        uuids = list(photo_uuids)
        if not uuids:
            raise ValueError("photo_uuids must be non-empty")
        return await self._core.call(
            "collections.add",
            {"collection": collection, "uuids": uuids},
        )

    async def remove(
        self,
        collection: str,
        photo_uuids: Iterable[str],
    ) -> dict:
        """Remove photos from a collection by name."""
        uuids = list(photo_uuids)
        if not uuids:
            raise ValueError("photo_uuids must be non-empty")
        return await self._core.call(
            "collections.remove",
            {"collection": collection, "uuids": uuids},
        )

    async def delete(self, collection: str) -> dict:
        """Delete a collection by name. Photos themselves are not affected."""
        if not collection:
            raise ValueError("collection name must be non-empty")
        return await self._core.call(
            "collections.delete",
            {"collection": collection},
        )

    async def get_photos(self, collection: str) -> _UUIDs:
        """Return the UUIDs of photos in a collection."""
        if not collection:
            raise ValueError("collection name must be non-empty")
        result = await self._core.call(
            "collections.get_photos",
            {"collection": collection},
        )
        return list(result.get("uuids") or [])
