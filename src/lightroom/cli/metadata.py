"""``lightroom metadata`` — keywords, ratings, color labels, IPTC, XMP."""

from __future__ import annotations

import asyncio
import json as json_lib

import click
from rich.console import Console

console = Console()


def _split_csv(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


def _parse_uuids(uuids: tuple[str, ...], selection: bool) -> list[str] | None:
    """Translate CLI args into a uuid list (or None for active selection)."""
    if selection and uuids:
        raise click.BadParameter("--selection and explicit UUIDs are mutually exclusive")
    if selection:
        return None  # bridge resolves to active selection
    if not uuids:
        raise click.UsageError(
            "Pass photo UUIDs as positional args, or `--selection` to use the active LR selection."
        )
    return list(uuids)


@click.group()
def metadata() -> None:
    """Write keywords / ratings / IPTC / XMP."""


@metadata.command("add-keywords")
@click.argument("keywords")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True, help="Apply to LR's active selection.")
def add_keywords(keywords: str, uuids: tuple[str, ...], selection: bool) -> None:
    """Add comma-separated KEYWORDS to photos."""
    from .. import LightroomClient

    kws = _split_csv(keywords)
    if not kws:
        raise click.BadParameter("at least one keyword required")
    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.metadata.add_keywords(kws, photo_uuids=photo_uuids)
        console.print(f"[green]added[/green] {kws} to {result.get('touched')} photo(s)")
        if result.get("missing"):
            console.print(f"[yellow]missing UUIDs:[/yellow] {result['missing']}")

    asyncio.run(_go())


@metadata.command("remove-keywords")
@click.argument("keywords")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def remove_keywords(keywords: str, uuids: tuple[str, ...], selection: bool) -> None:
    """Remove comma-separated KEYWORDS from photos."""
    from .. import LightroomClient

    kws = _split_csv(keywords)
    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.metadata.remove_keywords(kws, photo_uuids=photo_uuids)
        console.print(f"[green]removed[/green] {kws} from {result.get('touched')} photo(s)")

    asyncio.run(_go())


@metadata.command("rate")
@click.argument("rating", type=click.IntRange(0, 5))
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def rate(rating: int, uuids: tuple[str, ...], selection: bool) -> None:
    """Set RATING (0..5) on photos."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.metadata.set_rating(rating, photo_uuids=photo_uuids)
        console.print(f"[green]rating={rating}[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@metadata.command("color")
@click.argument("label", type=click.Choice(["", "red", "yellow", "green", "blue", "purple"]))
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def color(label: str, uuids: tuple[str, ...], selection: bool) -> None:
    """Set color LABEL on photos. Use '' to clear."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.metadata.set_color_label(label, photo_uuids=photo_uuids)
        console.print(f"[green]label={label!r}[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@metadata.command("set-iptc")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option(
    "--field",
    "-f",
    multiple=True,
    metavar="KEY=VALUE",
    help="Repeat for each field. e.g. -f caption='Sunset' -f city='Paris'",
)
def set_iptc(uuids: tuple[str, ...], selection: bool, field: tuple[str, ...]) -> None:
    """Set IPTC fields on photos."""
    from .. import LightroomClient

    if not field:
        raise click.UsageError("at least one --field K=V required")
    fields: dict[str, str] = {}
    for f in field:
        if "=" not in f:
            raise click.BadParameter(f"invalid --field {f!r}; expected KEY=VALUE")
        k, _, v = f.partition("=")
        fields[k.strip()] = v.strip()

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.metadata.set_iptc(fields, photo_uuids=photo_uuids)
        console.print(f"[green]wrote IPTC[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@metadata.command("write-xmp")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def write_xmp(uuids: tuple[str, ...], selection: bool) -> None:
    """Tell LR to flush XMP sidecars to disk for the photos."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.metadata.write_xmp(photo_uuids=photo_uuids)
        console.print(f"[green]wrote XMP for[/green] {result.get('touched')} photo(s)")

    asyncio.run(_go())


@metadata.command("read-xmp")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def read_xmp(uuids: tuple[str, ...], selection: bool) -> None:
    """Tell LR to re-read XMP from disk for the photos."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.metadata.read_xmp(photo_uuids=photo_uuids)
        console.print(f"[green]read XMP for[/green] {result.get('touched')} photo(s)")

    asyncio.run(_go())


@metadata.command("fast-write-xmp")
@click.argument("payload_json")
@click.option("--no-sync-back", is_flag=True, help="Skip the LR re-read step.")
def fast_write_xmp(payload_json: str, no_sync_back: bool) -> None:
    """Bulk-write XMP via ExifTool. PAYLOAD_JSON is {uuid: {tag: value, ...}}.

    Reads the JSON from stdin if PAYLOAD_JSON is '-'.
    """
    from .. import LightroomClient

    if payload_json == "-":
        import sys

        payload_json = sys.stdin.read()
    try:
        tags_by_uuid = json_lib.loads(payload_json)
    except json_lib.JSONDecodeError as exc:
        raise click.BadParameter(f"invalid JSON: {exc}") from exc

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.metadata.fast_write_xmp(tags_by_uuid, sync_back=not no_sync_back)
        console.print(json_lib.dumps(result, indent=2, default=str))

    asyncio.run(_go())
