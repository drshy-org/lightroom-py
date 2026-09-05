# Changelog

All notable changes to `lightroom-py` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 0.6.1 — Fixed: `[mcp]` extra installed a server that crashed on startup (2026-09)

`mcp>=1.0.0` was unpinned; `mcp` 2.x (released after 0.6.0) renamed
`FastMCP` and removed the low-level `Server` decorators `mcp_server.py`
uses, so every fresh `pip install "lightroom-py[mcp]"` produced a
`lightroom-mcp` that died with `AttributeError: 'Server' object has no
attribute 'list_tools'` — silently, in MCP clients that tolerate startup
failures (DeepSeek Harness, Claude Desktop). Pinned `mcp>=1.0.0,<2` and
added `tests/test_mcp_server_boot.py`, which boots the server and requires
a real `initialize` reply, so this class of drift fails CI instead of the
user. Found by walking the fresh-user install path of the dsh bundle.

### DeepSeek Harness (dsh) plugin bundle (2026-09)

The repository root now doubles as a dsh bundle (`package.json` with
`dsh.bundle` + `cordis.patch.yml`): `dsh plugin add github:drshy-org/lightroom-py`
mounts the `lightroom-mcp` server so all 15 tools appear as
`mcp__lightroom_py__*` native dsh tools. Pure configuration — no build
step, no `allowBuilds` prompt. The agent skill ships in dsh's
one-level layout at `dsh/skills/lightroom/SKILL.md`; `dsh/README.md`
covers install and skill discovery. Verified locally with
`dsh plugin add` + a run listing every tool and reading a real catalog.

## [0.6.0] — 2026-05-10

# 🎯 The geometry mask breakthrough.

Empirically verified against real Lightroom Classic 15.3: **synthetic radial-gradient masks written via raw `apply_settings` RENDER autonomously** — no AI compute step, no Export dialog, no user click. 35.44% pixel-diff vs unmasked baseline, mask localized exactly to specified frame coordinates (96.8% in target quadrant, 1.1% in opposite quadrant with correct feather falloff).

This closes the largest remaining gap in pro-photographer workflow coverage. Portrait, fashion, and landscape pros — who need selective dodge/burn, subject brightening without AI dependency, graduated ND simulation, sky-only color grade — can now drive the local-adjustment side of their work from agents.

### Added
- **`develop.mask_create_radial`** — Python sub-client + Lua handler + CLI command. Creates a radial-gradient (elliptical) mask with full local adjustment surface. Geometry: `top/bottom/left/right` (normalized 0..1 frame coords), `angle`, `feather`, `midpoint`, `roundness`, `invert`. Adjustments: 20+ Local* keys (exposure, contrast, highlights, shadows, whites, blacks, clarity, dehaze, saturation, hue, temperature, tint, sharpness, texture, luminance_noise, defringe, moire, toning_hue, toning_sat, grain). Multiple calls append additional masks (each in its own correction group).
- **`develop.mask_create_linear`** — same shape, with `zero_x/zero_y → full_x/full_y` line endpoints. ⚠️ Schema probed by analogy with radial; not yet empirically verified at synthesis time. Radial is the verified path. Linear is best-effort.
- **CLI**: `lightroom develop mask create-radial --left 0.05 --right 0.5 --top 0.4 --bottom 0.95 --exposure 1.0 --selection` — full per-adjustment flags, defaults give a centered mid-sized ellipse.

### Fixed — mask_list counting was always 0 for geometry masks
LR Classic 15.3 unifies ALL masks (AI, radial, linear, brush) under `MaskGroupBasedCorrections[]` — the legacy keys `CircularGradientBasedCorrections`, `GradientBasedCorrections`, `PaintBasedCorrections` no longer exist in 15.3 catalogs. Our `mask_list` handler was reading those legacy keys, so it always reported 0 for `circular / gradient / paint`. Now traverses the unified schema and counts by the `What:` field on each CorrectionMask:
- `Mask/Image` + `MaskSubType: 1` → `ai_subject`
- `Mask/Image` + `MaskSubType: 2` → `ai_sky`
- `Mask/Image` other → `ai_other`
- `Mask/CircularGradient` → `circular`
- `Mask/Gradient` → `gradient`
- `Mask/Paint` → `paint`

New `total:` field gives a one-glance mask count. Back-compat `ai_masks:` field preserved as `ai_subject + ai_sky + ai_other`.

