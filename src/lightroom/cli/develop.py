"""``lightroom develop`` — presets, slider settings, copy/reset."""

from __future__ import annotations

import asyncio
import json as json_lib
from typing import Any

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


@develop.group("mask")
def mask() -> None:
    """Mask create / list / clear. Geometry masks (radial, linear) work fully
    autonomously via apply_settings — no AI compute step needed. AI masks
    (Subject/Sky) still need the LR UI for the compute trigger."""


@mask.command("list")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
def mask_list(uuids: tuple[str, ...], selection: bool) -> None:
    """Summarize mask counts (ai/gradient/circular/paint/retouch_areas/red_eye)."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.mask_list(photo_uuids=photo_uuids)
        console.print(json_lib.dumps(result, indent=2, default=str))

    asyncio.run(_go())


@mask.command("clear")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option(
    "--kind",
    type=click.Choice(["all", "ai", "gradient", "circular", "paint"]),
    default="all",
    show_default=True,
)
def mask_clear(uuids: tuple[str, ...], selection: bool, kind: str) -> None:
    """Clear masks of the given KIND."""
    from .. import LightroomClient

    photo_uuids = _parse_uuids(uuids, selection)

    async def _go() -> None:
        async with LightroomClient.connect() as lr:
            result = await lr.develop.mask_clear(kind=kind, photo_uuids=photo_uuids)
        console.print(f"[green]cleared {kind} masks[/green] on {result.get('touched')} photo(s)")

    asyncio.run(_go())


@mask.command("create-radial")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--top", type=float, default=0.25, show_default=True)
@click.option("--bottom", type=float, default=0.75, show_default=True)
@click.option("--left", type=float, default=0.25, show_default=True)
@click.option("--right", type=float, default=0.75, show_default=True)
@click.option("--angle", type=float, default=0, show_default=True, help="Rotation in degrees.")
@click.option("--feather", type=int, default=50, show_default=True)
@click.option("--midpoint", type=int, default=50, show_default=True)
@click.option(
    "--roundness",
    type=int,
    default=0,
    show_default=True,
    help="-100 rect, 0 ellipse, +100 circle.",
)
@click.option(
    "--invert/--no-invert",
    default=False,
    help="Apply effect OUTSIDE the ellipse (e.g. for vignette-style darkening).",
)
@click.option("--name", help="Display name for the mask.")
# Local adjustments — pass any combination.
@click.option("--exposure", type=float, help="EV inside the mask (-5..5).")
@click.option("--contrast", type=float)
@click.option("--highlights", type=float)
@click.option("--shadows", type=float)
@click.option("--whites", type=float)
@click.option("--blacks", type=float)
@click.option("--clarity", type=float)
@click.option("--dehaze", type=float)
@click.option("--saturation", type=float)
@click.option("--hue", type=float)
@click.option("--temperature", type=float)
@click.option("--tint", type=float)
@click.option("--sharpness", type=float)
@click.option("--texture", type=float)
@click.option("--luminance-noise", type=float)
@click.option("--defringe", type=float)
@click.option("--moire", type=float)
@click.option("--toning-hue", type=float)
@click.option("--toning-sat", type=float)
@click.option("--grain", type=float)
def mask_create_radial(
    uuids: tuple[str, ...],
    selection: bool,
    top: float,
    bottom: float,
    left: float,
    right: float,
    angle: float,
    feather: int,
    midpoint: int,
    roundness: int,
    invert: bool,
    name: str | None,
    **adjustments: Any,
) -> None:
    """Create a radial-gradient mask with local adjustments.

    Geometry is 0..1 frame coordinates. The mask ellipse is inscribed in
    the (--left,--top)..(--right,--bottom) bounding box.

    Example: brighten subject by +1 stop:
        lightroom develop mask create-radial --left 0.2 --right 0.6
        --top 0.3 --bottom 0.8 --exposure 1.0 --selection
    """
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.mask_create_radial(
            top=top,
            bottom=bottom,
            left=left,
            right=right,
            angle=angle,
            feather=feather,
            midpoint=midpoint,
            roundness=roundness,
            invert=invert,
            name=name,
            photo_uuids=photo_uuids,
            **{k: v for k, v in adjustments.items() if v is not None},
        )
    )


@mask.command("create-linear")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--zero-x", type=float, default=0.5, show_default=True)
@click.option("--zero-y", type=float, default=0.0, show_default=True)
@click.option("--full-x", type=float, default=0.5, show_default=True)
@click.option("--full-y", type=float, default=0.5, show_default=True)
@click.option("--name")
@click.option("--exposure", type=float)
@click.option("--contrast", type=float)
@click.option("--highlights", type=float)
@click.option("--shadows", type=float)
@click.option("--whites", type=float)
@click.option("--blacks", type=float)
@click.option("--clarity", type=float)
@click.option("--dehaze", type=float)
@click.option("--saturation", type=float)
@click.option("--hue", type=float)
@click.option("--temperature", type=float)
@click.option("--tint", type=float)
@click.option("--sharpness", type=float)
@click.option("--texture", type=float)
def mask_create_linear(
    uuids: tuple[str, ...],
    selection: bool,
    zero_x: float,
    zero_y: float,
    full_x: float,
    full_y: float,
    name: str | None,
    **adjustments: Any,
) -> None:
    """Create a linear-gradient mask with local adjustments.

    Geometry: line from (--zero-x,--zero-y) to (--full-x,--full-y) in 0..1
    coords. Effect ramps from 0 to full strength along the perpendicular.

    Default (zero-y=0, full-y=0.5): top-down gradient covering upper half —
    classic graduated-ND for sky darkening.

    ⚠️ Linear schema is probed-but-unverified; radial is empirically proven.
    """
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.mask_create_linear(
            zero_x=zero_x,
            zero_y=zero_y,
            full_x=full_x,
            full_y=full_y,
            name=name,
            photo_uuids=photo_uuids,
            **{k: v for k, v in adjustments.items() if v is not None},
        )
    )


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


# ---------- Typed wrappers (v0.5) ----------
# Pure Python over apply_settings; one Click command per Develop panel.


def _parse_kv_pairs(pairs: tuple[str, ...]) -> dict[str, float]:
    """Parse `key=value` pairs (used for HSL bands, etc.)."""
    out: dict[str, float] = {}
    for p in pairs:
        if "=" not in p:
            raise click.BadParameter(f"expected key=value, got {p!r}")
        k, v = p.split("=", 1)
        try:
            out[k.strip()] = float(v.strip())
        except ValueError as exc:
            raise click.BadParameter(f"value for {k} is not a number: {v!r}") from exc
    return out


def _typed_runner(coro_factory):
    """Wrap a typed-wrapper call into Click's sync world."""
    from .. import LightroomClient

    async def _go():
        async with LightroomClient.connect() as lr:
            result = await coro_factory(lr)
        console.print(
            f"[green]applied[/green] to {result.get('touched', 0)} photo(s)"
            + (f" (skipped: {result['skipped']})" if result.get("skipped") else "")
        )

    asyncio.run(_go())


