# lightroom-py

Unofficial Python library, CLI, and Claude/Codex agent skill for automating Adobe Lightroom Classic. Architecturally modeled after [`teng-lin/notebooklm-py`](https://github.com/teng-lin/notebooklm-py).

> **v0.3.1 — verified end-to-end against Lightroom Classic 15.3.** Six tagged releases of incremental real-LR validation. Honest scorecard of what works vs what doesn't is in [§ What this can and cannot do](#what-this-can-and-cannot-do) below.

> **Unofficial.** Not affiliated with Adobe. Uses the Lightroom Classic Lua plugin SDK plus a local HTTP bridge.

## Why

Lightroom Classic exposes only a Lua plugin SDK — no AppleScript, no COM, no UXP. Its `LrSocket` and `LrHttp` modules are outbound-only, so a plugin physically *cannot* host a server. `lightroom-py` is the missing Python-side counterpart: a tiny Lua plugin polls a local Python HTTP server, and Python code (or Claude via the agent skill / MCP server) drives Lightroom by enqueueing commands.

```
┌─────────────────────────────────────┐
│ Claude Desktop / Claude Code / CLI  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ lightroom-py (Python, async, Click) │
│  ├ LightroomClient                  │
│  ├ MCP server adapter (lightroom-mcp)│
│  └ LocalBridgeServer (aiohttp)      │
└──────────────┬──────────────────────┘
       HTTP poll/respond
┌──────────────▼──────────────────────┐
│ lightroom-py-bridge.lrplugin (Lua)  │
│  └ LrTasks loop dispatching to LR   │
└─────────────────────────────────────┘
            ↕ runs inside
   Adobe Lightroom Classic (macOS / Windows)
```

## Installation

### 1. Clone the repo

```bash
git clone <your-repo-url> lightroom-py
cd lightroom-py
```

### 2. Set up a virtualenv

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the package

For end users:
```bash
pip install -e .
```

With the optional MCP server (Claude Desktop integration):
```bash
pip install -e ".[mcp]"
```

For development (adds ruff, mypy, pytest, pre-commit):
```bash
pip install -e ".[dev]"
pre-commit install
```

Everything (mcp + exiftool + dev):
```bash
pip install -e ".[all]"
```

### 4. Install the Lightroom plugin

```bash
lightroom bridge install
```

This copies `lightroom-py-bridge.lrplugin` into Lightroom's Modules directory:
- macOS: `~/Library/Application Support/Adobe/Lightroom/Modules/`
- Windows: `%APPDATA%\Adobe\Lightroom\Modules\`

### 5. Start the bridge server

```bash
lightroom bridge start
```

Keep this terminal open for the whole session. It prints a token and persists connection details to `~/.lightroom/profiles/default/bridge.json`.

### 6. Enable the plugin in Lightroom

1. Launch **Lightroom Classic**.
2. `File → Plug-in Manager…`
3. If `lightroom-py bridge` doesn't appear, click **Add** and navigate to `~/Library/Application Support/Adobe/Lightroom/Modules/lightroom-py-bridge.lrplugin`.
4. Confirm it's **enabled** (green status dot).
5. Close Plug-in Manager.

### 7. Configure the token + start the bridge inside LR

1. `Library → "lightroom-py: Configure…"`
2. Paste the token from step 5 (also visible in `~/.lightroom/profiles/default/bridge.json`). Host stays `127.0.0.1`, port stays `8765`.
3. Click `Save`.
4. `Library → "lightroom-py: Start bridge"` — you should see a "Bridge started" dialog.

### 8. Verify

In another terminal:

```bash
lightroom doctor       # full health check
lightroom bridge ping  # round-trip test, should print 'pong'
```

If `ping` returns `pong {'pong': True, 'lr_version': '15.x'}`, the install is good.

## Quick start

```bash
# Set the active catalog (read-only via SQLite)
lightroom catalog open ~/Pictures/Lightroom/MyCatalog.lrcat
lightroom catalog stats

# Cull
lightroom photos list --rating ">=4" --camera Sony --since 2026-01-01
lightroom photos list --keyword wedding --json     # for agent consumption

# Tag (selection-based or by UUID)
lightroom metadata add-keywords "wedding,bride,People|Family|Mom" --selection
lightroom metadata rate 5 --selection
lightroom metadata color red --selection
lightroom metadata set-iptc -f caption="Sunset over Paris" --selection

# Develop
lightroom develop list-presets
lightroom develop apply-preset "Pop" --folder "Adaptive: Subject" --selection
lightroom develop apply-settings '{"Exposure2012": 0.5, "Contrast2012": 25}' --selection

# Edit-In (export → external tool → reimport as stack)
lightroom edit-in run "magick {input} -auto-level {output}" --selection

# Collections
lightroom collections create "Picks 2026"
lightroom collections add "Picks 2026" --selection
```

## Three ways to use

| | |
|---|---|
| **CLI** | `lightroom <verb>` — run interactively or from shell scripts. |
| **Python API** | `async with LightroomClient.connect() as lr: ...` — for custom pipelines. See [docs/python-api.md](docs/python-api.md). |
| **MCP server** | `pip install ".[mcp]"`, then point Claude Desktop at the `lightroom-mcp` binary. See [docs/mcp.md](docs/mcp.md). |

## What this can and cannot do

### ✅ Verified working against real Lightroom Classic 15.3

| Surface | Capabilities |
|---|---|
| **Catalog** | open / info / stats — counts of photos/folders/keywords/collections |
| **Photos** | filter by rating / camera / lens / keyword / date range; SQLite read fast-path (no LR round-trip per photo) |
| **Metadata** | keywords (incl. hierarchical paths `"A\|B\|C"`), ratings (0..5, 0 clears), color labels, IPTC fields (caption/title/headline/copyright/creator/city/state/country) |
| **XMP** | flush sidecars to disk, re-read sidecars from disk, bulk-write via ExifTool |
| **Develop** | list-presets (all 393 LR built-ins recognized), apply preset, apply raw settings table, get settings, copy settings, reset to defaults, live slider control |
| **Collections** | list (regular + smart + groups), create, add/remove photos, delete, get photos in a collection |
| **Library** | list folder tree, export selected photos (TIFF/JPEG/PSD/DNG/ORIGINAL), stack photos |
| **Edit-In** | export to disk, full round-trip (export → run external tool with `{input}`/`{output}` → reimport as stack) |
| **Dev tools** | hot-reload Lua handlers without restarting LR (`bridge reload`), eval arbitrary Lua, tail plugin log |

### ⚠️ Documented limits (Lightroom SDK, not our bugs)

| Surface | Why it doesn't work |
|---|---|
| **AI Denoise / AI Masks staging** | LR silently ignores the keys we write (`EnableAIDenoise`, `AIDenoiseAmount` etc.). Adobe hasn't documented public AI-feature keys for plugin authors. Workaround: stage what you can, then user runs **Enhance → Denoise…** in LR's UI. |
| **Virtual copies** | LR SDK exposes no public API in 15.3. Use **Photo → Create Virtual Copy** in LR's UI. |
| **Photo deletion from catalog** | No `cat:trashPhotos` in 15.3. Delete via LR's UI. |
| **Photo import** | `library.import_photos` raises `NotImplementedError` — same yieldability concern as edit-in import was before we cracked it; will revisit. Use LR's **File → Import** UI. |
| **Smart collection creation** | Authoring an `LrCollectionSearchDescription` is a much larger surface; intentionally deferred. Read-side smart collections work fine. |
| **Lightroom Cloud (LR CC)** | Out of scope. Partner-API gated. This library targets LR Classic only. |
| **AppleScript / COM** | LR Classic doesn't expose either. The Lua plugin SDK is the only automation surface. |

### Honest scorecard

| | |
|---|---|
| Tests | 66 passing (ruff + mypy + pytest, CI on macOS + Linux × py 3.10–3.13) |
| Real-LR validation | 6 sessions across v0.1.0 → v0.3.1, every public surface exercised |
| Bug-fix velocity | `lightroom bridge install --force && lightroom bridge reload` — ~5 seconds per Lua iteration after v0.3.1 hot-reload |
| Cross-platform | Code paths for Windows are written but **only tested on macOS** so far |

## Configuration

Environment variables (all optional):

| Variable | Default | Purpose |
|---|---|---|
| `LIGHTROOM_HOME` | `~/.lightroom` | Config root |
| `LIGHTROOM_PROFILE` | `default` | Per-agent isolation (great for parallel Claude agents) |
| `LIGHTROOM_BRIDGE_HOST` | `127.0.0.1` | Bridge server bind host |
| `LIGHTROOM_BRIDGE_PORT` | `8765` | Bridge server bind port |
| `LIGHTROOM_BRIDGE_TOKEN` | (auto-generated) | Shared secret with the LR plugin |
| `LIGHTROOM_LOG_LEVEL` | `WARNING` | Library log level |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `lightroom doctor` says "plugin not installed" | First-time setup | `lightroom bridge install` |
| `lightroom bridge status` says "unreachable" | Bridge server not running | Run `lightroom bridge start` in a terminal and leave it open |
| `lightroom bridge status` shows "plugin not connected" | Plugin not started inside LR | Library → `lightroom-py: Start bridge` |
| `lightroom bridge ping` times out | Plugin loaded stale code | `lightroom bridge install --force && lightroom bridge reload` (Handlers.lua only). For BridgeRunner.lua / Info.lua changes: Cmd+Q LR + relaunch. |
| Plugin plist shows wrong version after edit | Lua require cache | Use `lightroom bridge reload` (added in v0.3.1) — it invalidates the cache without restarting LR. |
| Status shows `version=0.x.y` for plugin where x.y is older | An old `.lrplugin` is registered somewhere else | Check `find / -name "lightroom-py-bridge.lrplugin" 2>/dev/null` and remove duplicates |
| `Yielding is not allowed within a C or metamethod call` | A Lua API yields and we're calling it inside a non-yieldable context (usually `pcall` or `withWriteAccessDo({asynchronous=false})`). | This is the most common Lua plugin gotcha. Fix is usually `LrTasks.pcall` or restructuring the access wrapper — see CHANGELOG entries v0.1.2 and v0.3.1. |

For the developer log: `lightroom bridge tail-log` prints the plugin's recent log lines.

## Development

```bash
git clone <repo-url>
cd lightroom-py
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
pre-commit install
```

Run checks:

```bash
ruff format .
ruff check .
mypy
pytest
```

Project layout:

```
src/lightroom/
  client.py              public LightroomClient
  _core.py               bridge transport (httpx + aiohttp server)
  _catalog.py / _photos.py / _develop.py / ...   (one per noun)
  _sqlite.py             read fast-path against .lrcat
  _exiftool.py           XMP fast-path via exiftool -stay_open
  bridge/                aiohttp server + protocol
  cli/                   one Click module per noun
  mcp_server.py          MCP server adapter

plugin/lightroom-py-bridge.lrplugin/
  Info.lua + LightroomBridge.lua + BridgeRunner.lua
  Handlers.lua           every command handler
  json.lua               tiny JSON encoder/decoder
  StartBridge.lua / StopBridge.lua / Status.lua / Configure.lua

tests/                   pytest + asyncio mode (66 tests)
docs/                    cli-reference, python-api, mcp, examples gallery
PLAN.md                  full design + research log
CHANGELOG.md             field-tested bugs and fixes per release
```

## Roadmap

| | |
|---|---|
| ✅ v0.1.x | Phase 0–3: scaffold, bridge protocol, SQLite read, metadata writes |
| ✅ v0.2.0 | Phase 4: Develop module |
| ✅ v0.3.0 | Phase 5–7: Collections, Library, Edit-In, MCP server, CI |
| ✅ v0.3.1 | Real-LR validation pass; hot-reload dev tooling; 5 bug fixes |
| ⏳ v0.4.0 | `library.import_photos` (file → catalog), tested-on-Windows, smart collection creation |
| 🚫 Out of scope | LR Cloud, AppleScript dictionary (LR doesn't expose), virtual copies (LR SDK gap) |

## License

MIT. See [LICENSE](LICENSE).
