"""aiohttp-based local bridge server.

Phase 1: full command queue + long-poll + plugin handshake + result-await.

Lifecycle::

    server = LocalBridgeServer(host="127.0.0.1", port=8765)
    await server.start()
    cmd_id = await server.enqueue("ping", {})
    response = await server.await_result(cmd_id, timeout=10)
    await server.stop()
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
import uuid
from collections import deque
from typing import Any

from .protocol import CommandRequest, CommandResponse

logger = logging.getLogger(__name__)

DEFAULT_POLL_WAIT_SECONDS = 30.0


class LocalBridgeServer:
    """Hosts the HTTP endpoints the Lua plugin polls.

    The Python side is the server because LR's ``LrSocket`` / ``LrHttp`` are
    outbound-only — the plugin physically cannot host a server.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: str | None = None,
        version: str = "0.6.0",
    ) -> None:
        self.host = host
        self.port = port
        self.token = token or secrets.token_hex(16)
        self.version = version

        self._runner: Any = None
        self._site: Any = None

        self._queue: deque[CommandRequest] = deque()
        self._queue_event = asyncio.Event()
        self._pending: dict[str, asyncio.Future[CommandResponse]] = {}

        self._plugin_session_id: str | None = None
        self._plugin_last_seen: float | None = None
        self._plugin_version: str | None = None
        self._lr_version: str | None = None

    # ---------- public API ----------

    async def start(self) -> None:
        from aiohttp import web

        app = web.Application()
        app.router.add_get("/health", self._health)
        app.router.add_post("/handshake", self._handshake)
        app.router.add_get("/poll", self._poll)
        app.router.add_post("/respond", self._respond)
        app.router.add_post("/enqueue", self._enqueue_http)
        app.router.add_get("/result/{cmd_id}", self._result_http)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info("Bridge server listening on http://%s:%s", self.host, self.port)

    async def stop(self) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def enqueue(self, method: str, params: dict[str, Any] | None = None) -> str:
        """Queue a command for the plugin and return its id."""
        cmd = CommandRequest(id=uuid.uuid4().hex, method=method, params=params or {})
        loop = asyncio.get_running_loop()
        self._pending[cmd.id] = loop.create_future()
        self._queue.append(cmd)
        self._queue_event.set()
        return cmd.id

    async def await_result(self, cmd_id: str, timeout: float | None = None) -> CommandResponse:
        """Block until the plugin responds to ``cmd_id``."""
        fut = self._pending.get(cmd_id)
        if fut is None:
            raise KeyError(f"unknown command id: {cmd_id}")
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        finally:
            if fut.done():
                self._pending.pop(cmd_id, None)

    @property
    def plugin_connected(self) -> bool:
        return self._plugin_session_id is not None

    @property
    def plugin_last_seen_seconds_ago(self) -> float | None:
        if self._plugin_last_seen is None:
            return None
        return max(0.0, time.monotonic() - self._plugin_last_seen)

    # ---------- HTTP handlers ----------

    async def _health(self, request):
        from aiohttp import web

        del request
        return web.json_response(
            {
                "ok": True,
                "version": self.version,
                "plugin_session_id": self._plugin_session_id,
                "plugin_version": self._plugin_version,
                "lr_version": self._lr_version,
                "plugin_last_seen_seconds_ago": self.plugin_last_seen_seconds_ago,
                "queue_depth": len(self._queue),
                "pending": len(self._pending),
            }
        )

    async def _handshake(self, request):
        from aiohttp import web

        body = await request.json()
        if not self._check_token(body.get("token")):
            return web.json_response({"ok": False, "error": "bad_token"}, status=401)

        self._plugin_session_id = uuid.uuid4().hex
        self._plugin_version = body.get("plugin_version")
        self._lr_version = body.get("lr_version")
        self._plugin_last_seen = time.monotonic()
        logger.info(
            "Plugin handshake: version=%s lr=%s session=%s",
            self._plugin_version,
            self._lr_version,
            self._plugin_session_id,
        )
        return web.json_response({"ok": True, "session_id": self._plugin_session_id})

    async def _poll(self, request):
        from aiohttp import web

        if not self._check_token(request.query.get("token")):
            return web.json_response({"error": "bad_token"}, status=401)
        if not self._check_session(request.query.get("session_id")):
            return web.json_response({"error": "bad_session"}, status=401)

        self._plugin_last_seen = time.monotonic()

        try:
            wait = float(request.query.get("wait", DEFAULT_POLL_WAIT_SECONDS))
        except ValueError:
            wait = DEFAULT_POLL_WAIT_SECONDS

        deadline = time.monotonic() + wait
        while not self._queue:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return web.Response(status=204)
            self._queue_event.clear()
            try:
                await asyncio.wait_for(self._queue_event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return web.Response(status=204)

        cmd = self._queue.popleft()
        return web.json_response(cmd.to_wire())

    async def _respond(self, request):
        from aiohttp import web

        if not self._check_token(request.query.get("token")):
            return web.json_response({"error": "bad_token"}, status=401)
        if not self._check_session(request.query.get("session_id")):
            return web.json_response({"error": "bad_session"}, status=401)

        self._plugin_last_seen = time.monotonic()
        body = await request.json()
        response = CommandResponse.from_wire(body)
        fut = self._pending.get(response.id)
        if fut is None or fut.done():
            logger.warning("response for unknown / done command id=%s", response.id)
            return web.json_response({"ok": False, "error": "unknown_id"}, status=404)
        fut.set_result(response)
        return web.json_response({"ok": True})

    async def _enqueue_http(self, request):
        from aiohttp import web

        body = await request.json()
        cmd_id = await self.enqueue(body["method"], body.get("params") or {})
        return web.json_response({"id": cmd_id})

    async def _result_http(self, request):
        from aiohttp import web

        cmd_id = request.match_info["cmd_id"]
        try:
            wait = float(request.query.get("wait", "30"))
        except ValueError:
            wait = 30.0
        try:
            response = await self.await_result(cmd_id, timeout=wait)
        except KeyError:
            return web.json_response({"error": "unknown_id"}, status=404)
        except asyncio.TimeoutError:
            return web.json_response({"error": "wait_timeout"}, status=408)
        return web.json_response(response.to_wire())

    # ---------- guards ----------

    def _check_token(self, supplied: str | None) -> bool:
        return bool(supplied) and secrets.compare_digest(supplied or "", self.token)

    def _check_session(self, supplied: str | None) -> bool:
        return bool(self._plugin_session_id) and supplied == self._plugin_session_id
