"""``lightroom ai`` — stage AI develop settings (compute requires user click)."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console

console = Console()


def _parse_uuids(uuids: tuple[str, ...], selection: bool) -> list[str] | None:
    if selection and uuids:
        raise click.BadParameter("--selection and explicit UUIDs are mutually exclusive")
    if selection:
        return None
    if not uuids:
        raise click.UsageError(
            "Pass photo UUIDs as positional args, or `--selection` to use the active LR selection."
        )
    return list(uuids)


@click.group()
def ai() -> None:
    """AI develop settings (Denoise, Masks, etc.).

    The LR SDK lets us stage settings but cannot trigger the AI compute step.
    After staging, use `lightroom ai prompt-update` (or click 'Update AI
    Settings' in Lightroom yourself) to actually run the model.
    """


@ai.command("stage-denoise")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--strength", type=click.IntRange(0, 100), default=50, show_default=True)
def stage_denoise(uuids: tuple[str, ...], selection: bool, strength: int) -> None:
    """Stage AI Denoise (strength 0..100). Compute requires Update AI."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.ai.stage_denoise(strength=strength, photo_uuids=photo_uuids)
        console.print(
            f"[green]staged AI denoise (strength={strength})[/green] on "
            f"{result.get('touched')} photo(s)"
        )
        console.print(f"[dim]{result.get('note', '')}[/dim]")

    asyncio.run(_go())


@ai.command("prompt-update")
def prompt_update() -> None:
    """Show a dialog in LR telling the user to click Update AI Settings."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect(timeout=300) as lr:
            await lr.ai.prompt_update()
        console.print("[green]user acknowledged[/green]")

    asyncio.run(_go())
