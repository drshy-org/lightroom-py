# lightroom-py — Research & Plan

> Goal: a Python library + CLI + Claude skill that lets agents drive Adobe Lightroom Classic, modeled architecturally on [`teng-lin/notebooklm-py`](https://github.com/teng-lin/notebooklm-py).

---

## 1. What "notebooklm-py style" means (template we are mirroring)

`notebooklm-py` is a 10k-LOC async Python package with three coordinated faces:

| Layer | Implementation |
|---|---|
| **Python API** | `NotebookLMClient` async context manager with namespaced sub-clients: `notebooks`, `sources`, `chat`, `artifacts`, `notes`, `research`, `settings`, `sharing`. One file per sub-client (`_notebooks.py`, `_sources.py`, …). Core (`_core.py`) wraps `httpx` and an internal RPC encoder/decoder. |
| **CLI** | `notebooklm …` command tree built with Click + Rich, dispatched from `notebooklm_cli.py` to `cli/` modules (one per noun). Stores per-profile state under `~/.notebooklm/`. Env vars: `NOTEBOOKLM_HOME`, `NOTEBOOKLM_PROFILE`, `NOTEBOOKLM_AUTH_JSON`. |
| **Agent skill** | A canonical [`SKILL.md`](https://github.com/teng-lin/notebooklm-py/blob/main/SKILL.md) shipped in the wheel and installable via `notebooklm skill install` (writes to `~/.claude/skills/notebooklm` and `~/.agents/skills/notebooklm`). Plus an `AGENTS.md` for Codex. |

Other shape details worth copying: `pyproject.toml` with hatchling, optional extras (`[browser]`, `[dev]`), `pytest-asyncio` with VCR cassettes for protocol tests, ruff + mypy + pre-commit, MIT license, `CHANGELOG.md`, `docs/` (cli-reference, python-api, configuration, troubleshooting, stability, rpc-development, rpc-reference, development, releasing).

The clone of the repo currently lives at `/tmp/notebooklm-py` for reference while we scaffold.

---

## 2. The hard truth about Lightroom automation

Lightroom Classic is **uniquely the most locked-down** of the major RAW editors. There is no AppleScript dictionary, no COM, no UXP, no ExtendScript — only the Lua-based **Lightroom Classic SDK**. This is the primary constraint that shapes the entire design.

### 2.1 What the SDK gives us

A `.lrplugin` is a folder with `Info.lua` declaring hooks. Useful modules:

- `LrApplication`, `LrCatalog`, `LrPhoto` — catalog/photo CRUD, keywords, ratings, collections, metadata, virtual copies, snapshots.
- `LrDevelopController` — live slider control (Exposure, Contrast, WB, HSL, Tone Curve, Sharpening, NR, Lens Correction, Effects). **Only works while user is in the Develop module on the target photo.**
- `LrPhoto:applyDevelopSettings(table)` / `getDevelopSettings()` — settings-table application from any task; works on any photo without Develop-module focus. Develop presets (`.xmp`/`.lrtemplate`) are essentially these tables serialized.
- `LrTasks` — coroutine async; most APIs must run inside a task.
- `LrHttp` — **outbound** HTTP client.
- `LrSocket` — TCP, **localhost only, outbound only** (no listen/bind). To fake duplex you open two unidirectional sockets on different ports (this is what MIDI2LR does).
- `LrFileUtils`, `LrPathUtils`, `LrShell.openPathsViaCommandLine` — file I/O + launch external binaries.

### 2.2 What's blocked (and we must design around)

- **No inbound socket / no embedded HTTP server** in the plugin. The plugin must be the *client*, not the server.
- **AI Denoise / AI Masks (Select Subject, Sky) / Generative Remove** — settings can be staged into a settings table but the plugin **cannot trigger the AI compute step**. Confirmed limitation; user must click "Update AI Settings." Design implication: expose a "stage + ask user to run" workflow.
- **Direct `.lrcat` SQLite writes** — Lightroom locks the DB while running and the schema is undocumented. Reads from a copy are fine; writes are a corruption risk. Treat SQLite as a fast read path only.
- **AppleScript / COM** — none. UI scripting via System Events / AutoHotkey is brittle and not a foundation.
- **Lightroom (Cloud) REST API** — exists at `lr.adobe.io` but is **partner-entitlement-gated** (Adobe IMS OAuth, partner approval required). Not a viable substrate for an open library targeting end users on day one.

### 2.3 XMP sidecar round-trip

External tools (ExifTool, Python) can write XMP sidecars, but Lightroom does **not** auto-import external XMP changes — it shows a metadata-mismatch badge and the user must trigger "Read Metadata from File" (or a plugin must call the SDK equivalent on the selection). Asymmetric and manual, but useful for batch metadata writes that don't need Develop focus.

---

## 3. Prior art we're learning from

| Project | Technique | What we steal |
|---|---|---|
| [`Automaat/lightroom-mcp`](https://github.com/Automaat/lightroom-mcp) | Lua plugin polls Node MCP server at `localhost:8765` every 3s; server blocks up to 30s for response. | **Polling-HTTP transport.** This is our baseline. |
| [`mikechambers/adb-mcp`](https://github.com/mikechambers/adb-mcp) | Photoshop UXP plugin holds persistent WebSocket to a "command proxy"; MCP server talks to proxy over WS. 582★. | Upgrade path if polling latency hurts; same shape: external proxy works around Adobe's no-server constraint. |
| [`rsjaffe/MIDI2LR`](https://github.com/rsjaffe/MIDI2LR) + [`micdah/LrControl`](https://github.com/micdah/LrControl) | Two unidirectional `LrSocket`s (one send, one receive), newline-framed messages, real-time slider control. | Reference for low-latency Develop-module control if we ever need sub-100ms feedback. |
| [`gesteves/lightroom-alt-text-plugin`](https://github.com/gesteves/lightroom-alt-text-plugin) | Pure-Lua plugin, calls Anthropic API, writes to IPTC `caption` via `setRawMetadata`. | Canonical "minimum viable LR ↔ Claude" shape — under 200 lines of Lua. |
| [`BPW-Photo/IPTCFiller-Lightroom-Plugin`](https://github.com/BPW-Photo/IPTCFiller-Lightroom-Plugin) | Mostly Python (anthropic, Pillow, pillow-heif, geopy) with thin LR plugin shell. | Only "Python-driving-LR" precedent; vendor-direction split (heavy work in Python, plugin minimal) is the right instinct. |
| [`fdenivac/Lightroom-SQL-tools`](https://github.com/fdenivac/Lightroom-SQL-tools), [`thatlarrypearson/LightroomClassicCatalogReader`](https://github.com/thatlarrypearson/LightroomClassicCatalogReader), [`camerahacks/lightroom-database`](https://github.com/camerahacks/lightroom-database) | Direct read of `.lrcat` SQLite + community schema docs. | Read-only fast path for bulk catalog inspection. |
| Topaz Photo AI "Edit In…" pattern | LR exports JPEG/TIFF → external app processes → result re-imported as stack. | TOS-clean **escape hatch** for anything the SDK can't express (pixel-level ops). |
| [`lou-k/lightroom-cc-api`](https://github.com/lou-k/lightroom-cc-api) | Python wrapper around Adobe Lightroom Services REST. 13★, "use with caution," partner-gated. | Shape reference if/when we ever add cloud-LR support. **Skipped for v1.** |

Comparable RAW editors for context: **darktable** has first-class Lua scripting; **Capture One** has a full AppleScript dictionary; **RawTherapee** has CLI + PP3 sidecars. LR Classic is the outlier — which is exactly why this library is worth doing.

---

## 4. Proposed architecture

Two coordinated pieces: a Python package and a small Lua bridge plugin that ships with it.

```
┌─────────────────────────────────────────────────────────────┐
│ Claude Code / Codex / OpenClaw / human in CLI               │
└──────────────┬──────────────────────────────────────────────┘
               │  natural language / CLI args
┌──────────────▼──────────────────────────────────────────────┐
│ lightroom-py (Python, async, httpx + Click)                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ LightroomClient                                       │  │
│  │  ├── catalog       (catalog-level: open/info/stats)   │  │
│  │  ├── photos        (find/filter/select/iterate)       │  │
│  │  ├── develop       (sliders, presets, settings tbls)  │  │
│  │  ├── metadata      (keywords, ratings, IPTC, GPS)     │  │
│  │  ├── collections   (collections, smart collections)   │  │
│  │  ├── library       (import/export, stacks, vcopy)     │  │
│  │  ├── ai            (stage AI settings, prompt-update) │  │
│  │  └── edit_in       (Topaz-style external handoff)     │  │
│  └───┬───────────────────────────────────────────────────┘  │
│      │ commands over HTTP                ▲ SQLite read     │
│  ┌───▼───────────────────────────────┐  │ (when LR closed │
│  │ LocalBridgeServer                 │  │  or read-only)  │
│  │  - aiohttp/uvicorn on 127.0.0.1   │  │                  │
│  │  - command queue + result store   │  │ ┌──────────────┐ │
│  │  - 30s long-poll, JSON envelopes  │  │ │ catalog.lrcat│ │
│  └───┬───────────────────────────────┘  │ └──────▲───────┘ │
└──────┼──────────────────────────────────┼────────┼─────────┘
       │ /poll (long-poll GET)            │        │
       │ /respond (POST result)           │        │
       ▼                                  │        │
┌────────────────────────────────────────────────────────────┐
│ lightroom-py-bridge.lrplugin  (Lua, ~500 lines)            │
│  - LrTasks loop: poll → dispatch → respond                 │
│  - Handlers: catalog query / develop apply / metadata write│
│  - Uses LrCatalog, LrPhoto, LrDevelopController, LrHttp    │
│  - Custom Library menu: "Bridge: Start / Stop"             │
└────────────────────────────────────────────────────────────┘
              │ runs inside ▼
       Adobe Lightroom Classic (macOS / Windows)
```

### 4.1 Why polling instead of socket

`LrSocket` is outbound-only and `LrHttp` only does outbound HTTP — the plugin **cannot host a server**. Forcing the Python side to be the server means standard tooling (uvicorn/aiohttp), trivial debugging (`curl localhost:NNNN/poll`), no two-port socket dance, and a transport that survives plugin restarts. We pay ~1s of latency on average. If a future workflow needs sub-100ms feedback (e.g. live-driving sliders from an LLM) we add the MIDI2LR-style dual-`LrSocket` channel as an opt-in fast lane.

### 4.2 Why a separate Lua bridge plugin

Keeping Lua code minimal is the load-bearing decision. The plugin is just a transport + dispatcher: it owns *no domain logic*. All command shapes, validation, retries, error formatting live in Python. This means:

- Schema changes don't require re-installing the plugin.
- The plugin survives Adobe SDK churn between LR versions because the surface it touches is small.
- We can iterate on the Python side at normal Python velocity.

### 4.3 SQLite read fast-path

When LR is closed (or for read-only queries while it's running, against a freshly-copied `.lrcat`), `lightroom-py` opens the catalog directly with `sqlite3` for bulk queries (list 50k photos, filter by camera/lens/date, dump keywords). This is orders of magnitude faster than round-tripping every photo through the bridge plugin. Writes always go through the plugin.

### 4.4 XMP / ExifTool fallback

For batch metadata writes that don't need Develop-module focus (keywords on 5,000 photos, IPTC fields, GPS), we write XMP via [ExifTool](https://exiftool.org/) and then trigger the bridge plugin to run "Read Metadata from File" on the selection. Faster than per-photo plugin calls.

### 4.5 Edit-In escape hatch

For pixel-level ops the SDK can't reach, mirror Topaz's pattern: tell LR to export selection as TIFF to a temp dir, run an external tool (or call Anthropic's vision API on the rendered file), drop the result back, and trigger LR's re-import as a stacked sibling. TOS-clean, version-stable.

---

## 5. Module-by-module mapping (notebooklm-py → lightroom-py)

| notebooklm-py | lightroom-py | Notes |
|---|---|---|
| `client.py` `NotebookLMClient` | `client.py` `LightroomClient` | `async with LightroomClient.connect() as lr:` — auto-starts bridge server, verifies plugin handshake. |
| `_core.py` (httpx + RPC) | `_core.py` (aiohttp/uvicorn server + command queue) | Inverted: we *host* the transport instead of calling out. |
| `auth.py` (Google OAuth via Playwright) | `bridge.py` (plugin handshake, port discovery, health) | No web auth; "auth" is "plugin is alive on the expected port with the expected token." |
| `_notebooks.py` | `_catalog.py` | open catalog, stats, paths, version. |
| `_sources.py` | `_library.py` | import photos, list folders, virtual copies, stacks, exports. |
| `_chat.py` | — | Drop. (No conversational surface in LR itself; the LLM lives in Claude.) |
| `_artifacts.py` (generate audio/video/quiz) | `_develop.py` + `_ai.py` | `develop` covers slider/preset application; `ai` covers staging settings for AI features and prompting the user to run "Update AI." |
| `_notes.py` | `_metadata.py` | keywords, IPTC, ratings, GPS. |
| `_research.py` | `_search.py` | smart collections, query builder. |
| `_sharing.py` | — | Drop for v1; revisit when cloud target lands. |
| `_settings.py` | `_settings.py` | preferences, profiles. |
| `cli/*.py` (one per noun) | `cli/*.py` (`catalog.py`, `photos.py`, `develop.py`, `metadata.py`, `library.py`, `ai.py`, `bridge.py`, `skill.py`, `doctor.py`) | |
| `SKILL.md` | `SKILL.md` | Same install pattern; same `lightroom skill install` CLI command. |
| `AGENTS.md` | `AGENTS.md` | Codex pointer file. |
| `rpc/encoder.py`, `rpc/decoder.py` | `bridge/protocol.py` | JSON envelope schema for poll/respond. |
| `tests/` with VCR cassettes | `tests/` with recorded plugin transcripts | Same testing philosophy: replay real protocol exchanges. |

---

## 6. CLI design (mirrors `notebooklm` patterns)

```bash
# 1. Install the bridge plugin into LR
lightroom bridge install                # copies .lrplugin into LR's Modules dir
lightroom bridge status                 # is the plugin running? what port? what version?

# 2. Catalog
lightroom catalog open ~/Pictures/My.lrcat    # writes to ~/.lightroom/context.json
lightroom catalog info
lightroom catalog stats --json

# 3. Photos
lightroom photos list --rating ">=4" --camera "Sony A7IV" --since 2026-01-01
lightroom photos select <uuid> [<uuid> ...]
lightroom photos count

# 4. Develop
lightroom develop apply-preset "My/Portrait Warm" --selection
lightroom develop set exposure +0.30 contrast +15 --photo <uuid>
lightroom develop copy <src-uuid> <dst-uuid>
lightroom develop reset --selection

# 5. Metadata
lightroom metadata add-keywords "wedding,bride" --selection
lightroom metadata rate 5 --selection
lightroom metadata write-xmp --selection         # via ExifTool fast path

# 6. AI (staged settings)
lightroom ai stage denoise --strength 50 --selection
lightroom ai prompt-update                      # tells user "go click Update AI"

# 7. Edit-In escape hatch
lightroom edit-in topaz --selection
lightroom edit-in script ./scripts/my_filter.py --selection

# 8. Skill / agent
lightroom skill install
lightroom skill status
lightroom agent show claude
lightroom agent show codex

# 9. Diagnostics
lightroom doctor                                # bridge running? plugin version? lrcat readable?
```

Env vars (mirror notebooklm-py): `LIGHTROOM_HOME` (`~/.lightroom`), `LIGHTROOM_PROFILE`, `LIGHTROOM_BRIDGE_PORT`, `LIGHTROOM_BRIDGE_TOKEN`.

---

## 7. Skill design

A single `SKILL.md` shipped in the wheel under `lightroom/data/SKILL.md`, installable to `~/.claude/skills/lightroom/` via `lightroom skill install`. Triggers on explicit `/lightroom` and intent like "cull these photos," "apply my warm preset to the selection," "tag this batch with keywords."

Skill walks Claude through:
1. Verify bridge is running (`lightroom doctor`).
2. Pick the right operation surface (catalog query → SQLite fast path; develop edit → bridge; batch metadata → XMP fast path; AI settings → stage + prompt user).
3. Use selection semantics (always pass `--selection` or explicit `--photo` UUIDs; never rely on implicit context across parallel agents).
4. Document AI compute limitations upfront so Claude doesn't promise things the SDK can't do.

Plus an `AGENTS.md` for Codex with the same content in Codex format.

Optional later: an MCP server (`lightroom-mcp`) that wraps the same Python client and exposes tools to Claude Desktop. The Python client is the source of truth; MCP and SKILL are thin adapters.

---

## 8. Roadmap

### Phase 0 — scaffold (1–2 days)
- Project layout: `pyproject.toml` (hatchling), `src/lightroom/`, `tests/`, `docs/`, ruff/mypy/pre-commit, MIT, CHANGELOG.
- Empty CLI skeleton with `lightroom doctor` returning "bridge not installed."
- CI: ruff + mypy + pytest on macOS + Windows + Linux (Linux can run unit tests; integration tests skipped).

### Phase 1 — bridge MVP (1 week)
- Python `LocalBridgeServer` with two endpoints (`/poll`, `/respond`) and a token-auth handshake.
- `lightroom-py-bridge.lrplugin`: `Info.lua`, a Library menu item ("Start Bridge" / "Stop Bridge"), an `LrTasks` poll loop, and three handlers — `ping`, `catalog.info`, `photos.count`.
- `lightroom bridge install` copies the `.lrplugin` to LR's Modules folder for current OS.
- `lightroom doctor` end-to-end happy path.
- Tests with recorded protocol fixtures.

### Phase 2 — read-heavy library (1 week)
- SQLite read fast-path: `lightroom photos list` with filters, `lightroom catalog stats`.
- Bridge handlers: `photos.find`, `photos.get_metadata`, `collections.list`.
- Selection helpers (`lightroom photos select`).

### Phase 3 — write-side library (1 week)
- Bridge handlers: keywords add/remove, ratings, color labels, collections create/add/remove.
- ExifTool XMP fast-path with "Read Metadata from File" trigger.

### Phase 4 — Develop module (1–2 weeks)
- Bridge handlers: `develop.apply_preset`, `develop.apply_settings`, `develop.copy`, `develop.reset`, plus per-slider `develop.set` for the common keys.
- Document the "Develop module must be active" caveat for live-slider mode; auto-fall-back to settings-table application when not focused.

### Phase 5 — AI staging + Edit-In (3–5 days)
- `lightroom ai stage` for denoise/masks/genrm settings injection.
- `lightroom ai prompt-update` UI (just an `LrDialogs.message` for now).
- `lightroom edit-in` external-tool round-trip pattern.

### Phase 6 — Skill + agent ergonomics (3–5 days)
- `SKILL.md`, `AGENTS.md`, `lightroom skill install`, `lightroom agent show`.
- Examples gallery in `docs/examples/`.
- Ship 0.1.0 to PyPI.

### Phase 7 — optional upgrades
- Dual-`LrSocket` fast lane for low-latency slider control (MIDI2LR-style).
- MCP server adapter for Claude Desktop.
- Adobe Lightroom Services (cloud) sub-client for users with partner credentials.

---

## 9. Open questions / risks

- **Adobe SDK version drift.** The SDK has changed across LR Classic majors. The bridge plugin's surface is intentionally small to limit churn; pin `LrSdkVersion` to the lowest we can.
- **AI feature gap is real.** We can stage settings but not trigger compute for Denoise / Select Subject / Generative Remove. Documenting this honestly upfront is critical — better than promising and failing.
- **Cross-platform plugin install.** LR's Modules folder lives at different paths on macOS vs Windows. `lightroom bridge install` must handle both.
- **TOS / distribution.** Ship our plugin source (MIT). Don't redistribute Adobe's SDK PDFs/headers — link to Adobe's download instead. Don't bundle Adobe trademarks beyond descriptive use.
- **Catalog corruption surface.** Direct SQLite must be **read-only** and against a copy when LR is running. Hardcode this; never expose a write path that bypasses the plugin.
- **Concurrency.** Multiple Claude agents driving the same LR instance can stomp the active selection. Mirror notebooklm-py's profile/context isolation: every agent passes explicit `--photo <uuid>` or owns a dedicated profile.
- **Latency.** 1–3s polling latency is fine for batch ops, painful for interactive sliders. Defer fast-lane to Phase 7.

---

## 10. Reusable building blocks to pull in

- [`Automaat/lightroom-mcp`](https://github.com/Automaat/lightroom-mcp) Lua plugin source — direct reference for the poll loop.
- [`gesteves/lightroom-alt-text-plugin`](https://github.com/gesteves/lightroom-alt-text-plugin) — clean reference for `setRawMetadata` / IPTC writes.
- [`fdenivac/Lightroom-SQL-tools`](https://github.com/fdenivac/Lightroom-SQL-tools) + [`camerahacks/lightroom-database`](https://github.com/camerahacks/lightroom-database) — schema reference and read-only query patterns.
- [`Jaid/lightroom-sdk-8-examples`](https://github.com/Jaid/lightroom-sdk-8-examples) — Adobe's official SDK example bundle.
- [`micdah/LrControl`](https://github.com/micdah/LrControl) — dual-`LrSocket` reference for Phase 7 fast lane.
- [`teng-lin/notebooklm-py`](https://github.com/teng-lin/notebooklm-py) — the architectural template, kept open while scaffolding for shape parity.

---

## 11. Decision log (for the record)

| # | Decision | Rationale |
|---|---|---|
| 1 | Target **Lightroom Classic**, not Cloud, for v1. | Cloud is partner-gated; Classic is what users actually have on disk. |
| 2 | Two pieces: Python package + tiny Lua bridge plugin. | SDK doesn't allow Python in-process; this is the only honest shape. |
| 3 | Polling HTTP transport, not `LrSocket`. | `LrSocket` is outbound-only; polling is simpler, debuggable, and survives plugin restarts. |
| 4 | Read-only SQLite fast-path for bulk queries. | Orders of magnitude faster than per-photo bridge calls. |
| 5 | ExifTool/XMP fast-path for batch metadata. | Avoids round-tripping 5,000 photos through the bridge. |
| 6 | Edit-In pattern as documented escape hatch. | TOS-clean, version-stable, covers anything the SDK can't reach. |
| 7 | Mirror notebooklm-py's Click + Rich CLI, hatchling build, SKILL.md install. | Shape parity makes the project legible to anyone who's used notebooklm-py. |
| 8 | MIT license, ship plugin source, don't redistribute Adobe SDK. | Standard for a third-party Adobe automation library. |
