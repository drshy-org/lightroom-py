"""``lightroom setup`` — one-command installer.

Runs the full install path in order:

1. Install the LR plugin (`bridge install`)
2. Generate a bridge token (`bridge start --once`-equivalent: just save state)
3. Install the bridge server as a macOS LaunchAgent (`bridge install-service`)
4. Install the agent skill into ~/.claude/skills/lightroom and ~/.agents/skills/lightroom
5. Open Lightroom Classic so the user can enable the plugin (the only manual step)

After this, the user only has to:
  - In LR: File → Plug-in Manager → enable "lightroom-py bridge" (one-time, ~10s)
  - In LR: Library menu → "lightroom-py: Start bridge" (token auto-loads)
"""

from __future__ import annotations

import secrets
import shutil
import subprocess
import sys

import click
from rich.console import Console

from .._bridge_state import bridge_state_file, load_bridge_state, save_bridge_state
from ..paths import lr_modules_dir
from . import bridge as bridge_mod
from . import skill as skill_mod

console = Console()


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=int, default=8765, show_default=True)
@click.option(
    "--no-service",
    is_flag=True,
    help="Skip installing the macOS LaunchAgent (use `bridge start` manually).",
)
@click.option(
    "--no-skill",
    is_flag=True,
    help="Skip installing the agent skill into Claude / .agents skill dirs.",
)
@click.option(
    "--no-open-lr",
    is_flag=True,
    help="Skip auto-launching Lightroom at the end.",
)
@click.option("--force", is_flag=True, help="Overwrite existing install.")
def setup(
    host: str,
    port: int,
    no_service: bool,
    no_skill: bool,
    no_open_lr: bool,
    force: bool,
) -> None:
    """One-command setup: plugin + service + skill + open LR.

    After running this, only one manual step remains: enable the plugin in
    Lightroom's Plug-in Manager (Adobe sandbox requires user action there).
    """
    console.print("[bold]lightroom-py setup[/bold]")
    console.print()

    # 1. Install the LR plugin
    console.print("[1/5] Installing LR plugin...")
    src = bridge_mod._bundled_plugin_dir()
    dst = lr_modules_dir() / bridge_mod.PLUGIN_DIRNAME
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if not force:
            console.print(
                f"  [yellow]already installed at {dst}[/yellow] (use --force to reinstall)"
            )
        else:
            shutil.rmtree(dst)
            shutil.copytree(src, dst)
            console.print(f"  [green]reinstalled[/green] → {dst}")
    else:
        shutil.copytree(src, dst)
        console.print(f"  [green]installed[/green] → {dst}")

    # 2. Generate / persist a bridge token
    console.print("[2/5] Generating bridge token...")
    existing = load_bridge_state()
    if existing and existing.get("token") and not force:
        token = str(existing["token"])
        console.print(f"  [green]reused existing token[/green] from {bridge_state_file()}")
    else:
        token = secrets.token_hex(16)
        save_bridge_state(host, port, token)
        console.print(f"  [green]new token[/green] saved to {bridge_state_file()}")

    # 3. Install the LaunchAgent (macOS only)
    if no_service:
        console.print("[3/5] [dim]Skipping LaunchAgent (--no-service)[/dim]")
    elif sys.platform != "darwin":
        console.print(
            "[3/5] [yellow]Skipping LaunchAgent[/yellow] — currently macOS only. "
            "Run `lightroom bridge start` manually to start the bridge server."
        )
    else:
        console.print("[3/5] Installing LaunchAgent (auto-starts on login)...")
        try:
            cli_path = bridge_mod._resolve_lightroom_cli()
        except click.ClickException as exc:
            console.print(f"  [yellow]could not install service:[/yellow] {exc.message}")
            cli_path = None

        if cli_path is not None:
            protected = bridge_mod._is_tcc_protected(cli_path)
            if protected:
                console.print(
                    f"  [yellow]skipped LaunchAgent[/yellow]: CLI is at {cli_path}\n"
                    f"  macOS TCC blocks LaunchAgents from reading files under ~/{protected}.\n"
                    f"  To enable auto-start: reinstall lightroom-py in ~/.lightroom/venv "
                    f"or with `pip install --user`, then re-run `lightroom bridge install-service`.\n"
                    f"  For now, run `lightroom bridge start` in a terminal."
                )
            else:
                plist_path = bridge_mod._service_plist_path()
                plist_path.parent.mkdir(parents=True, exist_ok=True)
                if plist_path.exists():
                    bridge_mod._launchctl("unload", str(plist_path))
                plist_path.write_text(bridge_mod._build_plist(cli_path, host, port))
                result = bridge_mod._launchctl("load", str(plist_path))
                if result.returncode == 0:
                    console.print(
                        f"  [green]service running[/green] (label={bridge_mod.SERVICE_LABEL})"
                    )
                    console.print(f"  bridge listening at http://{host}:{port}")
                else:
                    console.print(
                        f"  [yellow]launchctl load returned {result.returncode}[/yellow]: "
                        f"{result.stderr.strip()}"
                    )

    # 4. Install the agent skill
    if no_skill:
        console.print("[4/5] [dim]Skipping skill install (--no-skill)[/dim]")
    else:
        console.print("[4/5] Installing agent skill...")
        try:
            src_md = skill_mod._bundled_skill_md()
        except click.ClickException as exc:
            console.print(f"  [yellow]could not locate SKILL.md:[/yellow] {exc.message}")
        else:
            for target_dir in skill_mod.SKILL_TARGETS:
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / "SKILL.md"
                shutil.copy2(src_md, target)
                console.print(f"  [green]installed[/green] → {target}")

    # 5. Open Lightroom (the user still has to enable the plugin manually)
    console.print()
    console.print("[5/5] Final manual step in Lightroom:")
    console.print("    1. File → Plug-in Manager → verify 'lightroom-py bridge' is enabled")
    console.print("    2. Library → 'lightroom-py: Start bridge'")
    console.print("    (Token auto-loads from bridge.json — no paste needed.)")

    if no_open_lr:
        console.print("[dim]Skipping LR launch (--no-open-lr).[/dim]")
    elif sys.platform == "darwin":
        try:
            subprocess.run(
                ["open", "-a", "Adobe Lightroom Classic"],
                check=False,
                capture_output=True,
                timeout=5,
            )
            console.print("[dim](Launching Lightroom Classic now…)[/dim]")
        except Exception:  # noqa: BLE001
            pass

    console.print()
    console.print("[bold green]Setup complete.[/bold green] Run `lightroom doctor` to verify.")
