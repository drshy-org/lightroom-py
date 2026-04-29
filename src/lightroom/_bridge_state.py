"""Persisted bridge connection info: host, port, shared token.

Written by ``lightroom bridge start`` and read by every other CLI command and
by ``LightroomClient.connect()`` so a single ``bridge start`` is enough to
configure the whole library for a session.

File location: ``$LIGHTROOM_HOME/profiles/<profile>/bridge.json``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TypedDict

from .paths import profile_dir

logger = logging.getLogger(__name__)


class BridgeState(TypedDict, total=False):
    host: str
    port: int
    token: str


def bridge_state_file() -> Path:
    return profile_dir() / "bridge.json"


def load_bridge_state() -> BridgeState | None:
    f = bridge_state_file()
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("could not read %s: %s", f, exc)
        return None
    if not isinstance(data, dict):
        return None
    out: BridgeState = {}
    if "host" in data:
        out["host"] = str(data["host"])
    if "port" in data:
        try:
            out["port"] = int(data["port"])
        except (TypeError, ValueError):
            pass
    if "token" in data:
        out["token"] = str(data["token"])
    return out


def save_bridge_state(host: str, port: int, token: str) -> Path:
    f = bridge_state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"host": host, "port": port, "token": token}, indent=2))
    return f
