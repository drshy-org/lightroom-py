"""Exception hierarchy for lightroom-py.

All custom errors derive from :class:`LightroomError` so callers can catch the
package's errors with a single ``except``.
"""

from __future__ import annotations


class LightroomError(Exception):
    """Base class for all lightroom-py errors."""


class BridgeNotRunningError(LightroomError):
    """The local bridge server is not running, or the LR plugin isn't polling."""


class PluginHandshakeError(LightroomError):
    """The LR plugin connected but failed token / version handshake."""


class CatalogError(LightroomError):
    """An operation against the catalog failed (missing file, locked, etc.)."""


class CommandTimeoutError(LightroomError):
    """A bridge command was sent but the plugin did not respond in time."""


class CommandFailedError(LightroomError):
    """The plugin returned an error result for a command."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
