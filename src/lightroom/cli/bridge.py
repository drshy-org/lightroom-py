"""``lightroom bridge`` — install / start / stop / ping / status."""

from __future__ import annotations

import asyncio
import json
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import click
import httpx
from rich.console import Console

from .._bridge_state import bridge_state_file, load_bridge_state, save_bridge_state
from ..paths import lr_modules_dir

console = Console()

PLUGIN_DIRNAME = "lightroom-py-bridge.lrplugin"

# macOS LaunchAgent label and path. Project-scoped (not author-scoped) so it
# stays stable if the GitHub URL changes.
SERVICE_LABEL = "com.lightroom-py.bridge"


def _service_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"


def _service_log_dir() -> Path:
    d = Path.home() / ".lightroom" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


# macOS TCC-protected directories. LaunchAgents run in a sandboxed context
# without Full Disk Access, so they cannot read files inside these paths.
# A venv (or wheel) sitting under any of these will silently fail at startup
# with PermissionError on .venv/pyvenv.cfg.
#
# Caught by E2E test 2026-05-07: install-service installed cleanly but the
# spawned bridge could not read its own pyvenv.cfg, exited 256, KeepAlive
# restarted it forever. Now refuse to install with a clear error instead.
TCC_PROTECTED_DIRS = (
    "Documents",
    "Desktop",
    "Downloads",
    "Pictures",
    "Movies",
    "Music",
)


def _is_tcc_protected(path: Path) -> str | None:
    """Return the offending top-level dir name if `path` is under a TCC-protected
    location (macOS only), else None."""
    if sys.platform != "darwin":
        return None
    try:
        rel = path.resolve().relative_to(Path.home())
    except ValueError:
        return None
    if not rel.parts:
        return None
    top = rel.parts[0]
    return top if top in TCC_PROTECTED_DIRS else None


def _resolve_lightroom_cli() -> Path:
    """Locate the absolute path of the `lightroom` CLI for use in a LaunchAgent.

    LaunchAgents don't get a login shell's PATH, so we need an absolute path.
    Prefer `shutil.which`; fall back to Python's bin dir.
    """
    found = shutil.which("lightroom")
    if found:
        return Path(found).resolve()
    # Fallback: same dir as the running interpreter
    bin_dir = Path(sys.executable).parent
    candidate = bin_dir / "lightroom"
    if candidate.exists():
        return candidate.resolve()
    raise click.ClickException(
        "Could not locate the `lightroom` CLI on PATH. "
        "Make sure you've activated the venv where lightroom-py is installed."
    )


def _build_plist(cli_path: Path, host: str, port: int) -> str:
    log_dir = _service_log_dir()
    out_log = log_dir / "bridge.out.log"
    err_log = log_dir / "bridge.err.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{SERVICE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{cli_path}</string>
        <string>bridge</string>
        <string>start</string>
        <string>--host</string>
        <string>{host}</string>
        <string>--port</string>
        <string>{port}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{out_log}</string>
    <key>StandardErrorPath</key>
    <string>{err_log}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{cli_path.parent}:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
"""


def _launchctl(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run `launchctl <args>` and return the completed process. Never raises."""
    return subprocess.run(
        ["launchctl", *args],
        capture_output=True,
        text=True,
        check=check,
    )


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


@bridge.command("reload")
def reload() -> None:
    """Hot-reload Handlers.lua without restarting Lightroom.

    Clears the Lua require cache for our handler module so the next
    dispatch picks up edits made on disk. Use after `lightroom bridge
    install --force` when you've changed handler code.

    BridgeRunner.lua and Info.lua changes still need a real LR restart.
    """
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr._core.call("system.reload_handlers", {})
        console.print(f"[green]reloaded[/green]: {result}")

    try:
        asyncio.run(_go())
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]reload failed:[/red] {exc}")
        raise SystemExit(1) from exc


@bridge.command("eval")
@click.argument("code")
def eval_(code: str) -> None:
    """Run an arbitrary Lua snippet in the plugin (dev tool, off by default).

    To enable: in LR, Library → "lightroom-py: Configure...", or set
    `prefs.enable_eval = true` via plugin prefs. Off by default for safety.

    Pass '-' to read CODE from stdin.
    """
    import sys as _sys

    from .. import LightroomClient

    if code == "-":
        code = _sys.stdin.read()

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr._core.call("system.eval", {"code": code})
        console.print(json.dumps(result, indent=2, default=str))

    try:
        asyncio.run(_go())
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]eval failed:[/red] {exc}")
        raise SystemExit(1) from exc