@develop.command("crop")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--top", type=float)
@click.option("--left", type=float)
@click.option("--right", type=float)
@click.option("--bottom", type=float)
@click.option("--angle", type=float, help="Rotation degrees (positive = clockwise).")
@click.option("--constrain-to-warp/--no-constrain-to-warp", default=None)
def crop_cmd(
    uuids: tuple[str, ...],
    selection: bool,
    top: float | None,
    left: float | None,
    right: float | None,
    bottom: float | None,
    angle: float | None,
    constrain_to_warp: bool | None,
) -> None:
    """Set crop rectangle (0..1) and rotation angle."""
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.crop(
            top=top,
            left=left,
            right=right,
            bottom=bottom,
            angle=angle,
            constrain_to_warp=constrain_to_warp,
            photo_uuids=photo_uuids,
        )
    )


@develop.command("hsl")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--hue", "hue_pairs", multiple=True, help="band=value pairs, e.g. --hue red=10")
@click.option(
    "--saturation", "sat_pairs", multiple=True, help="band=value, e.g. --saturation orange=-5"
)
@click.option(
    "--luminance", "lum_pairs", multiple=True, help="band=value, e.g. --luminance blue=12"
)
def hsl_cmd(
    uuids: tuple[str, ...],
    selection: bool,
    hue_pairs: tuple[str, ...],
    sat_pairs: tuple[str, ...],
    lum_pairs: tuple[str, ...],
) -> None:
    """Adjust HSL per band (red/orange/yellow/green/aqua/blue/purple/magenta)."""
    photo_uuids = _parse_uuids(uuids, selection)
    hue = _parse_kv_pairs(hue_pairs) or None
    sat = _parse_kv_pairs(sat_pairs) or None
    lum = _parse_kv_pairs(lum_pairs) or None
    _typed_runner(
        lambda lr: lr.develop.hsl(
            hue=hue,
            saturation=sat,
            luminance=lum,
            photo_uuids=photo_uuids,
        )
    )


