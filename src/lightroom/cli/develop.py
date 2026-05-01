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


# ===================================================================
# v0.4 additions: tone curve, snapshots, process version, targeted
# resets, paste-settings.
# ===================================================================


# ---------- tone curve ----------


@develop.group("curve")
def curve() -> None:
    """Tone curve get/set/preset on the RGB or per-channel curves."""


@curve.command("get")
@click.argument("uuid")
@click.option("--channel", type=click.Choice(["rgb", "red", "green", "blue"]), default="rgb")
def curve_get(uuid: str, channel: str) -> None:
    """Print the tone curve for a photo on CHANNEL (rgb/red/green/blue)."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.curve_get(uuid, channel=channel)
        console.print(json_lib.dumps(result, indent=2, default=str))

    asyncio.run(_go())


@curve.command("set")
@click.argument("points")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--channel", type=click.Choice(["rgb", "red", "green", "blue"]), default="rgb")
def curve_set(points: str, uuids: tuple[str, ...], selection: bool, channel: str) -> None:
    """Apply a custom tone curve. POINTS is a JSON array `[x1,y1,x2,y2,...]` 0..255."""
    from .. import LightroomClient

    try:
        pts = json_lib.loads(points)
    except json_lib.JSONDecodeError as exc:
        raise click.BadParameter(f"invalid JSON points list: {exc}") from exc
    if not isinstance(pts, list):
        raise click.BadParameter("points must be a JSON list of numbers")

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.curve_set(pts, channel=channel, photo_uuids=photo_uuids)
        console.print(
            f"[green]curve set[/green] on {result.get('touched')} photo(s), channel={channel}"
        )

    asyncio.run(_go())


@curve.command("preset")
@click.argument(
    "name", type=click.Choice(["Linear", "Medium Contrast", "Strong Contrast", "Custom"])
)
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def curve_preset(name: str, uuids: tuple[str, ...], selection: bool) -> None:
    """Apply a named tone-curve preset."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.curve_preset(name, photo_uuids=photo_uuids)
        console.print(f"[green]curve preset[/green] '{name}' on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@curve.command("linear")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def curve_linear(uuids: tuple[str, ...], selection: bool) -> None:
    """Shortcut for `curve preset Linear`."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.curve_preset("Linear", photo_uuids=photo_uuids)
        console.print(f"[green]linear curve[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@curve.command("s-curve")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--strength", type=click.Choice(["medium", "strong"]), default="medium")
def curve_s(uuids: tuple[str, ...], selection: bool, strength: str) -> None:
    """Shortcut for `curve preset 'Medium Contrast' / 'Strong Contrast'`."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)
    name = "Medium Contrast" if strength == "medium" else "Strong Contrast"

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.curve_preset(name, photo_uuids=photo_uuids)
        console.print(f"[green]{name}[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


# ---------- snapshots ----------


@develop.group("snapshot")
def snapshot() -> None:
    """Develop snapshots — frozen states of a photo's edits."""


@snapshot.command("create")
@click.argument("name")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def snapshot_create(name: str, uuids: tuple[str, ...], selection: bool) -> None:
    """Create a develop snapshot named NAME on each target photo."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.snapshot_create(name, photo_uuids=photo_uuids)
        console.print(json_lib.dumps(result, indent=2, default=str))

    asyncio.run(_go())


@snapshot.command("list")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def snapshot_list(uuids: tuple[str, ...], selection: bool) -> None:
    """List snapshots for the target photos."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.snapshot_list(photo_uuids=photo_uuids)
        console.print(json_lib.dumps(result, indent=2, default=str))

    asyncio.run(_go())


# ---------- process version ----------


@develop.group("process-version")
def process_version() -> None:
    """Get/set the develop process version (PV2003=5.0, PV2010=6.7, PV2012=11.0)."""


@process_version.command("get")
@click.argument("uuid")
def process_version_get(uuid: str) -> None:
    """Print the process version for a photo."""
    from .. import LightroomClient

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            v = await lr.develop.process_version_get(uuid)
        console.print(v)

    asyncio.run(_go())


@process_version.command("set")
@click.argument("version")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def process_version_set(version: str, uuids: tuple[str, ...], selection: bool) -> None:
    """Set the process version (e.g. `11.0` for PV2012)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.process_version_set(version, photo_uuids=photo_uuids)
        console.print(
            f"[green]process version={version}[/green] on {result.get('touched')} photo(s)"
        )

    asyncio.run(_go())


# ---------- targeted resets ----------


@develop.command("reset-crop")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def reset_crop(uuids: tuple[str, ...], selection: bool) -> None:
    """Reset only the crop (switches to Develop module per photo)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.reset_crop(photo_uuids=photo_uuids)
        console.print(f"[green]reset crop[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@develop.command("reset-masking")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def reset_masking(uuids: tuple[str, ...], selection: bool) -> None:
    """Clear all masks (mask groups, gradient/circular/paint corrections)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.reset_masking(photo_uuids=photo_uuids)
        console.print(f"[green]reset masking[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@develop.command("reset-spot")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def reset_spot(uuids: tuple[str, ...], selection: bool) -> None:
    """Clear spot-removal / healing edits."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.reset_spot(photo_uuids=photo_uuids)
        console.print(f"[green]reset spot[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@develop.command("reset-redeye")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def reset_redeye(uuids: tuple[str, ...], selection: bool) -> None:
    """Clear red-eye corrections."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.reset_redeye(photo_uuids=photo_uuids)
        console.print(f"[green]reset red-eye[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@develop.command("reset-transforms")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def reset_transforms(uuids: tuple[str, ...], selection: bool) -> None:
    """Reset upright/perspective/lens transforms."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.reset_transforms(photo_uuids=photo_uuids)
        console.print(f"[green]reset transforms[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


# ---------- paste-settings ----------


@develop.command("paste-settings")
@click.argument("payload_json")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--subset", help="Comma-separated keys to paste (default: all keys in PAYLOAD_JSON).")
def paste_settings(
    payload_json: str,
    uuids: tuple[str, ...],
    selection: bool,
    subset: str | None,
) -> None:
    """Paste develop settings to many photos. Mirror of LR's "Paste Settings…" dialog.

    PAYLOAD_JSON is e.g. the output of `lightroom develop get-settings <uuid>`.
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
    subset_keys = [k.strip() for k in (subset or "").split(",") if k.strip()] or None

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.paste_settings(
                settings, subset=subset_keys, photo_uuids=photo_uuids
            )
        console.print(
            f"[green]pasted {len(result.get('applied_keys', []))} key(s)[/green] "
            f"to {result.get('touched')} photo(s)"
        )

    asyncio.run(_go())
