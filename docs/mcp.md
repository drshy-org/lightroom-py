# MCP server (Claude Desktop)

`lightroom-py` ships an optional MCP server that exposes the Python client as tools for Claude Desktop.

## Install

```bash
pip install "lightroom-py[mcp]"
```

This pulls in the `mcp` Python SDK alongside the rest of the library.

## Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "lightroom": {
      "command": "lightroom-mcp"
    }
  }
}
```

Then **restart Claude Desktop**. The lightroom tools will appear in the tool tray.

## Prerequisites

The MCP server is a thin adapter — it still needs the bridge running:

```bash
lightroom bridge start          # in a terminal
```

And the plugin enabled + bridge started inside Lightroom Classic. See [README.md](../README.md) for the full setup.

## Exposed tools

| Tool | Wraps |
|---|---|
| `catalog_info` | `lr.catalog.info()` |
| `catalog_stats` | `lr.catalog.stats()` |
| `photos_list` | `lr.photos.list(...)` |
| `metadata_add_keywords` | `lr.metadata.add_keywords(...)` |
| `metadata_set_rating` | `lr.metadata.set_rating(...)` |
| `metadata_set_color_label` | `lr.metadata.set_color_label(...)` |
| `metadata_set_iptc` | `lr.metadata.set_iptc(...)` |
| `develop_list_presets` | `lr.develop.list_presets()` |
| `develop_apply_preset` | `lr.develop.apply_preset(...)` |
| `develop_apply_settings` | `lr.develop.apply_settings(...)` |
| `develop_reset` | `lr.develop.reset(...)` |
| `collections_list` | `lr.collections.list()` |
| `collections_create` | `lr.collections.create(...)` |
| `collections_add` | `lr.collections.add(...)` |
| `library_export` | `lr.library.export(...)` |

The full Python API surface in [python-api.md](python-api.md) has more sub-clients (`develop.copy/get/set`, `library.list_folders/make_virtual_copy/stack`, `edit_in.run`, `metadata.write_xmp/read_xmp/fast_write_xmp`, `ai.stage_denoise/prompt_update`). Adding any of them to the MCP surface is a 5-line edit in `src/lightroom/mcp_server.py`.

## Honest limits

- The MCP server uses the same bridge as the CLI, so all the same caveats apply: AI denoise keys are no-ops, `import_photos` raises `NotImplementedError`, etc. See [SKILL.md](../SKILL.md) for the full list.
- Errors from the bridge are returned as `"ERROR: ..."` text content in the tool result so Claude can see what went wrong rather than a silent timeout.