### What's now possible for agents
Selective dodge/burn on subjects, graduated ND on skies, vignette-style darkening (`--invert`), selective HSL/color on regions, background darkening for portraits, eye/teeth selective work (with smaller masks), and **stacking multiple masks** for composite local adjustments. Each call appends a new correction group, so agents can apply 2-3 masks (subject brighten + sky darken + foreground texture-boost) in sequence.

### Schema knowledge gained (documented for future maintenance)
`/tmp/lr-mask-v6/` contains the empirical proof:
- Radial mask geometry keys: `Top, Bottom, Left, Right, Angle, Feather, Midpoint, Roundness, Flipped, Version`
- Correction group adjustment keys: 20+ `Local*` keys parallel to LR's slider names with `2012` suffix on the modern subset

### Versions
- `pyproject` 0.5.0 → 0.6.0
- `__version__` 0.5.0 → 0.6.0
- bridge server version 0.5.0 → 0.6.0
- `PLUGIN_VERSION` 0.5.0 → 0.6.0
- `Info.lua` VERSION 0.5.0 → 0.6.0

### What's still NOT covered
- **Brush mask creation** (`Mask/Paint`): stroke data is in a complex `Dabs:` array; not yet probed.
- **AI mask compute trigger from `apply_settings`**: still requires LR's Export-dialog "Update affected photos" click (Adobe SDK gap, already documented v0.4.2).
- **Spot removal create**: Adobe SDK doesn't expose this.

## [0.5.0] — 2026-05-10

Comprehensive **typed Develop API** + **EXIF query layer** + **export production-quality**. Pure agent ergonomics: every common photographer action now has a first-class verb instead of raw Adobe-key dict gymnastics. Two real bugs caught + fixed against LR 15.3 along the way.

### Added — Typed Develop wrappers (8 new verbs over apply_settings)
- **`develop crop`** — `--top/--left/--right/--bottom/--angle/--constrain-to-warp`
- **`develop hsl`** — `--hue band=value`, `--saturation band=value`, `--luminance band=value` for the 8 LR HSL bands (red/orange/yellow/green/aqua/blue/purple/magenta)
- **`develop color-grade`** — full 3-way wheels + global wheel + blending/balance. Transparently routes Shadow/Highlight Hue+Sat through legacy `SplitToning*` keys (LR 15.3 quirk: new `ColorGrade*` schema only accepts those values for Midtone/Global/Lum). Auto-sets `EnableSplitToning=true` when needed.
- **`develop transform`** — `--vertical/--horizontal/--rotate/--scale/--x-offset/--y-offset/--aspect/--upright`. Upright modes: off/auto/level/vertical/full.
- **`develop lens-correction`** — `--enable-profile/--distortion-amount/--vignetting-amount/--chromatic-aberration-scale/--remove-chromatic-aberration/--auto-lateral-ca`
- **`develop calibration`** — `--profile "Adobe Color"/--shadow-tint/--red-hue/--red-sat/--green-hue/--green-sat/--blue-hue/--blue-sat`
- **`develop detail`** — Detail panel: `--sharpness/--sharpen-radius/--sharpen-detail/--sharpen-masking/--luminance-nr/--luminance-detail/--luminance-contrast/--color-nr/--color-detail/--color-smoothness`
- **`develop effects`** — Effects panel: post-crop vignette + grain (`--vignette-amount/--vignette-midpoint/--vignette-feather/--vignette-roundness/--vignette-highlight-contrast/--grain-amount/--grain-size/--grain-frequency`)

All 8 are pure Python over `apply_settings` — no new bridge handlers, zero LR-side risk. None=leave alone. Verified end-to-end on real LR 15.3.

### Added — EXIF query expansion (SQLite fast-path, no bridge round-trip)
- New columns surfaced from `AgHarvestedExifMetadata`: ISO, aperture (f-stop), shutter speed (APEX → human "1/200"), focal length (mm), capture time, GPS lat/lon + has-gps boolean.
- New `photos list` filters: `--iso ">=400"`, `--aperture "<=2.8"`, `--focal ">=85"`, `--gps/--no-gps`. Range syntax shared with `--rating`.
- **`Photo` dataclass** extended with `iso`, `aperture`, `shutter_speed`, `focal_length`, `camera`, `lens`, `has_gps`, `capture_time` (camera/lens promoted from EXIF lookup helper). JSON output exposes all.
- Agents now have full shooting-context awareness without exporting first.

