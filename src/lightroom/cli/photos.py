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


_NUMERIC_RANGE_RE = re.compile(r"^\s*(>=|<=|>|<|=)?\s*([\d.]+)\s*$")


def _parse_numeric_range(
    spec: str | None,
    name: str,
    *,
    as_float: bool = False,
) -> tuple[float | int | None, float | int | None]:
    """Parse a numeric filter like '>=400' / '=2.8' / '<=8' into (gte, lte)."""
    if not spec:
        return None, None
    m = _NUMERIC_RANGE_RE.match(spec)
    if not m:
        raise click.BadParameter(f"could not parse {name} spec: {spec!r}")
    op = m.group(1) or "="
    raw = m.group(2)
    val: float | int = float(raw) if as_float else int(float(raw))
    if op == ">=":
        return val, None
    if op == ">":
        # int-safe; for floats we leave it as is (callers compare >=)
        return val, None
    if op == "<=":
        return None, val
    if op == "<":
        return None, val
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
@click.option("--file-format", help="LR fileFormat (RAW/JPG/TIFF/PSD/DNG/VIDEO).")
@click.option("--path-substring", help="Match photos whose absolute path contains this substring.")
@click.option("--color", help="Filter by color label (red/yellow/green/blue/purple, '' for none).")
@click.option("--iso", help="ISO range, e.g. '>=400', '<=200', '=800'.")
@click.option("--aperture", help="Aperture (f-stop) range, e.g. '>=2.8', '<=8'.")
@click.option("--focal", help="Focal length (mm) range, e.g. '>=85', '<=35'.")
@click.option("--gps/--no-gps", "has_gps", default=None, help="Filter by GPS presence.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def list_(
    rating: str | None,
    camera: str | None,
    lens: str | None,
    keyword: str | None,
    since: str | None,
    until: str | None,
    limit: int,
    file_format: str | None,
    path_substring: str | None,
    color: str | None,
    iso: str | None,
    aperture: str | None,
    focal: str | None,
    has_gps: bool | None,
    as_json: bool,
) -> None:
    """List photos matching filters (read-only via SQLite)."""
    from .. import LightroomClient

    rating_gte, rating_lte = _parse_rating(rating)
    _iso_gte, _iso_lte = _parse_numeric_range(iso, "iso")
    aperture_gte, aperture_lte = _parse_numeric_range(aperture, "aperture", as_float=True)
    focal_gte, focal_lte = _parse_numeric_range(focal, "focal", as_float=True)
    iso_gte: int | None = int(_iso_gte) if _iso_gte is not None else None
    iso_lte: int | None = int(_iso_lte) if _iso_lte is not None else None

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
                    file_format=file_format,
                    path_substring=path_substring,
                    color_label=color,
                    iso_gte=iso_gte,
                    iso_lte=iso_lte,
                    aperture_gte=aperture_gte,
                    aperture_lte=aperture_lte,
                    focal_gte=focal_gte,
                    focal_lte=focal_lte,
                    has_gps=has_gps,
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
                            "camera": r.camera,
                            "lens": r.lens,
                            "iso": r.iso,
                            "aperture": r.aperture,
                            "shutter_speed": r.shutter_speed,
                            "focal_length": r.focal_length,
                            "has_gps": r.has_gps,
                            "capture_time": r.capture_time,
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
@click.option("--file-format")
@click.option("--path-substring")
@click.option("--color")
def count(
    rating: str | None,
    camera: str | None,
    lens: str | None,
    keyword: str | None,
    since: str | None,
    until: str | None,
    file_format: str | None,
    path_substring: str | None,
    color: str | None,
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
                    file_format=file_format,
                    path_substring=path_substring,
                    color_label=color,
                )
            except CatalogError as exc:
                raise click.ClickException(str(exc)) from exc
        console.print(str(n))

    asyncio.run(_go())


