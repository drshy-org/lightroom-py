# lightroom-py

> **Drive Adobe Lightroom Classic from Python and Claude.** Cull, develop, mask, tag, export — by code or by AI agent. The most comprehensive open agent driver for LR Classic, with verified AI mask compute and 124+ commands.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LR Classic](https://img.shields.io/badge/LR%20Classic-15.3%20verified-orange.svg)](#what-this-can-and-cannot-do)
[![Tests](https://img.shields.io/badge/tests-88%20passing-brightgreen.svg)](#development)

> **v0.4.2 — verified end-to-end against Lightroom Classic 15.3.** 8 tagged releases of incremental real-LR validation. AI mask compute path empirically proven (20.91% pixel-diff). Honest scorecard of what works vs what doesn't is in [§ What this can and cannot do](#what-this-can-and-cannot-do) below.

> **Unofficial.** Not affiliated with Adobe. Uses the Lightroom Classic Lua plugin SDK + a local HTTP bridge.

---

## Why this exists

Lightroom Classic is the most locked-down RAW editor for automation: no AppleScript, no COM, no UXP. The Lua plugin SDK is the only door, and `LrSocket` / `LrHttp` are outbound-only, so a plugin **physically cannot host a server**.

`lightroom-py` is the missing Python-side counterpart: a tiny Lua plugin polls a local Python HTTP server, and Python (or Claude via the bundled agent skill / MCP server) drives Lightroom by enqueueing commands.

```
┌─────────────────────────────────────┐
│ Claude Desktop / Claude Code / CLI  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ lightroom-py (Python, async, Click) │
│  ├ LightroomClient (Python API)     │
│  ├ MCP server (lightroom-mcp)       │
│  ├ Click CLI (`lightroom <verb>`)   │
│  └ aiohttp bridge server            │
└──────────────┬──────────────────────┘
       HTTP poll/respond
┌──────────────▼──────────────────────┐
│ lightroom-py-bridge.lrplugin (Lua)  │
│  └ LrTasks loop dispatching to LR   │
└─────────────────────────────────────┘
            ↕ runs inside
   Adobe Lightroom Classic (macOS / Windows)
```

---

## Install — 3 user actions

```bash
pip install lightroom-py            # 1. install the package
lightroom setup                     # 2. one-command install: plugin + service + skill
                                    # 3. In LR: File → Plug-in Manager → enable
                                    #    "lightroom-py bridge"  (~10 seconds, one-time)
```

**That's it.** `lightroom setup` does:

- Copies the LR plugin into `~/Library/Application Support/Adobe/Lightroom/Modules/`
- Generates a bridge token (saved to `~/.lightroom/profiles/default/bridge.json`)
- Installs the bridge as a **macOS LaunchAgent** that auto-starts on login (no terminal needed)
- Installs the Claude agent skill into `~/.claude/skills/lightroom/` and `~/.agents/skills/lightroom/`
- Opens Lightroom Classic so you can finish enabling the plugin

The token is read directly from `bridge.json` by the LR plugin — **no manual paste step**. After enabling in Plug-in Manager, click `Library → "lightroom-py: Start bridge"` and verify with:

```bash
lightroom doctor                   # full health check
lightroom bridge ping              # round-trip → 'pong'
```

### Install variants

| Need | Command |
|---|---|
| Default (CLI + Python lib) | `pip install lightroom-py` |
| With Claude Desktop MCP server | `pip install "lightroom-py[mcp]"` |
| With ExifTool fast-path for XMP | `pip install "lightroom-py[exiftool]"` |
| Everything (mcp + exiftool + dev) | `pip install "lightroom-py[all]"` |

### macOS gotcha — TCC-protected venvs

LaunchAgents on macOS can't read files under `~/Documents`, `~/Desktop`, `~/Downloads`, `~/Pictures`, `~/Movies`, `~/Music` without Full Disk Access. **Install your venv outside those dirs**, e.g.:

```bash
python3 -m venv ~/.lightroom/venv
~/.lightroom/venv/bin/pip install lightroom-py
~/.lightroom/venv/bin/lightroom setup
```

`lightroom setup` and `bridge install-service` detect protected paths and refuse with workaround instructions before silently failing.

### Windows

Manual bridge start (no LaunchAgent equivalent yet — coming in a later release):

```bash
pip install lightroom-py
lightroom bridge install
lightroom bridge start             # leave running, or add to Startup folder
# Then in LR: Plug-in Manager → enable
```

---

## What you can do — capability matrix

### ✅ Verified working against Lightroom Classic 15.3

| Surface | Verbs |
|---|---|
| **Catalog** | `catalog open / info / stats` — counts of photos / folders / keywords / collections / smart-collections |
| **Photos (read)** | `photos list / count / find-by-path` — filter by rating, camera, lens, keyword, date, color label, file format, path substring. SQLite read fast-path: 50k+ catalogs return instantly without a per-photo bridge round-trip. |
| **Photos (selection + nav)** | `select`, `select-all`, `select-none`, `select-inverse`, `select-extend`, `next`, `previous` |
| **Photos (rating / flags / colors)** | `flag-pick`, `flag-reject`, `flag-clear`, `rate-up / rate-down` (handles 0 boundary), `color-cycle` |
| **Metadata** | `metadata add-keywords` (incl. hierarchical paths `"People\|Family\|Mom"`), `remove-keywords`, `rate`, `color`, `set-iptc` (caption / title / headline / copyright / creator / city / state / country) |
| **XMP** | `metadata write-xmp` / `read-xmp` — flush / re-read sidecars; ExifTool fast-path for batch-writes that don't need LR focus |
| **Develop (basic)** | `develop list-presets`, `apply-preset`, `apply-settings` (raw dict), `paste-settings --subset` (filtered keys), `get-settings`, `copy` (verbatim from src→dst), `reset`, `set` (live-mode sliders) |
| **Develop (tone curve)** | `develop curve get / set / preset / linear / s-curve` — channel-aware (RGB / Red / Green / Blue), accepts custom point lists or named presets |
| **Develop (snapshots)** | `develop snapshot create / list` — checkpoint before agent edits |
| **Develop (process version)** | `develop process-version get / set` |
| **Develop (targeted resets)** | `reset-crop`, `reset-masking`, `reset-spot`, `reset-redeye`, `reset-transforms` |
| **Develop (masks read)** | `develop mask list` — counts of AI / gradient / circular / paint / retouch / red-eye masks |
| **AI mask compute** | `develop apply-preset --folder "Adaptive: Subject"` (or Sky / Landscape / Portrait) → `library export` triggers LR's "AI Updates Required" dialog → user clicks **Export** once → AI mask renders into output. **Empirically verified**: 20.91% pixel-diff vs unmasked baseline. |
| **Collections** | `collections list / create / add / remove / delete / get-photos` — supports regular + smart + group folders |
| **Library** | `library list-folders`, `export` (JPEG / TIFF / PSD / DNG / ORIGINAL with quality + color space), `make-virtual-copy`, `stack` |
| **Edit-In** | `edit-in export` to disk, `edit-in run` for full round-trip (export → run external tool with `{input}`/`{output}` → reimport as stack) |
| **Dev / observability** | `bridge reload` (hot-reload Lua handlers — no LR restart), `bridge eval` (arbitrary Lua), `bridge tail-log`, `bridge handlers` (list registered) |
| **Service mgmt (macOS)** | `bridge install-service`, `uninstall-service`, `service-status` — LaunchAgent for auto-start on login |

**62 bridge handlers · 80 CLI verbs · 88 unit tests.**

### ⚠️ Documented limits (Adobe SDK gaps, not bugs)

| Surface | Why |
|---|---|
| **AI Denoise compute** | LR exposes no public trigger for `Enhance → Denoise…`. Workaround: agent stages settings, user clicks Enhance manually. |
| **AI mask compute via raw `apply_settings`** | Synthetic AI mask schemas written via `apply_settings` are accepted by LR but **silently not rendered**. Use the real preset path (`apply_preset --folder "Adaptive: …"`) — LR's "AI Updates Required" dialog on Export triggers compute correctly. |
| **Geometry mask creation** (radial / linear / brush) | Not yet investigated; planned for v0.6. |
| **Photo deletion** | `cat:trashPhotos` doesn't exist in LR 15.3. Delete via LR's UI. |
| **Virtual copy deletion** | Same — only creation works. |
| **Smart collection creation with rules** | The criteria-table schema is undocumented. Read-side smart collections work fine. |
| **Lightroom Cloud (LR CC)** | Out of scope. Partner-API gated. |

---

## Three ways to use

### 1. CLI (interactive or scripts)

```bash
lightroom photos list --rating ">=4" --camera Sony --since 2026-01-01
lightroom develop apply-preset "Pop" --folder "Adaptive: Subject" --selection
lightroom library export ~/Desktop/finals --selection --format JPEG
```

### 2. Python API

```python
import asyncio
from lightroom import LightroomClient

async def main():
    async with LightroomClient.connect() as lr:
        await lr.catalog.open("~/Pictures/Lightroom/MyCatalog.lrcat")
        keepers = await lr.photos.list(rating=">=4", since="2026-01-01")
        for p in keepers:
            await lr.metadata.add_keywords(["portfolio"], photo_uuids=[p.uuid])

asyncio.run(main())
```

See [docs/python-api.md](docs/python-api.md) for the full async sub-client surface.

### 3. Claude / agent integration

The package ships a canonical [`SKILL.md`](SKILL.md) installable into Claude Code / Claude Desktop / Codex via `lightroom skill install` (also done automatically by `lightroom setup`). It activates on `/lightroom` or intent like:

- "cull these photos"
- "apply my warm preset to the selection"
- "tag this batch with wedding + bride"
- "export the 5-star photos as JPEGs to ~/Desktop/finals"

For Claude Desktop's MCP integration, install with `pip install "lightroom-py[mcp]"` and point Claude Desktop's config at the bundled `lightroom-mcp` binary. See [docs/mcp.md](docs/mcp.md).

---

## Quick start — 30-second demo

```bash
# Set the catalog
lightroom catalog open ~/Pictures/Lightroom/MyCatalog.lrcat
lightroom catalog stats

# Cull
lightroom photos list --rating ">=4" --camera Sony --json

# Tag the current selection
lightroom metadata add-keywords "wedding,bride,People|Family|Mom" --selection
lightroom metadata rate 5 --selection
lightroom metadata color red --selection

# Apply an AI-mask preset (LR will pop the "AI Updates Required" dialog on export)
lightroom develop apply-preset "Pop" --folder "Adaptive: Subject" --selection
lightroom library export ~/Desktop/finals --selection --format JPEG --quality 90

# Or full round-trip via ImageMagick
lightroom edit-in run "magick {input} -auto-level {output}" --selection
```

---

## Configuration

All optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `LIGHTROOM_HOME` | `~/.lightroom` | Config root |
| `LIGHTROOM_PROFILE` | `default` | Per-agent isolation (great for parallel Claude agents) |

The bridge server reads `host` / `port` / `token` from `$LIGHTROOM_HOME/profiles/$LIGHTROOM_PROFILE/bridge.json`, which is auto-generated on first `lightroom bridge start` (or `lightroom setup`). The LR plugin reads the same file directly — **bridge.json is the single source of truth**, no manual paste needed.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `lightroom doctor` says "Bridge plugin not installed" | First-time setup | `lightroom setup` |
| `doctor` says "Bridge service: loaded but not currently running" + last_exit=256 | macOS TCC blocked the venv | Reinstall venv outside `~/Documents/`. See [Install variants](#install-variants). |
| `bridge ping` times out | Plugin loaded stale code | `lightroom bridge install --force && lightroom bridge reload`. For Lua changes outside `Handlers.lua`: `Cmd+Q` LR + relaunch. |
| Plugin disabled after a Lua error | LR auto-disables on plugin init crash | `File → Plug-in Manager` → click plugin → re-enable |
| `Yielding is not allowed within a C or metamethod call` | Lua API yielded inside non-yieldable context | Use `LrTasks.pcall` instead of bare `pcall`. See CHANGELOG v0.1.2 / v0.3.1 / v0.4.1. |
| AI mask preset applied but export looks unchanged | Forgot to click Export on "AI Updates Required" dialog | Re-run export, watch LR for the modal, click **Export** with the "Update affected photos" box checked |

For the developer log: `lightroom bridge tail-log -n 50`.

---

## Development

```bash
git clone https://github.com/drshy/lightroom-py.git
cd lightroom-py
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
pre-commit install
```

Run checks:

```bash
ruff format . && ruff check .
mypy
pytest
```

Project layout:

```
src/lightroom/
  client.py              public LightroomClient
  _core.py               bridge transport (httpx + aiohttp)
  _catalog.py / _photos.py / _develop.py / ...   (one per noun)
  _sqlite.py             read fast-path against .lrcat
  _exiftool.py           XMP fast-path via exiftool -stay_open
  bridge/                aiohttp server + protocol
  cli/                   one Click module per noun
  mcp_server.py          MCP server adapter

plugin/lightroom-py-bridge.lrplugin/
  Info.lua + LightroomBridge.lua + BridgeRunner.lua
  BridgeState.lua        token auto-load from bridge.json (v0.4.2)
  Handlers.lua           every command handler (62 in v0.4.2)
  json.lua               tiny JSON encoder/decoder
  StartBridge.lua / StopBridge.lua / Status.lua / Configure.lua

tests/                   pytest + asyncio mode (88 tests)
docs/                    cli-reference, python-api, mcp, examples
PLAN.md                  full design + research log
CHANGELOG.md             field-tested bugs and fixes per release
SKILL.md                 canonical agent skill, installable via `lightroom skill install`
```

---

## Roadmap

| | |
|---|---|
| ✅ v0.1.x | Phase 0–3: scaffold, bridge protocol, SQLite read, metadata writes |
| ✅ v0.2.0 | Phase 4: Develop module |
| ✅ v0.3.0 / v0.3.1 | Phase 5–7: Collections, Library, Edit-In, MCP server, hot-reload dev tooling |
| ✅ v0.4.0 / v0.4.1 | Feature catch-up sprint: tone curve, snapshots, process version, paste-settings, mask read/clear, AI staging |
| ✅ v0.4.2 | **Install simplification** — `lightroom setup`, LaunchAgent, token auto-load, doctor improvements, TCC-aware install |
| ⏳ v0.5 | Style transfer skill (`Adaptive: Subject` + paste-settings + EXIF), preview extraction from `.lrcat-Previews.lrdata`, histogram readout |
| ⏳ v0.6 | Geometry mask creation (radial / linear / brush), spot removal create, Windows LaunchAgent equivalent |
| 🚫 Out of scope | LR Cloud, AppleScript dictionary (LR doesn't expose), photo deletion (SDK gap), AI Denoise compute trigger (SDK gap) |

---

## Contact

Built by **drshy** — find me at **[drshy.xyz](http://www.drshy.xyz)**.

Found a bug, hit a SDK gap, or want to compare notes on agent-driven photo workflows? Open an [issue](https://github.com/drshy/lightroom-py/issues) or drop me a line via the homepage.

If `lightroom-py` saves you time, a star ⭐ on the repo is appreciated.

---

## License

MIT — see [LICENSE](LICENSE). Use freely; no warranty; not affiliated with Adobe.