### Added — Production-quality exports
- `library export` extended with: `--sharpening low|standard|high`, `--sharpening-media screen|matte|glossy`, `--resize-long-edge N`, `--resize-max-width N`, `--resize-max-height N`, `--dpi N`, `--filename-template "{{image_name}}_web"` (LR token format), `--watermark`, `--watermark-name`, `--minimize-metadata`.
- Resize verified end-to-end: `--resize-long-edge 1920` lands a 1920×1280 JPEG (exact 3:2). DPI verified at 96 vs LR's default 240.
- Watermark passthrough uses LR's saved-watermark name/UUID. Tested user must have a watermark saved in LR's Edit Watermarks dialog.

### Fixed — two mask bugs caught against real LR 15.3
- **`develop mask clear --kind ai|all|gradient|circular|paint`** crashed with `bad argument #1 to 'next' (table expected, got string)`. Root cause: handler used `""` as a sentinel to clear correction lists, but LR's `applyDevelopSettings` iterates these values with `next()` expecting a table. Fix: pass empty array `{}`. All 5 kinds now work.
- **`develop mask list` always reported `red_eye: 1`** even on clean photos. Root cause: handler used `s.RedEyeInfo and 1` (truthiness check), but LR 15.3 always sets `RedEyeInfo` to an empty list `{}` even when no red-eye corrections exist (empty Lua tables are truthy). Fix: count length like other mask types. Clean photos now correctly report `red_eye: 0`.

### Versions
- `pyproject` 0.4.2 → 0.5.0
- `__version__` 0.4.2 → 0.5.0
- bridge server version 0.4.2 → 0.5.0
- `PLUGIN_VERSION` 0.4.2 → 0.5.0
- `Info.lua` VERSION 0.4.2 → 0.5.0

## [0.4.2] — 2026-05-07

Install-UX sprint. Cuts the install flow from 6 steps to 3 user actions and eliminates the manual token paste that was the most-complained-about friction point. No new bridge handlers; pure Python + Lua-side ergonomics. Also adds the empirically-verified AI mask compute path documentation (caught earlier this session).

### Added
- **`lightroom setup`** — one-command installer that runs plugin install + bridge token generation + LaunchAgent install + skill install + opens Lightroom Classic. Reduces first-time install to: `pip install lightroom-py` → `lightroom setup` → enable plugin in LR's Plug-in Manager (the one Adobe-required manual step).
- **`lightroom bridge install-service`** — installs the bridge server as a macOS LaunchAgent so it auto-starts on login. No more "keep `bridge start` running in a terminal." Plist label `com.lightroom-py.bridge`. Logs to `~/.lightroom/logs/bridge.{out,err}.log`. KeepAlive=true for crash recovery.
- **`lightroom bridge uninstall-service`** — symmetric removal of the LaunchAgent.
- **`lightroom bridge service-status`** — show whether the LaunchAgent is loaded + running, with PID.
- **Plugin-side token auto-load** (`BridgeState.lua`) — the LR plugin now reads `~/.lightroom/profiles/<profile>/bridge.json` directly on every plugin load and every Start, syncing host/port/token into LrPrefs. **Eliminates manual token paste entirely.** Honours `$LIGHTROOM_HOME` and `$LIGHTROOM_PROFILE` for multi-profile setups. bridge.json is now the single source of truth; LrPrefs is a cache.
- **`Configure...` dialog**: shows whether the token was auto-loaded and where bridge.json was read from. Still allows manual override for non-default setups.
- **Better `lightroom doctor`**: now reports macOS LaunchAgent status, and prints a numbered "Next:" hint after the table when something needs attention (instead of leaving the user to figure it out).

### Changed
- `Development Status :: 3 - Alpha` → `4 - Beta`. Seven tagged releases + real-LR validation across LR Classic 15.3 justifies the bump.
- `StartBridge.lua`: re-syncs from bridge.json before starting (picks up token rotation since LR launched).

### Documented
- AI mask compute path: confirmed via empirical pixel-diff test that `Adaptive: Subject` preset application via `LrPhoto:applyPreset` triggers LR's "AI Updates Required" dialog on Export. Clicking Export with the auto-checked "Update affected photos" box renders the AI mask into output (20.93% pixel-diff verified). This is the path agents use to drive AI masks; previously memory believed this was a hard Adobe-side blocker. Synthetic AI mask writes via raw `apply_settings` still produce no rendering, but preset-driven flow works end-to-end with one user click per export batch.

### Versions
- `pyproject` 0.4.1 → 0.4.2
- `__version__` 0.4.1 → 0.4.2
- bridge server version 0.4.1 → 0.4.2
- `PLUGIN_VERSION` 0.4.1 → 0.4.2
- `Info.lua` VERSION 0.4.0 → 0.4.2

