# Python API

```python
import asyncio
from lightroom import LightroomClient

async def main():
    async with LightroomClient.connect() as lr:
        # ... lr.catalog / lr.photos / lr.metadata / lr.develop / ...
        pass

asyncio.run(main())
```

`LightroomClient.connect()` resolves connection params in this order:
explicit kwarg → `LIGHTROOM_BRIDGE_*` env var → persisted
`bridge.json` → built-in default. Pass `require_bridge=False` for
read-only flows that hit only the SQLite fast-path.

## `lr.catalog` — `CatalogAPI`

| Method | Returns |
|---|---|
| `info()` | `CatalogInfo` (path, photo count, sqlite version, capture-time bounds) |
| `stats()` | `dict` of counts |
| `open(path)` | sets active catalog, returns `CatalogInfo` |
| `active_path()` | currently-active catalog `Path` or None |

## `lr.photos` — `PhotosAPI`

| Method | Returns |
|---|---|
| `list(rating_gte=, rating_lte=, camera=, lens=, keyword=, since=, until=, limit=)` | `list[Photo]` |
| `count(...)` | `int` (same filters) |
| `select(*uuids)` | sets LR's active selection (bridge call) |

## `lr.metadata` — `MetadataAPI`

| Method | Notes |
|---|---|
| `add_keywords(keywords, photo_uuids=)` | accepts `"A\|B\|C"` paths |
| `remove_keywords(keywords, photo_uuids=)` | |
| `set_rating(rating, photo_uuids=)` | 0..5; 0 clears |
| `set_color_label(label, photo_uuids=)` | red/yellow/green/blue/purple/"" |
| `set_iptc(fields, photo_uuids=)` | dict of IPTC key→value |
| `write_xmp(photo_uuids=)` | flush sidecars |
| `read_xmp(photo_uuids=)` | re-read from disk |
| `fast_write_xmp(tags_by_uuid, sync_back=True)` | bulk via ExifTool |

## `lr.develop` — `DevelopAPI`

| Method | Notes |
|---|---|
| `list_presets()` | `[{folder, name, uuid}, ...]` |
| `apply_preset(preset, folder=, photo_uuids=)` | |
| `apply_settings(settings, photo_uuids=)` | raw `{Exposure2012: 0.5, ...}` |
| `get_settings(photo_uuid)` | full settings dict for one photo |
| `copy(src_uuid, dst_uuids)` | |
| `reset(photo_uuids=)` | back to camera defaults |
| `set(**slider_values)` | live LrDevelopController; requires Develop module |

## `lr.collections` — `CollectionsAPI`

| Method | Notes |
|---|---|
| `list()` | regular + smart + groups |
| `create(name, parent=)` | optional parent set name |
| `add(collection, photo_uuids)` | by collection name |
| `remove(collection, photo_uuids)` | |
| `delete(collection)` | photos themselves not affected |
| `get_photos(collection)` | `list[uuid]` |

## `lr.library` — `LibraryAPI`

| Method | Notes |
|---|---|
| `list_folders()` | flat list with `depth` |
| `export(out_dir, photo_uuids=, format=, quality=, color_space=)` | |
| `make_virtual_copy(photo_uuid, copy_name=)` | |
| `stack(photo_uuids)` | first becomes top of stack |
| `import_photos(...)` | ⚠️ NotImplementedError; use LR's UI for now |

## `lr.edit_in` — `EditInAPI`

| Method | Notes |
|---|---|
| `export(out_dir, photo_uuids=, format=, quality=, color_space=)` | |
| `import_as_stack(pairs)` | `pairs = [{src_uuid, result_path}, ...]` |
| `run(external_command, photo_uuids=, format=, out_dir=, cleanup_exports=)` | full round-trip |

## `lr.ai` — `AIAPI`

| Method | Notes |
|---|---|
| `stage_denoise(strength=, photo_uuids=)` | ⚠️ LR currently ignores the keys |
| `prompt_update()` | shows a dialog in LR |

## Exceptions

All raise from `lightroom.exceptions`:
- `LightroomError` — base class
- `BridgeNotRunningError` — server isn't reachable
- `PluginHandshakeError` — token / version mismatch
- `CatalogError` — no active catalog, missing file, locked
- `CommandTimeoutError` — bridge command exceeded timeout
- `CommandFailedError` — plugin returned an error result (`.code`, `.args[0]`)
