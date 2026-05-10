"""``lightroom doctor`` — diagnose the install."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from .. import __version__
from .._bridge_state import load_bridge_state
from ..paths import lightroom_home, lr_modules_dir

console = Console()


def _service_status_line() -> str:
    """Report macOS LaunchAgent state. Returns a Rich-marked-up line."""
    if sys.platform != "darwin":
        return "[dim]not applicable on this OS[/dim]"
    plist = Path.home() / "Library" / "LaunchAgents" / "com.lightroom-py.bridge.plist"
    if not plist.exists():
        return (
            "[yellow]not installed[/yellow] "
            "(optional — run `lightroom bridge install-service` to auto-start on login)"
        )
    try:
        result = subprocess.run(
            ["launchctl", "list", "com.lightroom-py.bridge"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:  # noqa: BLE001
        return "[yellow]plist exists but launchctl unreachable[/yellow]"
    if result.returncode != 0:
        return f"[yellow]plist exists but not loaded[/yellow] (`launchctl load {plist}`)"
    pid = None
    last_exit = None
    for line in result.stdout.splitlines():
        line = line.strip().rstrip(";")
        if line.startswith('"PID" = '):
            pid = line.split("=", 1)[1].strip()
        elif line.startswith('"LastExitStatus" = '):
            last_exit = line.split("=", 1)[1].strip()
    if pid and pid != "0":
        return f"[green]running[/green] (PID {pid})"
    # Service loaded but no PID — likely TCC sandbox is killing it.
    # Specifically: exit 256 + plist points to a venv under ~/Documents et al.
    hint = ""
    if last_exit == "256":
        hint = (
            " — likely macOS TCC blocking the venv path. "
            "Reinstall lightroom-py outside ~/Documents/~/Desktop/etc., or "
            "uninstall the service: `lightroom bridge uninstall-service`"
        )
    return f"[yellow]loaded but not currently running[/yellow]{hint}"


@click.command()
def doctor() -> None:
    """Check lightroom-py install, bridge plugin, server, and macOS service."""
    table = Table(title=f"lightroom-py {__version__} — doctor")
    table.add_column("Check", style="bold")
    table.add_column("Status")

    table.add_row("Python", f"{sys.version.split()[0]} on {sys.platform}")
    table.add_row("Config dir", str(lightroom_home()))

    # Track the next-step hint so we can print it after the table.
    next_step = None

    try:
        modules = lr_modules_dir()
        plugin_path = modules / "lightroom-py-bridge.lrplugin"
        if plugin_path.exists():
            table.add_row("Bridge plugin", f"[green]installed[/green] at {plugin_path}")
        else:
            table.add_row(
                "Bridge plugin",
                "[yellow]not installed[/yellow]",
            )
            next_step = "Run `lightroom setup` to install the plugin and start the bridge service."
    except RuntimeError as exc:
        table.add_row("Bridge plugin", f"[red]{exc}[/red]")

    # macOS LaunchAgent service
    table.add_row("Bridge service", _service_status_line())

    state = load_bridge_state()
    if not state:
        table.add_row(
            "Bridge state",
            "[yellow]not configured[/yellow]",
        )
        table.add_row("Plugin handshake", "[dim]—[/dim]")
        if next_step is None:
            next_step = "Run `lightroom setup` (or `lightroom bridge start`) to generate a token."
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
                    "[yellow]not yet connected[/yellow]",
                )
                if next_step is None:
                    next_step = (
                        "Open Lightroom Classic → Library menu → 'lightroom-py: Start bridge'.\n"
                        "  (Token auto-loads from bridge.json — no paste needed.)"
                    )
        except httpx.HTTPError as exc:
            table.add_row("Bridge server", f"[red]not reachable[/red] at {url}")
            table.add_row("Plugin handshake", "[dim]—[/dim]")
            if next_step is None:
                next_step = (
                    "Bridge server is not running. Start it with:\n"
                    "  • `lightroom bridge install-service` (recommended — auto-starts on login)\n"
                    "  • or `lightroom bridge start` (foreground, in a terminal)"
                )
            del exc

    console.print(table)

    if next_step:
        console.print()
        console.print(f"[bold]Next:[/bold] {next_step}")
    else:
        console.print()
        console.print(
            "[bold green]All systems go.[/bold green] Try `lightroom photos list --limit 5`."
        )