### Migration notes
- Existing users: re-run `lightroom bridge install --force` to update the plugin, then optionally `lightroom bridge install-service` to switch to the LaunchAgent (no more terminal). Existing token in bridge.json is preserved.
- Fresh installs: `pip install lightroom-py` then `lightroom setup`. That's it.
- **macOS TCC gotcha**: LaunchAgents cannot read files under `~/Documents`, `~/Desktop`, `~/Downloads`, `~/Pictures`, `~/Movies`, or `~/Music` without Full Disk Access. If your venv lives in one of these, `bridge install-service` (and `setup`) will detect this, refuse to install the LaunchAgent, and tell you the workarounds: install lightroom-py in `~/.lightroom/venv`, use `pip install --user`, or run `lightroom bridge start` manually. Caught and fixed via E2E test pre-launch.

## [0.4.1] — 2026-05-02

Real-LR validation pass for v0.4.0. Caught 5 bugs and fixed all of them via hot-reload (no LR restarts during the validation session itself). Every v0.4 verb now verified working against real LR Classic 15.3.

### Fixed (all caught against real LR; hot-reloaded in place)
- **`develop.curve_get` "attempt to call a string value"** inside `withReadAccessDo`. Same gap as `develop.get_settings` from v0.3.x — read-only operations don't need the wrapper. Direct read works.
- **`develop.snapshot_create` "Yielding is not allowed within a C or metamethod call"**. The inner `pcall` around `photo:createDevelopSnapshot` blocked the API's internal yield. Switched to `LrTasks.pcall`.
- **`develop.snapshot_list` returning the whole snapshot object as the `name` field**. `getDevelopSnapshots()` returns tables with `id_global` / `snapshotID` / `name` fields; we now extract them properly.
- **`develop.process_version_get` and `develop.mask_list`**: same `withReadAccessDo` issue as `curve_get`. Dropped wrappers.
- **`photos.rating_step` failing on 0→0 transition with `Invalid rating: 0`**. The Lua ternary trick `(new == 0) and nil or new` evaluates to `new` because `nil` is falsy in `and`-then-`or` short-circuits. Replaced with explicit if/else.
- **`photos.select_none` and `photos.select_inverse` "assertion failed!"**. LR's `setSelectedPhotos(nil, {})` rejects the nil first arg. Workaround: keep a single anchor photo as the "deselected" state (LR has no truly-empty selection), and short-circuit `select_inverse` when the inverse is empty.

### Validation summary against real LR Classic 15.3
| Verb group | Status |
|---|---|
| `develop curve get/set/preset/linear/s-curve` | ✅ all working; SQLite confirms points land |
| `develop snapshot create/list` | ✅ |
| `develop process-version get/set` | ✅ (your test photo reports `ProcessVersion = "15.4"` — interesting LR behaviour) |
| `develop mask list/clear` | ✅ |
| `develop paste-settings --subset` | ✅ subset filter works correctly |
| `develop reset-crop/masking/spot/redeye/transforms` | ✅ |
| `ai stage-select-subject/sky` | ⚠️ as documented — dispatches but LR likely ignores the keys |
| `photos find-by-path` | ✅ |
| `photos list/count` with `--file-format/--path-substring/--color` | ✅ |
| `photos select / select-extend / select-all / select-none / select-inverse` | ✅ |
| `photos next / previous` | ✅ |
| `photos flag-pick / flag-reject / flag-clear` | ✅ |
| `photos rate-up / rate-down` (incl. 0 boundary) | ✅ |
| `photos color-cycle [--reverse]` | ✅ |

