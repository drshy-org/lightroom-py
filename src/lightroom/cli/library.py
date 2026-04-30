"""``lightroom library`` — folders, virtual copies, stacks, export."""

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
        raise click.UsageError("Pass photo UUIDs as positional args, or `--selection`.")
    return list(uuids)


@click.group()
def library() -> None:
    """Library operations: folders, virtual copies, stacks, export."""


@library.command("list-folders")
@click.option("--json", "as_json", is_flag=True)
def list_folders(as_json: bool) -> None:
    """Print the folder tree of the active catalog."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            folders = await lr.library.list_folders()
        if as_json:
            console.print(json_lib.dumps(folders, indent=2))
            return
        table = Table(title=f"{len(folders)} folder(s)")
        table.add_column("Name")
        table.add_column("Path", style="dim")
        for f in folders:
            indent = "  " * (f.get("depth", 0) or 0)
            table.add_row(indent + (f.get("name") or ""), f.get("path") or "")
        console.print(table)

    asyncio.run(_go())


@library.command("export")
@click.argument("out_dir", type=click.Path(file_okay=False))
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["TIFF", "JPEG", "PSD", "DNG", "ORIGINAL"]),
    default="TIFF",
    show_default=True,
)
@click.option(
    "--quality",
    type=click.IntRange(0, 100),
    default=95,
    show_default=True,
    help="JPEG quality (ignored for other formats).",
)
@click.option("--color-space", default="AdobeRGB", show_default=True)
def export(
    out_dir: str,
    uuids: tuple[str, ...],
    selection: bool,
    fmt: str,
    quality: int,
    color_space: str,
) -> None:
    """Export photos to OUT_DIR (TIFF/JPEG/PSD/DNG/ORIGINAL)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            exported = await lr.library.export(
                out_dir,
                photo_uuids=photo_uuids,
                format=fmt,
                quality=quality,
                color_space=color_space,
            )
        console.print(json_lib.dumps(exported, indent=2, default=str))

    asyncio.run(_go())


@library.command("make-virtual-copy")
@click.argument("uuid")
@click.option("--copy-name", default=None)
def make_virtual_copy(uuid: str, copy_name: str | None) -> None:
    """Create a virtual copy of UUID."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.library.make_virtual_copy(uuid, copy_name=copy_name)
        console.print(json_lib.dumps(result, indent=2, default=str))

    asyncio.run(_go())


@library.command("stack")
@click.argument("uuids", nargs=-1, required=True)
def stack(uuids: tuple[str, ...]) -> None:
    """Stack the given photos together (first UUID becomes top of stack)."""
    from .. import LightroomClient

    if len(uuids) < 2:
        raise click.BadParameter("stack requires at least 2 UUIDs")

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.library.stack(list(uuids))
        console.print(f"[green]stacked[/green] {result.get('stacked')} photo(s)")

    asyncio.run(_go())