@bridge.command("tail-log")
@click.option("-n", "--lines", type=int, default=50, show_default=True)
def tail_log(lines: int) -> None:
    """Print the last N lines of the LR plugin's log file."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr._core.call("system.tail_log", {"lines": lines})
        if "error" in result:
            console.print(f"[red]{result['error']}[/red]  path={result.get('path')}")
            return
        console.print(
            f"[dim]{result.get('path')}  ({result.get('returned')}/{result.get('total')} lines)[/dim]"
        )
        for line in result.get("lines") or []:
            console.print(line)

    try:
        asyncio.run(_go())
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]tail-log failed:[/red] {exc}")
        raise SystemExit(1) from exc


@bridge.command("install-service")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=int, default=8765, show_default=True)
@click.option("--force", is_flag=True, help="Overwrite an existing service.")
def install_service(host: str, port: int, force: bool) -> None:
    """Install the bridge server as a macOS LaunchAgent (auto-starts on login).

    After this, you no longer need to keep `lightroom bridge start` running in
    a terminal — the bridge runs in the background and starts automatically
    when you log in.

    Windows is not yet supported; on Windows, run `lightroom bridge start`
    manually or add it to your Startup folder.
    """
    if sys.platform != "darwin":
        raise click.ClickException(
            "install-service currently supports macOS only. "
            "On Windows, use Task Scheduler or the Startup folder."
        )

    cli_path = _resolve_lightroom_cli()

    # Refuse to install if the venv lives under a TCC-protected directory.
    # The LaunchAgent would silently fail with PermissionError on pyvenv.cfg
    # and KeepAlive=true would loop forever. Better to fail loudly here.
    protected = _is_tcc_protected(cli_path)
    if protected:
        raise click.ClickException(
            f"Cannot install LaunchAgent: lightroom CLI is at {cli_path}\n"
            f"  This path is under ~/{protected}, which macOS TCC blocks LaunchAgents from reading.\n"
            f"\n"
            f"  Workarounds (any one):\n"
            f"    1. Reinstall lightroom-py into a venv outside protected dirs.\n"
            f"       Example:\n"
            f"         python3 -m venv ~/.lightroom/venv\n"
            f"         ~/.lightroom/venv/bin/pip install lightroom-py\n"
            f"         ~/.lightroom/venv/bin/lightroom bridge install-service\n"
            f"    2. Install with `pip install --user lightroom-py` (uses ~/.local/, allowed).\n"
            f"    3. Skip the LaunchAgent and run `lightroom bridge start` manually.\n"
            f"\n"
            f"  Why: macOS protects {', '.join('~/' + d for d in TCC_PROTECTED_DIRS)} "
            f"from launchd-spawned processes without Full Disk Access."
        )

    plist_path = _service_plist_path()

    if plist_path.exists() and not force:
        raise click.ClickException(
            f"{plist_path} already exists. Re-run with --force to overwrite, "
            f"or use `lightroom bridge uninstall-service` first."
        )

    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(_build_plist(cli_path, host, port))

    # Unload any prior version (best-effort), then load the new one.
    _launchctl("unload", str(plist_path))
    result = _launchctl("load", str(plist_path))
    if result.returncode != 0:
        raise click.ClickException(
            f"launchctl load failed: {result.stderr.strip() or result.stdout.strip()}"
        )

    log_dir = _service_log_dir()
    console.print(f"[green]Service installed[/green] → {plist_path}")
    console.print(f"  CLI: {cli_path}")
    console.print(f"  Listening: http://{host}:{port}")
    console.print(f"  Logs: {log_dir}/bridge.{{out,err}}.log")
    console.print(
        "[dim]The bridge now starts automatically on login. "
        "Check status: `lightroom bridge status` or `lightroom bridge service-status`.[/dim]"
    )


@bridge.command("uninstall-service")
def uninstall_service() -> None:
    """Stop and remove the macOS LaunchAgent installed by `install-service`."""
    if sys.platform != "darwin":
        raise click.ClickException("uninstall-service currently supports macOS only.")

    plist_path = _service_plist_path()
    if not plist_path.exists():
        console.print(f"[yellow]No service installed[/yellow] at {plist_path}")
        return

    _launchctl("unload", str(plist_path))
    plist_path.unlink()
    console.print(f"[green]Service removed[/green] ({plist_path})")
    console.print("[dim]To run the bridge manually, use `lightroom bridge start`.[/dim]")


@bridge.command("service-status")
def service_status() -> None:
    """Show the macOS LaunchAgent status for the bridge service."""
    if sys.platform != "darwin":
        raise click.ClickException("service-status currently supports macOS only.")

    plist_path = _service_plist_path()
    if not plist_path.exists():
        console.print("[yellow]Service not installed.[/yellow]")
        console.print(f"  Plist would be: {plist_path}")
        console.print("[dim]Install with: `lightroom bridge install-service`[/dim]")
        return

    result = _launchctl("list", SERVICE_LABEL)
    if result.returncode != 0:
        console.print("[yellow]Service plist exists but is not loaded[/yellow]")
        console.print(f"  Plist: {plist_path}")
        console.print(f"  Reload: `launchctl load {plist_path}`")
        return
    # `launchctl list <label>` prints a plist-like dict. Extract PID + last exit.
    body = result.stdout
    pid = None
    last_exit = None
    for line in body.splitlines():
        line = line.strip().rstrip(";")
        if line.startswith('"PID" = '):
            pid = line.split("=", 1)[1].strip()
        elif line.startswith('"LastExitStatus" = '):
            last_exit = line.split("=", 1)[1].strip()
    console.print(f"[green]Service loaded[/green] ({SERVICE_LABEL})")
    if pid and pid != "0":
        console.print(f"  Running: PID {pid}")
    else:
        console.print(f"  [yellow]Not currently running[/yellow] (last exit: {last_exit})")
    console.print(f"  Plist: {plist_path}")
    log_dir = _service_log_dir()
    console.print(f"  Logs:  {log_dir}/bridge.{{out,err}}.log")


@bridge.command("handlers")
def list_handlers() -> None:
    """List every handler currently registered in the plugin (post-reload).

    Use this after `bridge reload` to verify your new handlers loaded.
    """
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr._core.call("system.handler_list", {})
        for name in result.get("handlers") or []:
            console.print(name)
        console.print(f"\n[dim]{result.get('count')} handlers[/dim]")

    try:
        asyncio.run(_go())
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]handlers failed:[/red] {exc}")
        raise SystemExit(1) from exc
