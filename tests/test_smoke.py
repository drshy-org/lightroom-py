"""Phase 0 smoke tests: package imports cleanly, public surface is wired,
CLI loads, async client lifecycle works."""

from __future__ import annotations

from click.testing import CliRunner

import lightroom
from lightroom import LightroomClient
from lightroom.lightroom_cli import cli


def test_version_exposed() -> None:
    assert isinstance(lightroom.__version__, str)
    assert lightroom.__version__.count(".") >= 2


def test_public_surface() -> None:
    assert hasattr(lightroom, "LightroomClient")
    assert hasattr(lightroom, "LightroomError")
    assert hasattr(lightroom, "BridgeNotRunningError")


def test_subclients_present() -> None:
    client = LightroomClient.connect()
    for attr in (
        "catalog",
        "photos",
        "develop",
        "metadata",
        "collections",
        "library",
        "ai",
        "edit_in",
    ):
        assert hasattr(client, attr), f"LightroomClient missing sub-client: {attr}"


def test_client_construction() -> None:
    client = LightroomClient.connect(host="127.0.0.1", port=9999, token="t")
    assert client.bridge_url == "http://127.0.0.1:9999"


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "lightroom" in result.output


def test_cli_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert lightroom.__version__ in result.output


def test_cli_doctor_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor"])
    # Exit 0 even without LR installed; check it didn't crash.
    assert result.exit_code == 0


def test_cli_subcommands_registered() -> None:
    runner = CliRunner()
    for sub in ("doctor", "bridge", "catalog", "photos", "skill"):
        result = runner.invoke(cli, [sub, "--help"])
        assert result.exit_code == 0, f"{sub} --help failed: {result.output}"
