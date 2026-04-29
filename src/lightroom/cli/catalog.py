"""``lightroom catalog`` — open / info / stats."""

from __future__ import annotations

import asyncio
import json as json_lib

import click
from rich.console import Console
from rich.table import Table

from .._context import clear_active_catalog, load_active_catalog
from ..exceptions import CatalogError

console = Console()


@click.group()
def catalog() -> None:
    """Catalog-level operations (read fast-path via SQLite)."""


@catalog.command("open")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
def open_(path: str) -> None:
    """Set the active catalog path."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect(require_bridge=False) as lr:
            try:
                info = await lr.catalog.open(path)
            except CatalogError as exc:
                raise click.ClickException(str(exc)) from exc
        console.print(f"[green]Active catalog set to[/green] {info.path}")
        console.print(f"  photos: {info.photo_count}")

    asyncio.run(_go())


@catalog.command("info")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def info(as_json: bool) -> None:
    """Print info about the active catalog."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect(require_bridge=False) as lr:
            try:
                ci = await lr.catalog.info()
            except CatalogError as exc:
                raise click.ClickException(str(exc)) from exc

        if as_json:
            console.print(
                json_lib.dumps(
                    {
                        "path": str(ci.path),
                        "photo_count": ci.photo_count,
                        "lightroom_version": ci.lightroom_version,
                        **ci.extra,
                    },
                    indent=2,
                )
            )
            return

        table = Table(title=f"Catalog: {ci.path}")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("photos", str(ci.photo_count))
        for k, v in ci.extra.items():
            table.add_row(k, str(v))
        console.print(table)

    asyncio.run(_go())


@catalog.command("stats")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def stats(as_json: bool) -> None:
    """Counts: photos, folders, keywords, collections."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect(require_bridge=False) as lr:
            try:
                s = await lr.catalog.stats()
            except CatalogError as exc:
                raise click.ClickException(str(exc)) from exc

        if as_json:
            console.print(json_lib.dumps(s, indent=2))
            return
        table = Table(title="Catalog stats")
        table.add_column("Item", style="bold")
        table.add_column("Count", justify="right")
        for k in ("photos", "folders", "keywords", "collections", "smart_collections"):
            table.add_row(k, str(s.get(k, 0)))
        console.print(table)

    asyncio.run(_go())


@catalog.command("which")
def which() -> None:
    """Print the active catalog path (or 'none')."""
    p = load_active_catalog()
    console.print(str(p) if p else "[yellow]none[/yellow]")


@catalog.command("clear")
def clear() -> None:
    """Forget the active catalog path."""
    clear_active_catalog()
    console.print("[green]cleared[/green]")
