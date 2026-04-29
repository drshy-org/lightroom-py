"""``lightroom photos`` — list / select / count."""

from __future__ import annotations

import asyncio
import json as json_lib
import re

import click
from rich.console import Console
from rich.table import Table

from ..exceptions import CatalogError

console = Console()


_RATING_RE = re.compile(r"^\s*(>=|<=|=|>|<)?\s*(\d)\s*$")


def _parse_rating(spec: str | None) -> tuple[int | None, int | None]:
    """Parse a rating filter like '>=4' / '5' / '<=2' into (gte, lte)."""
    if not spec:
        return None, None
    m = _RATING_RE.match(spec)
    if not m:
        raise click.BadParameter(f"could not parse rating spec: {spec!r}")
    op, val = m.group(1) or "=", int(m.group(2))
    if op == ">=":
        return val, None
    if op == ">":
        return val + 1, None
    if op == "<=":
        return None, val
    if op == "<":
        return None, val - 1
    return val, val


@click.group()
def photos() -> None:
    """Photo-level operations."""


@photos.command("list")
@click.option("--rating", help="Rating filter, e.g. '>=4', '=5', '<=2'.")
@click.option("--camera", help="Camera model substring (LIKE %x%).")
@click.option("--lens", help="Lens model substring (LIKE %x%).")
@click.option("--keyword", help="Photos tagged with this keyword (case-insensitive).")
@click.option("--since", help="Capture time >= this ISO-ish timestamp.")
@click.option("--until", help="Capture time <= this ISO-ish timestamp.")
@click.option("--limit", type=int, default=50, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def list_(
    rating: str | None,
    camera: str | None,
    lens: str | None,
    keyword: str | None,
    since: str | None,
    until: str | None,
    limit: int,
    as_json: bool,
) -> None:
    """List photos matching filters (read-only via SQLite)."""
    from .. import LightroomClient

    rating_gte, rating_lte = _parse_rating(rating)

    async def _go() -> None:
        async with LightroomClient.connect(require_bridge=False) as lr:
            try:
                rows = await lr.photos.list(
                    rating_gte=rating_gte,
                    rating_lte=rating_lte,
                    camera=camera,
                    lens=lens,
                    keyword=keyword,
                    since=since,
                    until=until,
                    limit=limit,
                )
            except CatalogError as exc:
                raise click.ClickException(str(exc)) from exc

        if as_json:
            console.print(
                json_lib.dumps(
                    [
                        {
                            "uuid": r.uuid,
                            "filename": r.filename,
                            "rating": r.rating,
                            "color_label": r.color_label,
                        }
                        for r in rows
                    ],
                    indent=2,
                )
            )
            return

        table = Table(title=f"{len(rows)} photo(s)")
        table.add_column("UUID", style="dim")
        table.add_column("Filename")
        table.add_column("Rating", justify="right")
        table.add_column("Color")
        for r in rows:
            table.add_row(
                (r.uuid or "")[:8],
                r.filename or "",
                "★" * (r.rating or 0) if r.rating else "",
                r.color_label or "",
            )
        console.print(table)

    asyncio.run(_go())


@photos.command("count")
@click.option("--rating", help="Rating filter, e.g. '>=4'.")
@click.option("--camera")
@click.option("--lens")
@click.option("--keyword")
@click.option("--since")
@click.option("--until")
def count(
    rating: str | None,
    camera: str | None,
    lens: str | None,
    keyword: str | None,
    since: str | None,
    until: str | None,
) -> None:
    """Count photos matching filters."""
    from .. import LightroomClient

    rating_gte, rating_lte = _parse_rating(rating)

    async def _go() -> None:
        async with LightroomClient.connect(require_bridge=False) as lr:
            try:
                n = await lr.photos.count(
                    rating_gte=rating_gte,
                    rating_lte=rating_lte,
                    camera=camera,
                    lens=lens,
                    keyword=keyword,
                    since=since,
                    until=until,
                )
            except CatalogError as exc:
                raise click.ClickException(str(exc)) from exc
        console.print(str(n))

    asyncio.run(_go())


@photos.command("select")
@click.argument("uuids", nargs=-1, required=True)
def select(uuids: tuple[str, ...]) -> None:
    """Set Lightroom's active selection (requires running bridge)."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            await lr.photos.select(*uuids)
        console.print(f"[green]selected[/green] {len(uuids)} photo(s)")

    try:
        asyncio.run(_go())
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]select failed:[/red] {exc}")
        raise SystemExit(1) from exc
