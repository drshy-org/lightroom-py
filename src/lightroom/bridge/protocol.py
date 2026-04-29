"""JSON envelope schemas for the bridge protocol.

Wire shapes (JSON over HTTP, bound to 127.0.0.1):

  POST /handshake                              first call from the Lua plugin
       {"token": "...", "plugin_version": "0.0.1", "lr_version": "..."}
  -> 200 {"ok": true, "session_id": "..."}

  GET  /poll?token=...&session_id=...&wait=30  long-poll for next command
  -> 200 {"id": "...", "method": "...", "params": {...}}        command available
  -> 204                                                        no command before wait timeout

  POST /respond?token=...&session_id=...
       {"id": "...", "ok": true,  "result": {...}}
       {"id": "...", "ok": false, "error": {"code": "...", "message": "..."}}
  -> 200 {}

  POST /enqueue                                used by Python clients in-process,
       {"method": "...", "params": {...}}      not by the Lua plugin
  -> 200 {"id": "..."}                         (then poll /result/<id>)

  GET  /result/<id>?wait=30                    block until that command resolves
  -> 200 {"ok": true, "result": ...}
  -> 200 {"ok": false, "error": {...}}
  -> 408                                       wait timeout

  GET  /health
  -> 200 {"ok": true, "version": "...", "plugin_session_id": "...|null",
          "plugin_last_seen_seconds_ago": <float|null>, "queue_depth": N}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CommandRequest:
    """A command sitting in the queue, waiting for the plugin to pick it up."""

    id: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_wire(self) -> dict[str, Any]:
        return {"id": self.id, "method": self.method, "params": self.params}


@dataclass(slots=True)
class CommandResponse:
    """The plugin's response to a command."""

    id: str
    ok: bool
    result: Any = None
    error_code: str | None = None
    error_message: str | None = None

    def to_wire(self) -> dict[str, Any]:
        if self.ok:
            return {"id": self.id, "ok": True, "result": self.result}
        return {
            "id": self.id,
            "ok": False,
            "error": {"code": self.error_code, "message": self.error_message},
        }

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> CommandResponse:
        if payload.get("ok"):
            return cls(id=payload["id"], ok=True, result=payload.get("result"))
        err = payload.get("error") or {}
        return cls(
            id=payload["id"],
            ok=False,
            error_code=err.get("code"),
            error_message=err.get("message"),
        )
