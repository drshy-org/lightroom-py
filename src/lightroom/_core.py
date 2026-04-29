"""Core transport: talks to the local bridge server which queues commands for
the Lua plugin.

Two flavors:

- :class:`HttpBridgeClient` — the normal case: the bridge runs as a separate
  process (``lightroom bridge start``) and we talk to it over HTTP. Robust
  across Python process restarts.
- :class:`InProcessBridgeClient` — used in tests and for one-shot CLI calls:
  spin up a :class:`LocalBridgeServer` inside this process, no HTTP loopback.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

from .bridge.protocol import CommandResponse
from .bridge.server import LocalBridgeServer
from .exceptions import BridgeNotRunningError, CommandFailedError, CommandTimeoutError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class BridgeClient(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def call(
        self, method: str, params: dict[str, Any] | None = None, *, timeout: float | None = None
    ) -> Any: ...


class ClientCore:
    """Shared transport used by every sub-client.

    Holds a :class:`BridgeClient` (HTTP by default). Sub-clients call
    :meth:`call` with a method name and params; the core handles dispatch,
    timeouts, and error translation.
    """

    def __init__(
        self,
        bridge_url: str,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.bridge_url = bridge_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._client = HttpBridgeClient(self.bridge_url, token=token, timeout=timeout)
        self._opened = False

    async def open(self) -> None:
        if self._opened:
            return
        await self._client.open()
        self._opened = True

    async def close(self) -> None:
        if not self._opened:
            return
        await self._client.close()
        self._opened = False

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        if not self._opened:
            raise BridgeNotRunningError("ClientCore was not opened")
        return await self._client.call(method, params, timeout=timeout)


class HttpBridgeClient:
    """Talks to a :class:`LocalBridgeServer` running in another process."""

    def __init__(self, bridge_url: str, token: str | None, timeout: float) -> None:
        self.bridge_url = bridge_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._http: httpx.AsyncClient | None = None

    async def open(self) -> None:
        if self._http is not None:
            return
        self._http = httpx.AsyncClient(base_url=self.bridge_url, timeout=self.timeout)
        try:
            resp = await self._http.get("/health")
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.HTTPError) as exc:
            await self._http.aclose()
            self._http = None
            raise BridgeNotRunningError(
                f"Could not reach bridge at {self.bridge_url}: {exc}. "
                f"Run `lightroom bridge start` first."
            ) from exc

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        if self._http is None:
            raise BridgeNotRunningError("HttpBridgeClient is not open")

        wait = timeout if timeout is not None else self.timeout
        enqueue = await self._http.post(
            "/enqueue",
            json={"method": method, "params": params or {}},
        )
        enqueue.raise_for_status()
        cmd_id = enqueue.json()["id"]

        result_resp = await self._http.get(
            f"/result/{cmd_id}",
            params={"wait": wait},
            timeout=wait + 5,
        )
        if result_resp.status_code == 408:
            raise CommandTimeoutError(f"command {method} timed out after {wait}s")
        result_resp.raise_for_status()
        response = CommandResponse.from_wire(result_resp.json())
        if not response.ok:
            raise CommandFailedError(
                response.error_message or "command failed",
                code=response.error_code,
            )
        return response.result


class InProcessBridgeClient:
    """Bridge client that owns its server in-process — used in tests."""

    def __init__(self, server: LocalBridgeServer, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._server = server
        self.timeout = timeout

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        cmd_id = await self._server.enqueue(method, params)
        wait = timeout if timeout is not None else self.timeout
        response = await self._server.await_result(cmd_id, timeout=wait)
        if not response.ok:
            raise CommandFailedError(
                response.error_message or "command failed",
                code=response.error_code,
            )
        return response.result
