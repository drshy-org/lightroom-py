"""``lightroom edit-in`` — Topaz-style export → external tool → reimport."""

from __future__ import annotations

import asyncio
import json as json_lib
import shlex

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


@click.group(name="edit-in")
def edit_in() -> None:
    """Run an external tool on selected photos and re-import results as stacks."""


@edit_in.command("run")
@click.argument("command", required=True)
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
    "--out-dir",
    default=None,
    help="Where to drop exports (default: a temp dir, cleaned on success).",
)
def run(
    command: str,
    uuids: tuple[str, ...],
    selection: bool,
    fmt: str,
    out_dir: str | None,
) -> None:
    """Export, run COMMAND, reimport.

    COMMAND is a shell-style string. Use `{input}` and `{output}` placeholders.

    Example:
      lightroom edit-in run "magick {input} -auto-level {output}" --selection
    """
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)
    cmd_list = shlex.split(command)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.edit_in.run(
                cmd_list,
                photo_uuids=photo_uuids,
                format=fmt,
                out_dir=out_dir,
            )
        console.print(json_lib.dumps(result, indent=2, default=str))

    asyncio.run(_go())


@edit_in.command("export")
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
def export(
    out_dir: str,
    uuids: tuple[str, ...],
    selection: bool,
    fmt: str,
) -> None:
    """Export photos to OUT_DIR (no external tool, no reimport)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            exported = await lr.edit_in.export(
                out_dir,
                photo_uuids=photo_uuids,
                format=fmt,
            )
        console.print(json_lib.dumps(exported, indent=2, default=str))

    asyncio.run(_go())