@photos.command("find-by-path")
@click.argument("substring")
@click.option("--limit", type=int, default=50, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def find_by_path(substring: str, limit: int, as_json: bool) -> None:
    """Find photos whose absolute path contains SUBSTRING."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect(require_bridge=False) as lr:
            try:
                rows = await lr.photos.find_by_path(substring, limit=limit)
            except CatalogError as exc:
                raise click.ClickException(str(exc)) from exc

        if as_json:
            console.print(
                json_lib.dumps(
                    [{"uuid": r.uuid, "filename": r.filename} for r in rows],
                    indent=2,
                )
            )
            return
        table = Table(title=f"{len(rows)} photo(s) with '{substring}' in path")
        table.add_column("UUID", style="dim")
        table.add_column("Filename")
        for r in rows:
            table.add_row((r.uuid or "")[:8], r.filename or "")
        console.print(table)

    asyncio.run(_go())


# ---------- selection navigation (v0.4) ----------


@photos.command("select-extend")
@click.argument("uuids", nargs=-1, required=True)
def select_extend(uuids: tuple[str, ...]) -> None:
    """Add UUIDs to the current selection (don't replace)."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.select_extend(*uuids)
        console.print(f"[green]extended selection[/green] to {r.get('selected')} photo(s)")

    asyncio.run(_go())


@photos.command("select-all")
def select_all() -> None:
    """Select all photos in the active source/filter."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.select_all()
        console.print(f"[green]selected[/green] {r.get('selected')} photo(s)")

    asyncio.run(_go())


@photos.command("select-none")
def select_none() -> None:
    """Clear the selection."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            await lr.photos.select_none()
        console.print("[green]selection cleared[/green]")

    asyncio.run(_go())


@photos.command("select-inverse")
def select_inverse() -> None:
    """Invert the current selection."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.select_inverse()
        console.print(f"[green]inverted, now {r.get('selected')} selected[/green]")

    asyncio.run(_go())


@photos.command("next")
def next_photo() -> None:
    """Move selection to the next photo in the active source."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.next_photo()
        if r.get("moved"):
            console.print(f"[green]moved to[/green] {r.get('uuid', '')[:8]}")
        else:
            console.print(f"[yellow]not moved:[/yellow] {r.get('reason')}")

    asyncio.run(_go())


@photos.command("previous")
def previous_photo() -> None:
    """Move selection to the previous photo in the active source."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.previous_photo()
        if r.get("moved"):
            console.print(f"[green]moved to[/green] {r.get('uuid', '')[:8]}")
        else:
            console.print(f"[yellow]not moved:[/yellow] {r.get('reason')}")

    asyncio.run(_go())


# ---------- flag / pickStatus ----------


def _parse_uuids_or_selection(uuids: tuple[str, ...], selection: bool) -> list[str] | None:
    if selection and uuids:
        raise click.BadParameter("--selection and explicit UUIDs are mutually exclusive")
    if selection:
        return None
    if not uuids:
        raise click.UsageError(
            "Pass UUIDs as positional args, or `--selection` to use the active LR selection."
        )
    return list(uuids)


@photos.command("flag-pick")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def flag_pick(uuids: tuple[str, ...], selection: bool) -> None:
    """Mark photos as Picked (flag = 1)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids_or_selection(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.flag_pick(photo_uuids=photo_uuids)
        console.print(f"[green]picked[/green] {r.get('touched')} photo(s)")

    asyncio.run(_go())


@photos.command("flag-reject")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def flag_reject(uuids: tuple[str, ...], selection: bool) -> None:
    """Mark photos as Rejected (flag = -1)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids_or_selection(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.flag_reject(photo_uuids=photo_uuids)
        console.print(f"[green]rejected[/green] {r.get('touched')} photo(s)")

    asyncio.run(_go())


@photos.command("flag-clear")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def flag_clear(uuids: tuple[str, ...], selection: bool) -> None:
    """Clear pick/reject flag (flag = 0)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids_or_selection(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.flag_clear(photo_uuids=photo_uuids)
        console.print(f"[green]flag cleared[/green] on {r.get('touched')} photo(s)")

    asyncio.run(_go())


@photos.command("rate-up")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def rate_up(uuids: tuple[str, ...], selection: bool) -> None:
    """Increment rating by 1 (clamped to 5)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids_or_selection(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.rating_step(1, photo_uuids=photo_uuids)
        console.print(f"[green]rating +1[/green] on {r.get('touched')} photo(s)")

    asyncio.run(_go())


@photos.command("rate-down")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def rate_down(uuids: tuple[str, ...], selection: bool) -> None:
    """Decrement rating by 1 (clamped to 0/cleared)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids_or_selection(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.rating_step(-1, photo_uuids=photo_uuids)
        console.print(f"[green]rating -1[/green] on {r.get('touched')} photo(s)")

    asyncio.run(_go())


@photos.command("color-cycle")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--reverse", is_flag=True, help="Cycle backwards.")
def color_cycle(uuids: tuple[str, ...], selection: bool, reverse: bool) -> None:
    """Cycle color label forward (or --reverse for back)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids_or_selection(uuids, selection)
    direction = -1 if reverse else 1

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            r = await lr.photos.color_step(direction, photo_uuids=photo_uuids)
        arrow = "←" if reverse else "→"
        console.print(f"[green]color {arrow}[/green] on {r.get('touched')} photo(s)")

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
