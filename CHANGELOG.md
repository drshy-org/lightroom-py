# Changelog

All notable changes to `lightroom-py` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] — 2026-04-29

Real-LR validation pass against Lightroom Classic 15.3 with the v0.3.0 surface. Caught and fixed five real-LR bugs that the unit tests couldn't see, plus shipped hot-reload dev tooling so future iterations don't require LR restarts.

### Added — hot-reload dev tooling
- **`system.reload_handlers`** Lua handler: clears the cached Handlers module so the next dispatch re-reads from disk. Works around LR's sandboxed `package` table by using `dofile` + a global force-reload flag.
- **`system.eval`**: run arbitrary Lua snippets via the bridge. Pref-gated (off by default; temporarily ungated in v0.3.1 for debugging — will restore the gate in v0.4).
- **`system.tail_log`**: read the last N lines of `~/Documents/LrClassicLogs/lightroom-py.log`.
- **`system.handler_list`**: enumerate every registered handler.
- **CLI**: `lightroom bridge reload | eval | tail-log | handlers`.
- **`BridgeRunner.lua`** now loads Handlers via `dofile(_PLUGIN.path .. "/Handlers.lua")` with a manual cache so the reload mechanism actually works (LR sandboxes `package.loaded`).

After this release: handler-only edits go from a 3-minute reload cycle to ~5 seconds (`bridge install --force && bridge reload`).

### Fixed (caught against real LR 15.3)
- **`json.lua` decoded JSON `null` as a sentinel table** — broke any handler that did string ops on optional params. Now drops null keys from decoded objects entirely so `params.parent` is plain `nil`.
- **`collections.list` failed on regular collections** with "This function can only be called by a smart collection" — `getSearchDescription()` errors when called on regulars. Wrap in `pcall` to detect smart-vs-regular safely.
- **`find_collection_by_name` had a leftover `walk_collection_tree` call** that polluted the search and caused the same getSearchDescription error.
- **Hierarchical keyword paths** (`add-keywords "A|B|C"`) failed with "bad argument #2 to 'format'" — root cause was `parent:getChildren()` yielding internally inside our non-yieldable `withWriteAccessDo` scope. Fix: skip the existence-check walk entirely; rely on `createKeyword`'s `returnExisting=true` flag for idempotency.
- **`remove-keywords` didn't support hierarchical paths** — only matched top-level. Added `find_existing_keyword` that walks the tree (called outside `withWriteAccessDo` so `getChildren()` can yield freely).
- **`edit_in.import_as_stack` previously experimental** — now verified working. Imported a real edited JPEG into the catalog stacked above the source. The canonical pattern from the SDK research turned out to be exactly right: `catalog:withWriteAccessDo("name", function() catalog:addPhoto(path, src, "above") end, { timeout = 60 })`.

### Documented as not-implementable in LR Classic 15.3
- **`library.make_virtual_copy`**: LR SDK does not expose `catalog:createVirtualCopies`, `catalog:createVirtualCopy`, or `photo:createVirtualCopy`. Virtual copies are a UI-only feature. Handler now raises a clear error pointing the user at LR's UI (Photo → Create Virtual Copy).
- **`catalog:trashPhotos` / programmatic photo deletion**: not exposed in LR 15.3. Documented in the changelog so we don't waste time looking again.

### Real-LR validation log (this session)
- ✅ `bridge ping` — 0.3.1 plugin handshake
- ✅ `bridge handlers` — 36 handlers registered including 4 system.* dev tools
- ✅ `bridge reload` — hot-reload mechanism works
- ✅ `bridge eval` — arbitrary Lua introspection works
- ✅ `collections list / create / add / get-photos / remove / delete` — full round-trip
- ✅ `library list-folders` — 1 folder shown correctly
- ✅ `metadata add-keywords "A|B|C"` — hierarchical path created 3 keywords with proper parent chain
- ✅ `metadata remove-keywords "A|B|C"` — leaf removed from photo
- ✅ `edit-in run "cp {input} {output}"` — exported, processed, **imported as stack** (1 new photo in catalog)
- ⚠️ `library make-virtual-copy` — not implementable in LR 15.3, documented

### Tests + tooling
- 66 tests still passing, ruff + mypy clean.
- `lightroom-mcp` console script unchanged (still 15 tools exposed).
- CI workflow unchanged.

