"""LightroomClient.connect() should resolve host/port/token in this order:
explicit kwarg → env var → persisted bridge.json → built-in default.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lightroom import LightroomClient
from lightroom._bridge_state import load_bridge_state, save_bridge_state


def test_state_file_round_trip(lightroom_home: Path) -> None:
    del lightroom_home
    save_bridge_state("127.0.0.1", 18888, "abc123")
    state = load_bridge_state()
    assert state == {"host": "127.0.0.1", "port": 18888, "token": "abc123"}


def test_load_returns_none_if_missing(lightroom_home: Path) -> None:
    del lightroom_home
    assert load_bridge_state() is None


def test_connect_uses_persisted_state(lightroom_home: Path) -> None:
    del lightroom_home
    save_bridge_state("127.0.0.1", 19999, "saved-token")
    client = LightroomClient.connect()
    assert client.bridge_url == "http://127.0.0.1:19999"
    assert client._core.token == "saved-token"


def test_connect_explicit_kwarg_overrides_state(lightroom_home: Path) -> None:
    del lightroom_home
    save_bridge_state("127.0.0.1", 19999, "saved")
    client = LightroomClient.connect(port=22222, token="explicit")
    assert client.bridge_url == "http://127.0.0.1:22222"
    assert client._core.token == "explicit"


def test_connect_env_var_overrides_state(
    lightroom_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del lightroom_home
    save_bridge_state("127.0.0.1", 19999, "saved")
    monkeypatch.setenv("LIGHTROOM_BRIDGE_PORT", "33333")
    monkeypatch.setenv("LIGHTROOM_BRIDGE_TOKEN", "envtoken")
    client = LightroomClient.connect()
    assert client.bridge_url == "http://127.0.0.1:33333"
    assert client._core.token == "envtoken"


def test_connect_falls_back_to_defaults(lightroom_home: Path) -> None:
    del lightroom_home
    client = LightroomClient.connect()
    assert client.bridge_url == "http://127.0.0.1:8765"
    assert client._core.token is None
