"""Local bridge server.

The Lua plugin polls this server for commands and POSTs results back. The
Python side is the server because LR's ``LrSocket`` / ``LrHttp`` modules are
outbound-only — the plugin physically cannot host a server.

Phase 0: scaffold only. Real handlers and the long-poll loop arrive in Phase 1.
"""

from .protocol import CommandRequest, CommandResponse
from .server import LocalBridgeServer

__all__ = ["LocalBridgeServer", "CommandRequest", "CommandResponse"]