@develop.command("color-grade")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--shadow-hue", type=float)
@click.option("--shadow-sat", type=float)
@click.option("--shadow-lum", type=float)
@click.option("--midtone-hue", type=float)
@click.option("--midtone-sat", type=float)
@click.option("--midtone-lum", type=float)
@click.option("--highlight-hue", type=float)
@click.option("--highlight-sat", type=float)
@click.option("--highlight-lum", type=float)
@click.option("--global-hue", type=float)
@click.option("--global-sat", type=float)
@click.option("--global-lum", type=float)
@click.option("--blending", type=float)
@click.option("--balance", type=float)
def color_grade_cmd(uuids: tuple[str, ...], selection: bool, **kwargs: float | None) -> None:
    """Adjust 3-way color-grade wheels + global wheel + blending/balance."""
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.color_grade(
            photo_uuids=photo_uuids,
            **kwargs,
        )
    )


@develop.command("transform")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--vertical", type=float)
@click.option("--horizontal", type=float)
@click.option("--rotate", type=float, help="Degrees.")
@click.option("--scale", type=float)
@click.option("--x-offset", type=float)
@click.option("--y-offset", type=float)
@click.option("--aspect", type=float)
@click.option(
    "--upright",
    type=click.Choice(["off", "auto", "level", "vertical", "full"]),
)
def transform_cmd(
    uuids: tuple[str, ...],
    selection: bool,
    vertical: float | None,
    horizontal: float | None,
    rotate: float | None,
    scale: float | None,
    x_offset: float | None,
    y_offset: float | None,
    aspect: float | None,
    upright: str | None,
) -> None:
    """Set Transform / Upright values."""
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.transform(
            vertical=vertical,
            horizontal=horizontal,
            rotate=rotate,
            scale=scale,
            x_offset=x_offset,
            y_offset=y_offset,
            aspect=aspect,
            upright_mode=upright,
            photo_uuids=photo_uuids,
        )
    )


@develop.command("lens-correction")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--enable-profile/--no-enable-profile", default=None)
@click.option("--distortion-amount", type=float)
@click.option("--vignetting-amount", type=float)
@click.option("--chromatic-aberration-scale", type=float)
@click.option("--remove-chromatic-aberration/--no-remove-chromatic-aberration", default=None)
@click.option("--auto-lateral-ca/--no-auto-lateral-ca", default=None)
def lens_correction_cmd(
    uuids: tuple[str, ...],
    selection: bool,
    **kwargs: Any,
) -> None:
    """Set Lens Correction panel values."""
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.lens_correction(
            photo_uuids=photo_uuids,
            **kwargs,
        )
    )


@develop.command("calibration")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--profile", "camera_profile", help="Camera profile name (e.g. 'Adobe Color').")
@click.option("--shadow-tint", type=float)
@click.option("--red-hue", type=float)
@click.option("--red-sat", type=float)
@click.option("--green-hue", type=float)
@click.option("--green-sat", type=float)
@click.option("--blue-hue", type=float)
@click.option("--blue-sat", type=float)
def calibration_cmd(uuids: tuple[str, ...], selection: bool, **kwargs: Any) -> None:
    """Set Camera Calibration panel values."""
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.calibration(
            photo_uuids=photo_uuids,
            **kwargs,
        )
    )


@develop.command("detail")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--sharpness", type=float)
@click.option("--sharpen-radius", type=float)
@click.option("--sharpen-detail", type=float)
@click.option("--sharpen-masking", type=float)
@click.option("--luminance-nr", type=float)
@click.option("--luminance-detail", type=float)
@click.option("--luminance-contrast", type=float)
@click.option("--color-nr", type=float)
@click.option("--color-detail", type=float)
@click.option("--color-smoothness", type=float)
def detail_cmd(uuids: tuple[str, ...], selection: bool, **kwargs: Any) -> None:
    """Set Detail panel: sharpening + noise reduction."""
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.detail(
            photo_uuids=photo_uuids,
            **kwargs,
        )
    )


@develop.command("effects")
@click.argument("uuids", nargs=-1)
@click.option("--selection", is_flag=True)
@click.option("--vignette-amount", type=float)
@click.option("--vignette-midpoint", type=float)
@click.option("--vignette-feather", type=float)
@click.option("--vignette-roundness", type=float)
@click.option("--vignette-highlight-contrast", type=float)
@click.option("--grain-amount", type=float)
@click.option("--grain-size", type=float)
@click.option("--grain-frequency", type=float)
def effects_cmd(uuids: tuple[str, ...], selection: bool, **kwargs: Any) -> None:
    """Set Effects panel: post-crop vignette + grain."""
    photo_uuids = _parse_uuids(uuids, selection)
    _typed_runner(
        lambda lr: lr.develop.effects(
            photo_uuids=photo_uuids,
            **kwargs,
        )
    )