### Versions
- `pyproject` 0.3.0 → 0.3.1
- `__version__` 0.3.0 → 0.3.1
- bridge server version 0.3.0 → 0.3.1
- `PLUGIN_VERSION` 0.3.0 → 0.3.1
- `Info.lua` VERSION unchanged at 0.3.0 (no manifest changes)

## [0.3.0] — 2026-04-29

Closes the Phase 5 / Phase 6 / Phase 7 scope from PLAN.md. Sub-clients that were stubs since v0.1.0 (Collections, Library) are now real. Edit-In reimport is fixed using the canonical `addPhoto` pattern researched from Adobe's SDK reference + community plugins. New optional MCP server adapter for Claude Desktop. CI workflow and full docs.

### Added
- **`CollectionsAPI`** (was Phase 3 debt): Lua + Python + CLI + 6 tests. `lr.collections.list / create / add / remove / delete / get_photos`. Walks regular, smart, and group collections.
- **`LibraryAPI`** (was stubbed): Lua + Python + CLI + 5 tests. `lr.library.list_folders / export / make_virtual_copy / stack`. `import_photos` raises `NotImplementedError` with a clear message — same yieldability concern as edit-in import deferred until reimport-as-stack proves stable in production.
- **Keyword hierarchy paths**: `metadata.add_keywords` now accepts pipe-separated paths like `"People|Family|Mom"`. Walks segments, creates each missing parent. Backward compatible with flat names.
- **MCP server adapter** (`lightroom-mcp` console script, `pip install "lightroom-py[mcp]"`): exposes 15 tools to Claude Desktop. Thin wrapper over `LightroomClient`. Adds `mcp` optional dependency. See [docs/mcp.md](docs/mcp.md).
- **CI workflow** (`.github/workflows/test.yml`): ruff check + ruff format + mypy + pytest on macOS + Linux × Python 3.10/3.11/3.12/3.13.
- **Docs**: full [cli-reference.md](docs/cli-reference.md) (every subcommand), [python-api.md](docs/python-api.md) (every method), examples gallery (`docs/examples/cull_workflow.py`, `docs/examples/edit_in_imagemagick.py`).

### Fixed
- **`edit_in.import_as_stack`** — uses the canonical `catalog:withWriteAccessDo("name", function() catalog:addPhoto(path, src, "above") end, { timeout = 60 })` pattern per Adobe SDK reference + Automaat/lightroom-mcp + lightroom-alt-text-plugin precedent. No `asynchronous=false`, no inner `pcall`, no nested `LrTasks.startAsyncTask` wrapper. Verified in test suite; pending real-LR validation in next session.
- **`_collections.list[str]` shadowing**: same class-scope shadowing fix as v0.1.0 collections sub-client; uses `_UUIDs = list[str]` alias.

### Tests
- 66 tests, was 56. +10 new (6 collections, 5 library minus 1 deleted overlap).
- ruff + mypy clean across 37 source files.

### Versions
- `pyproject` 0.2.0 → 0.3.0
- `__version__` 0.2.0 → 0.3.0
- bridge server version 0.2.0 → 0.3.0
- `PLUGIN_VERSION` 0.2.0 → 0.3.0
- `Info.lua` VERSION 0.2.0 → 0.3.0

### Documenting Phase 7 scope
- ✅ MCP server adapter — done.
- ⏭ Dual-`LrSocket` fast lane (MIDI2LR-style) — deferred. v0.3.0 polling latency hasn't been a real-world issue in any of our validation sessions.
- ⏭ Cloud LR sub-client — deferred indefinitely. Partner-API gated, doesn't fit "Claude controls LR Classic" goal.

## [0.2.0] — 2026-04-29

Phase 4 (Develop module) and Phase 5 (AI staging + Edit-In escape hatch). Verified end-to-end against Lightroom Classic 15.3 with a real photo catalog. Caught and fixed three real-LR bugs that the MockPlugin tests couldn't see.

### Added

#### Phase 4 — Develop module (verified end-to-end against real LR)
- **Lua handlers**: `develop.list_presets`, `develop.apply_preset` (with optional folder disambiguation), `develop.apply_settings` (raw settings table), `develop.get_settings`, `develop.copy` (one src + many dsts in a single catalog walk), `develop.reset` (via `LrDevelopController.resetAllDevelopAdjustments` after switching to Develop module + selecting target), `develop.set` (live `LrDevelopController` slider control).
- **Python `DevelopAPI`** with one method per Lua handler, fully typed.
- **CLI**: `lightroom develop list-presets|apply-preset|apply-settings|get-settings|copy|reset|set`. The `set` command takes `SLIDER=VALUE` pairs (`set Exposure=0.3 Contrast=15`).
- Verified live: `apply-settings` of `{"Exposure2012": 0.5, "Contrast2012": 25, "Saturation": 20}` produced exactly those values in the catalog; `reset` returned them to 0.

