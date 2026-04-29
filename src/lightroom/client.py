"""Top-level :class:`LightroomClient` — the public API entry point.

Mirrors notebooklm-py's ``NotebookLMClient`` shape: an async context manager
that owns a transport ``_core`` and exposes one attribute per noun.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ._ai import AIAPI
from ._bridge_state import load_bridge_state
from ._catalog import CatalogAPI
from ._collections import CollectionsAPI
from ._core import DEFAULT_TIMEOUT, ClientCore
from ._develop import DevelopAPI
from ._edit_in import EditInAPI
from ._library import LibraryAPI
from ._metadata import MetadataAPI
from ._photos import PhotosAPI

logger = logging.getLogger(__name__)

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 8765


class LightroomClient:
    """Async client for Adobe Lightroom Classic.

    Provides namespaced sub-clients:

    - :attr:`catalog` — open / info / stats
    - :attr:`photos` — list / find / select
    - :attr:`develop` — presets, settings, sliders
    - :attr:`metadata` — keywords, ratings, IPTC, GPS
    - :attr:`collections` — create / add / remove
    - :attr:`library` — import / export / stacks
    - :attr:`ai` — stage AI develop settings
    - :attr:`edit_in` — external-tool round-trip

    Usage::

        async with LightroomClient.connect() as lr:
            info = await lr.catalog.info()
            photos = await lr.photos.list(rating_gte=4)
    """

    def __init__(
        self,
        bridge_url: str,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        *,
        require_bridge: bool = True,
    ) -> None:
        self._core = ClientCore(bridge_url=bridge_url, token=token, timeout=timeout)
        self._require_bridge = require_bridge

        self.catalog = CatalogAPI(self._core)
        self.photos = PhotosAPI(self._core)
        self.develop = DevelopAPI(self._core)
        self.metadata = MetadataAPI(self._core)
        self.collections = CollectionsAPI(self._core)
        self.library = LibraryAPI(self._core)
        self.ai = AIAPI(self._core)
        self.edit_in = EditInAPI(self._core)

    @classmethod
    def connect(
        cls,
        host: str | None = None,
        port: int | None = None,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        *,
        require_bridge: bool = True,
    ) -> LightroomClient:
        """Construct a client pointing at a local bridge server.

        Resolution order for each of host/port/token:
            1. explicit kwarg
            2. ``LIGHTROOM_BRIDGE_HOST`` / ``LIGHTROOM_BRIDGE_PORT`` /
               ``LIGHTROOM_BRIDGE_TOKEN`` env var
            3. persisted state in ``$LIGHTROOM_HOME/profiles/<profile>/bridge.json``
               (written by ``lightroom bridge start``)
            4. built-in default (only for host/port — no token default)

        Pass ``require_bridge=False`` for read-only flows (catalog stats /
        photos list) that hit the SQLite fast-path and never touch the bridge.
        """
        state = load_bridge_state() or {}

        host = (
            host
            or os.environ.get("LIGHTROOM_BRIDGE_HOST")
            or state.get("host")
            or DEFAULT_BRIDGE_HOST
        )

        port_str = os.environ.get("LIGHTROOM_BRIDGE_PORT")
        if port is None:
            if port_str:
                port = int(port_str)
            elif state.get("port"):
                port = int(state["port"])
            else:
                port = DEFAULT_BRIDGE_PORT

        token = token or os.environ.get("LIGHTROOM_BRIDGE_TOKEN") or state.get("token")

        url = f"http://{host}:{port}"
        return cls(bridge_url=url, token=token, timeout=timeout, require_bridge=require_bridge)

    async def __aenter__(self) -> LightroomClient:
        if self._require_bridge:
            await self._core.open()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._require_bridge:
            await self._core.close()

    @property
    def bridge_url(self) -> str:
        return self._core.bridge_url

    async def ping(self, *, timeout: float = 10.0) -> dict[str, Any]:
        """Round-trip a ping through the bridge → plugin → back.

        Returns the plugin's reply (typically ``{"pong": True, "lr_version": ...}``).
        """
        return await self._core.call("ping", {}, timeout=timeout)
