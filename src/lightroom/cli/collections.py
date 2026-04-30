"""``lightroom collections`` — list / create / add / remove / delete."""

from __future__ import annotations

import asyncio
import json as json_lib

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def collections() -> None:
    """Manage Lightroom collections (regular + smart)."""


@collections.command("list")
@click.option("--json", "as_json", is_flag=True)
def list_(as_json: bool) -> None:
    """List collections in the active catalog."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            colls = await lr.collections.list()
        if as_json:
            console.print(json_lib.dumps(colls, indent=2))
            return
        table = Table(title=f"{len(colls)} collection(s)")
        table.add_column("Kind", style="dim")
        table.add_column("Name")
        table.add_column("Parent", style="dim")
        table.add_column("Photos", justify="right")
        for c in colls:
            table.add_row(
                c.get("kind", ""),
                c.get("name", ""),
                c.get("parent") or "—",
                str(c.get("photo_count", 0)),
            )
        console.print(table)

    asyncio.run(_go())


@collections.command("create")
@click.argument("name")
@click.option("--parent", default=None, help="Name of an existing collection set/group.")
def create(name: str, parent: str | None) -> None:
    """Create a new collection (regular)."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.collections.create(name, parent=parent)
        console.print(f"[green]created[/green] collection '{result.get('name')}'")

    asyncio.run(_go())


@collections.command("add")
@click.argument("collection")
@click.argument("uuids", nargs=-1, required=True)
def add(collection: str, uuids: tuple[str, ...]) -> None:
    """Add UUIDs to COLLECTION (by name)."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.collections.add(collection, list(uuids))
        console.print(f"[green]added[/green] {result.get('added')} photo(s) to '{collection}'")

    asyncio.run(_go())


@collections.command("remove")
@click.argument("collection")
@click.argument("uuids", nargs=-1, required=True)
def remove(collection: str, uuids: tuple[str, ...]) -> None:
    """Remove UUIDs from COLLECTION (by name)."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.collections.remove(collection, list(uuids))
        console.print(
            f"[green]removed[/green] {result.get('removed')} photo(s) from '{collection}'"
        )

    asyncio.run(_go())


@collections.command("delete")
@click.argument("collection")
@click.confirmation_option(prompt="Really delete this collection? Photos are not affected.")
def delete(collection: str) -> None:
    """Delete COLLECTION (by name). Photos themselves are not affected."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            await lr.collections.delete(collection)
        console.print(f"[green]deleted[/green] collection '{collection}'")

    asyncio.run(_go())


@collections.command("get-photos")
@click.argument("collection")
@click.option("--json", "as_json", is_flag=True)
def get_photos(collection: str, as_json: bool) -> None:
    """List photo UUIDs in COLLECTION."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            uuids = await lr.collections.get_photos(collection)
        if as_json:
            console.print(json_lib.dumps(uuids, indent=2))
        else:
            for u in uuids:
                console.print(u)

    asyncio.run(_go())
