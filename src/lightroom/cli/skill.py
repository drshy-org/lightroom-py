"""``lightroom skill`` — install the agent skill into Claude Code / `.agents` dirs."""

from __future__ import annotations

import shutil
from pathlib import Path

import click
from rich.console import Console

console = Console()

SKILL_TARGETS = [
    Path.home() / ".claude" / "skills" / "lightroom",
    Path.home() / ".agents" / "skills" / "lightroom",
]


def _bundled_skill_md() -> Path:
    here = Path(__file__).resolve().parent.parent
    candidates = [
        here / "data" / "SKILL.md",
        here.parent.parent / "SKILL.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise click.ClickException("Could not locate SKILL.md in the install.")


@click.group()
def skill() -> None:
    """Install / inspect the lightroom-py agent skill."""


@skill.command("install")
def install() -> None:
    """Copy SKILL.md into Claude Code and `.agents` skill dirs."""
    src = _bundled_skill_md()
    for target_dir in SKILL_TARGETS:
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / "SKILL.md"
        shutil.copy2(src, dst)
        console.print(f"[green]Installed[/green] → {dst}")


@skill.command("status")
def status() -> None:
    """Show which agent skill dirs have lightroom installed."""
    for target_dir in SKILL_TARGETS:
        path = target_dir / "SKILL.md"
        marker = "[green]✓[/green]" if path.exists() else "[red]✗[/red]"
        console.print(f"{marker} {path}")
