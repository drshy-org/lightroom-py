"""lightroom-py — unofficial Python library for automating Adobe Lightroom Classic.

Three faces, mirroring the notebooklm-py shape:

- **Python API**: :class:`LightroomClient` async context manager with namespaced
  sub-clients (``catalog``, ``photos``, ``develop``, ``metadata``,
  ``collections``, ``library``, ``ai``, ``edit_in``).
- **CLI**: ``lightroom`` command tree (see ``lightroom --help``).
- **Agent skill**: ``SKILL.md`` installable into Claude Code / Codex via
  ``lightroom skill install``.

Example::

    import asyncio
    from lightroom import LightroomClient

    async def main():
        async with LightroomClient.connect() as lr:
            info = await lr.catalog.info()
            print(info)

    asyncio.run(main())
"""

from __future__ import annotations

from .client import LightroomClient
from .exceptions import (
    BridgeNotRunningError,
    CatalogError,
    LightroomError,
    PluginHandshakeError,
)

__version__ = "0.4.2"

__all__ = [
    "LightroomClient",
    "LightroomError",
    "BridgeNotRunningError",
    "PluginHandshakeError",
    "CatalogError",
    "__version__",
]
