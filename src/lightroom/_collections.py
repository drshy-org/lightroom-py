"""Collections sub-client: collections + smart collections."""

from __future__ import annotations

import logging
from typing import Any

from ._core import ClientCore

logger = logging.getLogger(__name__)

# Module-level aliases — needed because methods named `list` in the class
# below shadow the builtin in class-scope annotation resolution.
_UUIDs = list[str]
_Collection = dict[str, Any]


class CollectionsAPI:
    def __init__(self, core: ClientCore) -> None:
        self._core = core

    async def list(self) -> list[_Collection]:
        raise NotImplementedError

    async def create(self, name: str, *, parent: str | None = None) -> _Collection:
        del name, parent
        raise NotImplementedError

    async def add(self, collection: str, photo_uuids: _UUIDs) -> None:
        del collection, photo_uuids
        raise NotImplementedError

    async def remove(self, collection: str, photo_uuids: _UUIDs) -> None:
        del collection, photo_uuids
        raise NotImplementedError

    async def delete(self, collection: str) -> None:
        del collection
        raise NotImplementedError
