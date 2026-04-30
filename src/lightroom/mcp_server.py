"""MCP server adapter — exposes lightroom-py as MCP tools for Claude Desktop.

Run with::

    pip install "lightroom-py[mcp]"
    lightroom-mcp        # serves over stdio

Then add to Claude Desktop's config (`~/Library/Application Support/Claude/
claude_desktop_config.json`):

.. code-block:: json

    {
      "mcpServers": {
        "lightroom": {
          "command": "lightroom-mcp"
        }
      }
    }

Each tool is a thin wrapper around the corresponding ``LightroomClient``
sub-client method. The server reads bridge state from ``bridge.json`` the
same way the CLI does, so a single ``lightroom bridge start`` configures
both.

Why a separate adapter and not just the Python lib? MCP exposes a tool
discovery surface that Claude Desktop introspects; the adapter declares
each tool's schema explicitly. The Python lib is the source of truth.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from . import LightroomClient

logger = logging.getLogger(__name__)


def _require_mcp() -> Any:
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "MCP support requires the optional dependency. "
            "Install with: pip install 'lightroom-py[mcp]'"
        ) from exc
    return Server, stdio_server, TextContent, Tool


def _build_tools(Tool: Any) -> list[Any]:
    """Schema declarations for every tool we expose.

    Kept as flat data so it's easy to verify against ``LightroomClient``
    and easy to extend.
    """
    uuid_arg = {"type": "array", "items": {"type": "string"}, "description": "Photo UUIDs."}

    return [
        Tool(
            name="catalog_info",
            description="Info about the active Lightroom catalog: photo count, capture-time range.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="catalog_stats",
            description="Counts of photos / folders / keywords / collections in the active catalog.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="photos_list",
            description="List photos with filters. Pure SQLite read; no LR required.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rating_gte": {"type": "integer", "minimum": 0, "maximum": 5},
                    "rating_lte": {"type": "integer", "minimum": 0, "maximum": 5},
                    "camera": {"type": "string", "description": "Camera model substring."},
                    "lens": {"type": "string", "description": "Lens model substring."},
                    "keyword": {"type": "string"},
                    "since": {"type": "string", "description": "ISO-ish capture time."},
                    "until": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        Tool(
            name="metadata_add_keywords",
            description="Add keywords to photos. Pipe-separated paths supported (e.g. 'People|Family|Mom').",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "photo_uuids": uuid_arg,
                },
                "required": ["keywords"],
            },
        ),
        Tool(
            name="metadata_set_rating",
            description="Set rating 0..5 (0 clears).",
            inputSchema={
                "type": "object",
                "properties": {
                    "rating": {"type": "integer", "minimum": 0, "maximum": 5},
                    "photo_uuids": uuid_arg,
                },
                "required": ["rating"],
            },
        ),
        Tool(
            name="metadata_set_color_label",
            description="Set color label (red/yellow/green/blue/purple, or '' to clear).",
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "enum": ["", "red", "yellow", "green", "blue", "purple"],
                    },
                    "photo_uuids": uuid_arg,
                },
                "required": ["label"],
            },
        ),
        Tool(
            name="metadata_set_iptc",
            description="Set IPTC fields (caption, title, headline, copyright, creator, city, state, country, …).",
            inputSchema={
                "type": "object",
                "properties": {
                    "fields": {"type": "object", "additionalProperties": {"type": "string"}},
                    "photo_uuids": uuid_arg,
                },
                "required": ["fields"],
            },
        ),
        Tool(
            name="develop_list_presets",
            description="List every develop preset across all folders.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="develop_apply_preset",
            description="Apply a develop preset by name to photos.",
            inputSchema={
                "type": "object",
                "properties": {
                    "preset": {"type": "string"},
                    "folder": {"type": "string", "description": "Optional disambiguation."},
                    "photo_uuids": uuid_arg,
                },
                "required": ["preset"],
            },
        ),
        Tool(
            name="develop_apply_settings",
            description="Apply raw develop settings (e.g. {'Exposure2012': 0.5, 'Contrast2012': 25}).",
            inputSchema={
                "type": "object",
                "properties": {
                    "settings": {"type": "object"},
                    "photo_uuids": uuid_arg,
                },
                "required": ["settings"],
            },
        ),
        Tool(
            name="develop_reset",
            description="Reset develop settings to camera defaults.",
            inputSchema={
                "type": "object",
                "properties": {"photo_uuids": uuid_arg},
            },
        ),
        Tool(
            name="collections_list",
            description="List all collections (regular + smart + groups).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="collections_create",
            description="Create a new (regular) collection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "parent": {"type": "string", "description": "Optional parent group name."},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="collections_add",
            description="Add photos to a collection by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "photo_uuids": uuid_arg,
                },
                "required": ["collection", "photo_uuids"],
            },
        ),
        Tool(
            name="library_export",
            description="Export selected photos to a directory (TIFF/JPEG/PSD/DNG/ORIGINAL).",
            inputSchema={
                "type": "object",
                "properties": {
                    "out_dir": {"type": "string"},
                    "photo_uuids": uuid_arg,
                    "format": {
                        "type": "string",
                        "enum": ["TIFF", "JPEG", "PSD", "DNG", "ORIGINAL"],
                        "default": "TIFF",
                    },
                    "quality": {"type": "integer", "default": 95},
                    "color_space": {"type": "string", "default": "AdobeRGB"},
                },
                "required": ["out_dir"],
            },
        ),
    ]


# Map MCP tool name → callable that invokes the right LightroomClient method.
async def _dispatch(name: str, args: dict[str, Any]) -> Any:
    async with LightroomClient.connect() as lr:
        if name == "catalog_info":
            info = await lr.catalog.info()
            return {
                "path": str(info.path),
                "photo_count": info.photo_count,
                **info.extra,
            }
        if name == "catalog_stats":
            return await lr.catalog.stats()
        if name == "photos_list":
            rows = await lr.photos.list(**args)
            return [
                {
                    "uuid": r.uuid,
                    "filename": r.filename,
                    "rating": r.rating,
                    "color_label": r.color_label,
                }
                for r in rows
            ]
        if name == "metadata_add_keywords":
            return await lr.metadata.add_keywords(
                args["keywords"], photo_uuids=args.get("photo_uuids")
            )
        if name == "metadata_set_rating":
            return await lr.metadata.set_rating(args["rating"], photo_uuids=args.get("photo_uuids"))
        if name == "metadata_set_color_label":
            return await lr.metadata.set_color_label(
                args["label"], photo_uuids=args.get("photo_uuids")
            )
        if name == "metadata_set_iptc":
            return await lr.metadata.set_iptc(args["fields"], photo_uuids=args.get("photo_uuids"))
        if name == "develop_list_presets":
            return await lr.develop.list_presets()
        if name == "develop_apply_preset":
            return await lr.develop.apply_preset(
                args["preset"],
                folder=args.get("folder"),
                photo_uuids=args.get("photo_uuids"),
            )
        if name == "develop_apply_settings":
            return await lr.develop.apply_settings(
                args["settings"], photo_uuids=args.get("photo_uuids")
            )
        if name == "develop_reset":
            return await lr.develop.reset(photo_uuids=args.get("photo_uuids"))
        if name == "collections_list":
            return await lr.collections.list()
        if name == "collections_create":
            return await lr.collections.create(args["name"], parent=args.get("parent"))
        if name == "collections_add":
            return await lr.collections.add(args["collection"], args["photo_uuids"])
        if name == "library_export":
            return await lr.library.export(
                args["out_dir"],
                photo_uuids=args.get("photo_uuids"),
                format=args.get("format", "TIFF"),
                quality=args.get("quality", 95),
                color_space=args.get("color_space", "AdobeRGB"),
            )
        raise ValueError(f"unknown tool: {name}")


async def serve() -> None:
    """Run the MCP server over stdio."""
    Server, stdio_server, TextContent, Tool = _require_mcp()

    server = Server("lightroom-py")
    tools = _build_tools(Tool)

    @server.list_tools()
    async def _list_tools() -> list[Any]:
        return tools

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[Any]:
        import json as _json

        try:
            result = await _dispatch(name, arguments or {})
            return [TextContent(type="text", text=_json.dumps(result, indent=2, default=str))]
        except Exception as exc:  # noqa: BLE001
            logger.exception("tool %s failed", name)
            return [TextContent(type="text", text=f"ERROR: {type(exc).__name__}: {exc}")]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:  # pragma: no cover
    """Entry point for the ``lightroom-mcp`` console script."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    asyncio.run(serve())


if __name__ == "__main__":  # pragma: no cover
    main()