#### Phase 5 — AI staging + Edit-In escape hatch
- **`ai.stage_denoise` + `ai.prompt_update`** dispatchers and CLI commands (`lightroom ai stage-denoise|prompt-update`).
- **`edit_in.export`** Lua handler using `LrExportSession` — fully working. Exports selected photos as TIFF/JPEG/PSD/DNG/ORIGINAL into a target dir, with quality + color-space options.
- **`edit_in.import_as_stack`** Lua handler — experimental (see "Honest limitations" below).
- **`EditInAPI.run()`** Python orchestrator: export → run external command (with `{input}` / `{output}` placeholders) → reimport. The export + external-command legs are solid; the reimport leg is the experimental piece.
- **CLI**: `lightroom edit-in run|export`.
- Verified live: `edit-in export` rendered a 13.7 MB JPEG to disk in seconds.

### Fixed (caught against real LR 15.3 during validation)

- **`develop.get_settings` failed with "attempt to call a string value"**. The `withReadAccessDo` wrapper turns out to break this code path in LR 15.3. Reads of per-photo metadata don't need an explicit access wrapper — call `photo:getDevelopSettings()` directly.
- **`develop.reset` failed with "attempt to call method 'resetDevelopSettings' (a nil value)"**. `LrPhoto:resetDevelopSettings` doesn't exist in the LR SDK at all — that was a hallucination on my part. The canonical reset is `LrDevelopController.resetAllDevelopAdjustments()`, which acts on the active photo in the Develop module. Now: switch to Develop module, set each target as selection, reset.
- **`metadata.set_color_label` casing** (already verified in v0.1.2): LR accepts lowercase input but stores capitalized. Documented.

### Honest limitations (verified, documented in code)

- **AI Denoise / Masks staging is currently a no-op.** The Lua handler writes `EnableAIDenoise` + `AIDenoiseAmount` keys via `applyDevelopSettings`, but LR silently drops them — Adobe hasn't documented public AI-feature keys for plugin authors. The dispatcher works; the LR side ignores the writes. Documented in `_ai.py` and SKILL.md. Practical workflow: agent stages whatever it can, then `lightroom ai prompt-update` to nudge the user to run **Enhance → Denoise…** in LR's UI.
- **`edit_in.import_as_stack` is experimental.** `catalog:addPhoto` yields internally during thumbnail generation, and the LR-SDK access primitive that allows yields cleanly inside the bridge dispatcher hasn't been pinned down for LR Classic 15.3 (we tried `withWriteAccessDo({asynchronous=false})`, `withProlongedWriteAccessDo` with both signatures, and a fresh `LrTasks.startAsyncTask` wrapper — all hit different yield/index errors). The export side is fully working; users should drag the result file into LR manually as a workaround for the reimport step. Will revisit in v0.3.0 after studying Adobe's official `lightroom-sdk-8-examples` for the canonical `addPhoto` pattern.

### Tests
- 12 new tests via `CapturingPlugin` for develop / ai / edit_in handlers (56 total, was 44).
- All tests use mock plugin responses, so they verify wire-level behaviour but can't catch wrong Lua API names — that's why we run a real-LR validation pass per release.

### Real-LR validation log (this release)
Field session against Lightroom Classic 15.3 with a 95-photo catalog, exercising every CLI subcommand. Results:
- ✅ `bridge ping`, `catalog stats|info`, `photos list|count` (all filters)
- ✅ `metadata add-keywords|remove-keywords|rate|color|set-iptc|write-xmp|read-xmp` (full round-trip + cleanup; 0 clears rating, "" clears color/caption)
- ✅ `develop list-presets` (393 real LR presets), `apply-preset`, `apply-settings`, `get-settings`, `reset`, `set`
- ✅ `edit-in export`
- ⚠️ `edit-in run` (export + external-cmd OK, reimport-as-stack experimental)
- ⚠️ `ai stage-denoise` (dispatch OK, LR ignores the keys — no-op)

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
