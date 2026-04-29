"""``lightroom doctor`` — diagnose the install."""

from __future__ import annotations

import sys

import click
import httpx
from rich.console import Console
from rich.table import Table

from .. import __version__
from .._bridge_state import load_bridge_state
from ..paths import lightroom_home, lr_modules_dir

console = Console()


@click.command()
def doctor() -> None:
    """Check lightroom-py install, bridge plugin, and bridge server."""
    table = Table(title=f"lightroom-py {__version__} — doctor")
    table.add_column("Check", style="bold")
    table.add_column("Status")

    table.add_row("Python", f"{sys.version.split()[0]} on {sys.platform}")
    table.add_row("Config dir", str(lightroom_home()))

    try:
        modules = lr_modules_dir()
        plugin_path = modules / "lightroom-py-bridge.lrplugin"
        if plugin_path.exists():
            table.add_row("Bridge plugin", f"[green]installed[/green] at {plugin_path}")
        else:
            table.add_row(
                "Bridge plugin",
                "[yellow]not installed[/yellow] (run `lightroom bridge install`)",
            )
    except RuntimeError as exc:
        table.add_row("Bridge plugin", f"[red]{exc}[/red]")

    state = load_bridge_state()
    if not state:
        table.add_row(
            "Bridge server",
            "[yellow]not configured[/yellow] (run `lightroom bridge start`)",
        )
        table.add_row("Plugin handshake", "[dim]—[/dim]")
    else:
        url = f"http://{state['host']}:{state['port']}/health"
        try:
            resp = httpx.get(url, timeout=3.0)
            resp.raise_for_status()
            body = resp.json()
            table.add_row("Bridge server", f"[green]running[/green] at {url}")
            if body.get("plugin_session_id"):
                table.add_row(
                    "Plugin handshake",
                    f"[green]connected[/green] "
                    f"(v{body.get('plugin_version')}, lr {body.get('lr_version')}, "
                    f"last seen {body.get('plugin_last_seen_seconds_ago')}s ago)",
                )
            else:
                table.add_row(
                    "Plugin handshake",
                    "[yellow]not yet connected[/yellow] "
                    "(start the plugin via Library → 'lightroom-py: Start bridge')",
                )
        except httpx.HTTPError as exc:
            table.add_row("Bridge server", f"[red]not reachable[/red] at {url}: {exc}")
            table.add_row("Plugin handshake", "[dim]—[/dim]")

    console.print(table)
