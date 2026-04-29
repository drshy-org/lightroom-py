# Changelog

All notable changes to `lightroom-py` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] — 2026-04-28

End-to-end metadata writes verified against Lightroom Classic 15.3. Caught two real bugs that the mock-plugin tests couldn't see.

### Fixed
- **Lua dispatcher: `pcall` → `LrTasks.pcall`**. Lua 5.1's built-in `pcall` is C-implemented and forbids yielding inside it, but every metadata handler internally yields (waiting for the catalog write lock via `withWriteAccessDo`). Result: every metadata call failed with `"Yielding is not allowed within a C or metamethod call"` while ping kept working (because ping doesn't yield). Switched to `LrTasks.pcall`, which is LR's yield-aware protected call — same return shape, but the wrapped function may yield freely. This is the canonical idiom in Adobe's own SDK examples. `PLUGIN_VERSION` bumped to `0.1.2`.
- **`metadata.set_rating` rejecting `0`**. LR's `setRawMetadata("rating", 0)` raises `"Invalid rating: 0"` — to clear a rating you have to pass `nil`. Our handler was passing `0` literally. Now: handler maps `0 → nil` so callers can use `0..5` with `0 = clear`, mirroring LR's keyboard shortcut behaviour. `PLUGIN_VERSION` bumped to `0.1.3`.

### Verified end-to-end against real Lightroom 15.3
- `lightroom catalog stats / info` against a real 95-photo catalog — counts, capture-time bounds correct.
- `lightroom photos list` with `--rating`, `--camera`, `--lens`, `--keyword`, `--since` filters all work against the real `.lrcat` schema.
- `lightroom metadata add-keywords / remove-keywords / rate / color / set-iptc` — full write round-trip on a real photo, then full cleanup back to original state, verified via SQLite read-back.

## [0.1.1] — 2026-04-28

First-real-Lightroom validation pass against Lightroom Classic 15.3.

### Verified end-to-end
- Bridge protocol: real Lua plugin (in LR 15.3) handshakes, polls `/poll`, dispatches `ping`, POSTs to `/respond`. `lr_version` returned: `15.3`.
- Plugin install via `lightroom bridge install` works cleanly on macOS into `~/Library/Application Support/Adobe/Lightroom/Modules/`.
- Token-based auth + persisted `bridge.json` round-trip works.
- `LightroomClient.connect()` auto-discovery of host/port/token from persisted state confirmed live.

### Fixed
- **WAL-aware catalog open** (`_sqlite.open_catalog`). Lightroom keeps the catalog in WAL mode while running, so recent writes live in `.lrcat-wal` and aren't yet checkpointed into the main `.lrcat`. Our previous `immutable=1` URI silently ignored the WAL — for example, on a fresh LR 15.3 install we counted `collections: 0` even though 8 default smart-collection rows were sitting in a 502 KB `.lrcat-wal`. Now: if a non-empty `.lrcat-wal` exists, copy the trio (`.lrcat` + `-wal` + `-shm`) to a tempdir and open the copy with regular `mode=ro` so SQLite applies the WAL. If no WAL or empty WAL, keep the fast `immutable=1` path. Includes a regression test (`test_wal_aware_open`) that reproduces the real-LR bug against the synthetic catalog fixture.

## [0.1.0] — 2026-04-28

First shipped release. Covers Phase 0 (scaffold) → Phase 3 (metadata writes).

What works:
- Async `LightroomClient` with namespaced sub-clients (`catalog`, `photos`, `develop`, `metadata`, `collections`, `library`, `ai`, `edit_in`).
- Click+Rich CLI: `lightroom doctor | bridge | catalog | photos | metadata | skill`.
- Local HTTP bridge server (aiohttp) with command queue, long-poll, plugin handshake, token+session auth.
- Tiny Lua `.lrplugin` (`lightroom-py-bridge.lrplugin`) with `LrTasks` poll loop, JSON encoder/decoder, dispatcher.
- SQLite read fast-path against `.lrcat` (immutable URI + tempfile fallback) for catalog stats and photo queries.
- Metadata writes via the bridge (keywords, ratings, color labels, IPTC) plus ExifTool fast-path for bulk XMP.
- Auto-discovery of bridge state via persisted `bridge.json`.
- 43 tests, full ruff + mypy clean.

What's documented but not yet implemented (planned for later phases):
- Phase 4 — Develop module (presets, sliders, settings-table application).
- Phase 5 — AI staging + Edit-In escape hatch.
- Phase 6 — SKILL.md content polish + PyPI publish.
- Phase 7 — Dual-`LrSocket` fast lane, MCP server adapter, optional Cloud LR sub-client.