### Versions
- `pyproject` 0.4.0 → 0.4.1
- `__version__` 0.4.0 → 0.4.1
- bridge server version 0.4.0 → 0.4.1
- `PLUGIN_VERSION` 0.4.0 → 0.4.1
- `Info.lua` VERSION unchanged at 0.4.0 (manifest didn't change)

## [0.4.0] — 2026-05-01

Feature catch-up sprint to close the gap with `znznzna/lightroom-cli` (124 commands). Adds 30 new verbs across develop / photos / mask / ai. Tests: 88 (was 66). Plugin handlers: 50+ (was 36).

### Added — Develop module catch-up
- **Tone curve** (`develop curve get|set|preset|linear|s-curve`). Channel-aware (`rgb` / `red` / `green` / `blue`); accepts custom point lists `[x1, y1, x2, y2, ...]` 0..255 or named presets `Linear / Medium Contrast / Strong Contrast`.
- **Snapshots** (`develop snapshot create|list`). Wraps `LrPhoto:createDevelopSnapshot` and `getDevelopSnapshots`.
- **Process version** (`develop process-version get|set`). Read/write `ProcessVersion` from develop settings (`11.0` for PV2012, `6.7` for PV2010, `5.0` for PV2003).
- **Targeted resets**: `develop reset-crop`, `reset-masking`, `reset-spot`, `reset-redeye`, `reset-transforms`. Each clears a specific subset of develop settings without touching the rest.
- **Paste-settings** (`develop paste-settings PAYLOAD_JSON --subset=...`). Mirrors LR's "Paste Settings…" dialog: pass the source photo's `get-settings` output and an optional comma-separated subset of keys.
- **Masks read + clear** (`develop mask list|clear`). `mask list` summarizes counts of AI / gradient / circular / paint / retouch / red-eye masks per photo via `getDevelopSettings`. `mask clear --kind=all|ai|gradient|circular|paint` nils out the relevant settings keys.

### Added — AI staging surface (honest no-ops)
- `ai stage-select-subject` / `ai stage-select-sky` — write speculative `EnableSubjectSelectMask` / `EnableSkySelectMask` keys via `applyDevelopSettings`. **Same SDK gap as `ai stage-denoise`**: LR Classic 15.3 doesn't expose a public AI-mask compute trigger, so the keys are likely ignored. Documented honestly in docstrings + CLI yellow-warning text. Use LR's Masking panel manually for real subject/sky selection.

### Added — Photos rich find + selection ops
- **New `photos list / count` filters**: `--file-format` (RAW/JPG/TIFF/PSD/DNG/VIDEO), `--path-substring` (matches inside the absolute file path via SQL JOIN), `--color` (red/yellow/green/blue/purple/empty).
- **`photos find-by-path SUBSTRING`**: alias for `list --path-substring`.
- **Selection management**: `select-extend` (combine without replace), `select-all` / `select-none` / `select-inverse`, `next` / `previous` (move pivot through active source).
- **Flags**: `flag-pick` / `flag-reject` / `flag-clear` (sets `pickStatus` to 1 / -1 / 0 respectively).
- **Step verbs**: `rate-up` / `rate-down` (clamped 0..5; 0 → nil to clear), `color-cycle [--reverse]` (`""→red→yellow→green→blue→purple→""`).

### Internals
- 16 new Lua handlers (`develop.curve_*`, `develop.snapshot_*`, `develop.process_version_*`, `develop.reset_*`, `develop.paste_settings`, `develop.mask_list/clear`, `ai.stage_select_*`, `photos.select_extend/all/none/inverse/next/previous`, `photos.set_pick_status`, `photos.rating_step`, `photos.color_step`).
- 30 new Python sub-client methods + 30 new CLI commands.
- New SQLite WHERE clauses on `list_photos / count_photos`: `file_format`, `path_substring` (via `EXISTS (SELECT 1 FROM file JOIN folder JOIN root)` to construct full path inline), `color_label`.
- 22 new tests (`tests/test_develop_v04.py`, `tests/test_photos_v04.py`).

### Scope cuts vs original Phase B/D plan
Punted to v0.5 in favor of shipping the catch-up faster:
- **Develop local adjustments** (`develop local set/get/apply`) and **filter authoring** (`graduated/radial/brush/range`) — both require deep LR mask-data-table authoring; the SDK exposes the data shape but not all the geometry helpers, and our existing `apply-settings` already covers any known-key writes.
- **Smart collection creation** — needs `LrCollectionSearchDescription` authoring (P2 in the gap analysis).
- **Preview generation** — `edit-in export` already covers the "render to JPEG so Claude can see" use case.
- **Schema-driven MCP** — current 15-tool MCP server is hand-curated; auto-deriving from one schema is a net-win refactor but doesn't ship new user features.

### Versions
- `pyproject` 0.3.1 → 0.4.0
- `__version__` 0.3.1 → 0.4.0
- bridge server version 0.3.1 → 0.4.0
- `PLUGIN_VERSION` 0.3.1 → 0.4.0
- `Info.lua` VERSION 0.3.0 → 0.4.0

### Validation status
Code-only release. Real-LR validation pending (bridge needs to be restarted for the v0.4.0 plugin). Expected bug surface: same Lua-yieldability and missing-API patterns as previous versions; hot-reload tooling makes any bugs found a fast iteration loop.

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
