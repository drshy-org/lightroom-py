"""``lightroom bridge`` — install / start / stop / ping / status."""

from __future__ import annotations

import asyncio
import secrets
import shutil
from pathlib import Path

import click
import httpx
from rich.console import Console

from .._bridge_state import bridge_state_file, load_bridge_state, save_bridge_state
from ..paths import lr_modules_dir

console = Console()

PLUGIN_DIRNAME = "lightroom-py-bridge.lrplugin"


def _bundled_plugin_dir() -> Path:
    here = Path(__file__).resolve().parent.parent
    candidates = [
        here / "data" / PLUGIN_DIRNAME,
        here.parent.parent / "plugin" / PLUGIN_DIRNAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise click.ClickException(
        f"Could not locate {PLUGIN_DIRNAME}. Looked in: " + ", ".join(str(c) for c in candidates)
    )


@click.group()
def bridge() -> None:
    """Manage the Lightroom bridge plugin and local server."""


@bridge.command("install")
@click.option("--force", is_flag=True, help="Overwrite an existing install.")
def install(force: bool) -> None:
    """Copy the bridge plugin into Lightroom's Modules folder."""
    src = _bundled_plugin_dir()
    dst = lr_modules_dir() / PLUGIN_DIRNAME

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists() and not force:
        raise click.ClickException(f"{dst} already exists. Re-run with --force to overwrite.")
    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src, dst)
    console.print(f"[green]Installed[/green] {PLUGIN_DIRNAME} → {dst}")
    console.print(
        "[dim]Next: open Lightroom Classic → File → Plug-in Manager → "
        "verify 'lightroom-py bridge' is enabled, then "
        "Library menu → 'lightroom-py: Start bridge'.[/dim]"
    )


@bridge.command("status")
@click.option("--host", default=None)
@click.option("--port", type=int, default=None)
def status(host: str | None, port: int | None) -> None:
    """Probe the bridge server's /health and report state."""
    state = load_bridge_state() or {}
    host = host or str(state.get("host") or "127.0.0.1")
    port = port or int(str(state.get("port") or 8765))
    url = f"http://{host}:{port}/health"
    try:
        resp = httpx.get(url, timeout=3.0)
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPError as exc:
        console.print(f"[red]Bridge server unreachable[/red] at {url}: {exc}")
        raise SystemExit(1) from exc

    console.print(f"[green]Bridge server[/green] at [bold]{url}[/bold]")
    console.print(f"  version: {body.get('version')}")
    plugin = body.get("plugin_session_id")
    if plugin:
        console.print(
            f"  [green]plugin connected[/green] "
            f"(version={body.get('plugin_version')}, lr={body.get('lr_version')}, "
            f"last_seen={body.get('plugin_last_seen_seconds_ago')}s ago)"
        )
    else:
        console.print(
            "  [yellow]plugin not connected[/yellow] — "
            "open Lightroom and run 'lightroom-py: Start bridge' from the Library menu."
        )
    console.print(f"  queue: {body.get('queue_depth')} | pending: {body.get('pending')}")


@bridge.command("start")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=int, default=8765, show_default=True)
@click.option(
    "--token",
    default=None,
    help="Shared secret (default: generate + persist to ~/.lightroom/profiles/<profile>/bridge.json).",
)
def start(host: str, port: int, token: str | None) -> None:
    """Start the local bridge server in the foreground."""
    from ..bridge.server import LocalBridgeServer

    if token is None:
        existing = load_bridge_state()
        token = (
            str(existing.get("token"))
            if existing and existing.get("token")
            else secrets.token_hex(16)
        )

    save_bridge_state(host, port, token)

    async def _run() -> None:
        server = LocalBridgeServer(host=host, port=port, token=token)
        await server.start()
        console.print(f"[green]Bridge server running[/green] on http://{host}:{port}")
        console.print(f"[dim]Token (also saved to {bridge_state_file()}):[/dim] {token}")
        console.print("[dim]Ctrl-C to stop.[/dim]")
        try:
            await asyncio.Event().wait()
        finally:
            await server.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")


@bridge.command("ping")
@click.option("--host", default=None)
@click.option("--port", type=int, default=None)
@click.option("--timeout", type=float, default=10.0, show_default=True)
def ping(host: str | None, port: int | None, timeout: float) -> None:
    """Round-trip a ping through the bridge and the LR plugin."""
    from .. import LightroomClient

    state = load_bridge_state() or {}
    host = host or str(state.get("host") or "127.0.0.1")
    port = port or int(str(state.get("port") or 8765))
    token = str(state.get("token") or "") or None

    async def _go() -> None:
        async with LightroomClient.connect(host=host, port=port, token=token) as lr:
            console.print(f"[dim]Pinging plugin via {lr.bridge_url}...[/dim]")
            reply = await lr.ping(timeout=timeout)
            console.print(f"[green]pong[/green] {reply}")

    try:
        asyncio.run(_go())
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Ping failed:[/red] {exc}")
        raise SystemExit(1) from exc