### Added — Phase 3 (metadata writes + ExifTool fast-path)
- **Lua handlers**: `metadata.add_keywords`, `metadata.remove_keywords`, `metadata.set_rating`, `metadata.set_color_label`, `metadata.set_iptc`, `metadata.write_xmp`, `metadata.read_xmp`. All run inside `withWriteAccessDo` (or `withReadAccessDo` for XMP flush) and return `{touched, missing}`.
- **MetadataAPI**: bridge-driven `add_keywords` / `remove_keywords` / `set_rating` (0..5 validated client-side) / `set_color_label` (validated against `{"", red, yellow, green, blue, purple}`) / `set_iptc` / `write_xmp` / `read_xmp`. Plus `fast_write_xmp(tags_by_uuid, sync_back=True)` that resolves UUIDs → file paths via SQLite and bulk-writes via ExifTool, then triggers LR re-read.
- **ExifTool fast-path** (`lightroom/_exiftool.py`): persistent `exiftool -stay_open` process wrapper with `read_tags`, `write_tags`, `write_tags_batch` (groups files by tag-dict identity to amortize). Auto-discovers ExifTool on PATH plus common install locations.
- **SQLite UUID resolver** (`lightroom._sqlite.resolve_paths`): bulk `id_global` → absolute filesystem path lookup, joins root + folder + file rows. Used by `fast_write_xmp` and the agent skill.
- **CLI**: `lightroom metadata add-keywords | remove-keywords | rate | color | set-iptc | write-xmp | read-xmp | fast-write-xmp`. `--selection` flag for active-LR-selection or pass UUIDs as positional args. `set-iptc -f KEY=VALUE` (repeatable). `fast-write-xmp` reads JSON from arg or stdin.
- **Bridge state auto-discovery** (`lightroom/_bridge_state.py`): `LightroomClient.connect()` now reads `$LIGHTROOM_HOME/profiles/<profile>/bridge.json` as a fallback so a single `lightroom bridge start` configures the whole library for the session. Resolution order: explicit kwarg → env var → persisted state → built-in default.
- **Tests** (43 total, +6 from Phase 2): `CapturingPlugin` records every command the bridge enqueues, used to verify wire-level behaviour for keywords/rating/color/IPTC/XMP. UUID resolver tests against the synthetic catalog. Bridge state auto-discovery tests covering all four resolution layers. End-to-end CLI smoke (`/tmp/lr_phase3_smoke.py`) exercises every metadata subcommand against a real bridge subprocess.

### Added — Phase 2 (SQLite read fast-path + first real handlers)
- **SQLite reader** (`lightroom/_sqlite.py`): opens `.lrcat` read-only via `immutable=1` URI (works while LR is running); auto-fallback to a tempfile copy when immutable open fails. Strictly read-only — schema is undocumented and writes risk catalog corruption.
- **CatalogSummary / CatalogStats / PhotoRow** dataclasses + `get_catalog_summary`, `get_catalog_stats`, `list_photos`, `count_photos` queries with EXIF (camera/lens), keyword (case-insensitive), rating range, and capture-time filters.
- **Per-profile context** (`lightroom/_context.py`): active catalog path persisted to `~/.lightroom/profiles/<profile>/context.json`, shared across CLI invocations.
- **`CatalogAPI.info()` / `.stats()` / `.open()` / `.active_path()`** wired to the SQLite fast-path.
- **`PhotosAPI.list()` / `.count()`** wired to SQLite; **`PhotosAPI.select()`** wired to the bridge plugin.
- **`LightroomClient.connect(require_bridge=False)`**: skip bridge for read-only flows.
- **CLI**: `lightroom catalog open|info|stats|which|clear`, `lightroom photos list|count|select` with `--rating ">=4"` etc. parser, `--json` output, Rich tables.
- **Lua handlers**: `catalog.path`, `selection.uuids`, `photos.select` (resolves UUIDs and calls `setSelectedPhotos` inside `withWriteAccessDo`).
- **Tests**: synthetic `.lrcat` fixture + 11 SQLite/CatalogAPI tests covering filters, joins, date ranges, rating ranges, missing-catalog + no-active-catalog errors. 29 tests total, all green.

### Added — Phase 1 (bridge protocol)
- **Bridge server**: full command queue, long-poll `/poll`, `/respond`, `/handshake`, `/enqueue`, `/result/<id>`, `/health`. Per-process token + per-session `session_id`. Plugin handshake recorded in `/health`.
- **HttpBridgeClient**: opens against a running bridge, probes `/health`, dispatches via `/enqueue` + `/result/<id>` with timeout + `CommandFailedError` translation.
- **InProcessBridgeClient**: in-process variant for tests / one-shot CLI calls.
- **`LightroomClient.ping()`**: round-trip a `ping` through bridge → plugin.
- **CLI**: `lightroom bridge start` (persists token + host/port to `~/.lightroom/profiles/<profile>/bridge.json`), `lightroom bridge status`, `lightroom bridge ping`. `lightroom doctor` now probes `/health` and reports plugin handshake state.
- **Lua plugin**: real `LrTasks` long-poll loop in `BridgeRunner.lua` with handshake → poll → dispatch → respond. Tiny `json.lua` encoder/decoder. `Handlers.lua` dispatcher with `ping` + `echo`. Library menu items `Start bridge`, `Stop bridge`, `Status`, `Configure...`. State stored in plugin prefs.
- **Tests**: end-to-end protocol round-trip (`MockPlugin` Python double exercises handshake/poll/respond), handler-error propagation, bad-token rejection, `/health` reflects plugin state.

### Added — Phase 0 (scaffold)
- Project layout (`src/lightroom/`, `tests/`, `docs/`, `plugin/`), `pyproject.toml` (hatchling), ruff + mypy + pre-commit configs, MIT license, `CHANGELOG.md`.
- Empty Click CLI skeleton with `doctor`, `bridge`, `catalog`, `photos`, `skill` command groups.
- `LightroomClient` async stub with namespaced sub-clients (`catalog`, `photos`, `develop`, `metadata`, `collections`, `library`, `ai`, `edit_in`).
- `SKILL.md`, `AGENTS.md`, full `PLAN.md` design + research log.
