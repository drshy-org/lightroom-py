"""``lightroom develop`` — presets, slider settings, copy/reset."""

from __future__ import annotations

import asyncio
import json as json_lib

import click
from rich.console import Console
from rich.table import Table

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
def develop() -> None:
    """Develop module: presets, settings, sliders."""


@develop.command("list-presets")
@click.option("--json", "as_json", is_flag=True)
def list_presets(as_json: bool) -> None:
    """List every develop preset across all folders."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            presets = await lr.develop.list_presets()
        if as_json:
            console.print(json_lib.dumps(presets, indent=2))
            return
        table = Table(title=f"{len(presets)} preset(s)")
        table.add_column("Folder", style="dim")
        table.add_column("Name")
        for p in presets:
            table.add_row(p.get("folder", ""), p.get("name", ""))
        console.print(table)

    asyncio.run(_go())


@develop.command("apply-preset")
@click.argument("preset")
@click.argument("uuids", nargs=-1)
@click.option("--folder", help="Disambiguate when the same preset name exists in multiple folders.")
@click.option("--selection", is_flag=True)
def apply_preset(preset: str, uuids: tuple[str, ...], folder: str | None, selection: bool) -> None:
    """Apply a develop PRESET (by name) to photos."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.apply_preset(preset, folder=folder, photo_uuids=photo_uuids)
        console.print(f"[green]applied[/green] '{preset}' to {result.get('touched')} photo(s)")

    asyncio.run(_go())


@develop.command("apply-settings")
@click.argument("payload_json")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def apply_settings(payload_json: str, uuids: tuple[str, ...], selection: bool) -> None:
    """Apply raw develop-settings JSON to photos.

    PAYLOAD_JSON is e.g. '{"Exposure2012": 0.5, "Contrast2012": 25}'.
    Pass '-' to read from stdin.
    """
    from .. import LightroomClient

    if payload_json == "-":
        import sys

        payload_json = sys.stdin.read()
    try:
        settings = json_lib.loads(payload_json)
    except json_lib.JSONDecodeError as exc:
        raise click.BadParameter(f"invalid JSON: {exc}") from exc

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.apply_settings(settings, photo_uuids=photo_uuids)
        console.print(
            f"[green]applied {len(settings)} setting(s)[/green] to {result.get('touched')} photo(s)"
        )

    asyncio.run(_go())


@develop.command("get-settings")
@click.argument("uuid")
@click.option("--json", "as_json", is_flag=True, default=True, show_default=True)
def get_settings(uuid: str, as_json: bool) -> None:
    """Print the develop-settings table for one photo."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            settings = await lr.develop.get_settings(uuid)
        console.print(json_lib.dumps(settings, indent=2, default=str))

    del as_json
    asyncio.run(_go())


@develop.command("copy")
@click.argument("src")
@click.argument("dsts", nargs=-1, required=True)
def copy_(src: str, dsts: tuple[str, ...]) -> None:
    """Copy develop settings from SRC photo to one or more DSTS."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.copy(src, list(dsts))
        console.print(f"[green]copied[/green] {src[:8]} → {result.get('copied_to')} photo(s)")

    asyncio.run(_go())


@develop.command("reset")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def reset(uuids: tuple[str, ...], selection: bool) -> None:
    """Reset develop settings to defaults."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.reset(photo_uuids=photo_uuids)
        console.print(f"[green]reset[/green] {result.get('touched')} photo(s)")

    asyncio.run(_go())


@develop.command("set")
@click.argument("kvs", nargs=-1, required=True, metavar="SLIDER=VALUE [SLIDER=VALUE …]")
def set_(kvs: tuple[str, ...]) -> None:
    """Live-drive Develop module sliders.

    Requires the user to be in the Develop module on the target photo.
    Example: `lightroom develop set Exposure=0.3 Contrast=15 Highlights=-20`
    """
    from .. import LightroomClient

    values: dict[str, float] = {}
    for kv in kvs:
        if "=" not in kv:
            raise click.BadParameter(f"expected SLIDER=VALUE, got {kv!r}")
        k, _, v = kv.partition("=")
        try:
            values[k.strip()] = float(v)
        except ValueError as exc:
            raise click.BadParameter(f"value for {k!r} must be a number, got {v!r}") from exc

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.set(**values)
        console.print(json_lib.dumps(result, indent=2, default=str))

    asyncio.run(_go())
