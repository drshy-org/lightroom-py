# lightroom-py

> **Drive Adobe Lightroom Classic from Python and Claude.** First open agent driver with verified programmatic mask creation (35.4% pixel-diff confirmed) and the AI mask compute path documented elsewhere as impossible.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LR Classic 15.3 verified](https://img.shields.io/badge/LR%20Classic-15.3%20verified-orange.svg)](#what-this-can-and-cannot-do)
[![Tests](https://img.shields.io/badge/tests-101%20passing-brightgreen.svg)](#development)

**62 bridge handlers · 80 CLI verbs · 101 tests · 7+ real-LR validation sessions documented in [CHANGELOG.md](CHANGELOG.md).** Unofficial, MIT, not affiliated with Adobe.

---

## Install — 3 user actions

```bash
pip install lightroom-py            # 1. install
lightroom setup                     # 2. one-command: plugin + LaunchAgent + skill
                                    # 3. In LR: Plug-in Manager → enable
                                    #    "lightroom-py bridge"  (~10 sec, one-time)
```

`lightroom setup` installs the LR plugin into `~/Library/Application Support/Adobe/Lightroom/Modules/`, generates a bridge token at `~/.lightroom/profiles/default/bridge.json`, registers a macOS LaunchAgent that auto-starts the bridge server on login (no terminal), and installs the Claude agent skill. The token auto-loads into LR's plugin — **no manual paste**.

Verify with `lightroom doctor`.

<details>
<summary><b>Install variants + macOS TCC gotcha + Windows notes</b></summary>

### Variants
| Need | Command |
|---|---|
| Default (CLI + Python lib) | `pip install lightroom-py` |
| With Claude Desktop MCP server | `pip install "lightroom-py[mcp]"` |
| With ExifTool fast-path for XMP | `pip install "lightroom-py[exiftool]"` |
| Everything (mcp + exiftool + dev) | `pip install "lightroom-py[all]"` |

### macOS TCC-protected venvs
LaunchAgents on macOS can't read files under `~/Documents`, `~/Desktop`, `~/Downloads`, `~/Pictures`, `~/Movies`, `~/Music` without Full Disk Access. **Install your venv outside those dirs**:

```bash
python3 -m venv ~/.lightroom/venv
~/.lightroom/venv/bin/pip install lightroom-py
~/.lightroom/venv/bin/lightroom setup
```

`lightroom setup` and `bridge install-service` detect protected paths and refuse with workaround instructions before silently failing.

### Windows
Manual bridge start (no LaunchAgent equivalent yet):

```bash
pip install lightroom-py
lightroom bridge install
lightroom bridge start         # leave running
# Then in LR: Plug-in Manager → enable
```

</details>

---

## What you can do

| Surface | Verbs |
|---|---|
| **Catalog** | `catalog open / info / stats` — counts of photos / folders / keywords / collections |
| **Photos** | `photos list / count / find-by-path` — filter by rating, camera, lens, keyword, date, color label, file format, **ISO, aperture, focal length, GPS**; SQLite read fast-path (50k+ catalogs return instantly) |
| **Selection + nav** | `select`, `select-all/none/inverse/extend`, `next`, `previous` |
| **Flags + ratings** | `flag-pick/reject/clear`, `rate-up/rate-down`, `color-cycle` |
| **Metadata** | `add-keywords` (hierarchical `"People\|Family\|Mom"`), `rate`, `color`, `set-iptc` (caption/title/headline/copyright/creator/city/state/country) |
| **XMP** | `metadata write-xmp / read-xmp` + ExifTool fast-path |
| **Develop — globals** | `apply-preset`, `apply-settings`, `paste-settings --subset`, `get-settings`, `copy`, `reset`, live `set` |
| **Develop — typed** | `crop`, `hsl`, `color-grade`, `transform`, `lens-correction`, `calibration`, `detail`, `effects` |
| **Develop — tone curve** | `curve get/set/preset/linear/s-curve` — RGB + per-channel |
| **Develop — snapshots** | `snapshot create/list` — safety checkpoints before agent edits |
| **Develop — process version** | `process-version get/set` |
| **Develop — targeted resets** | `reset-crop / -masking / -spot / -redeye / -transforms` |
| **Masks — read + clear** | `mask list / clear` (unified `MaskGroupBasedCorrections` schema, LR 15.3+) |
| **Masks — create** ⭐ | `mask create-radial` (**verified end-to-end**) + `create-linear` (best-effort) with 20+ Local* adjustments per mask |
| **AI mask compute** ⭐ | `apply-preset --folder "Adaptive: Subject"` + `library export` → LR's "AI Updates Required" dialog → one click → mask renders (verified 20.91% pixel-diff) |
| **Collections** | `list / create / add / remove / delete / get-photos` — regular + smart |
| **Library** | `list-folders`, `export` (JPEG/TIFF/PSD/DNG with **watermark, output sharpening, resize, DPI, filename templates, minimize-metadata**), `make-virtual-copy`, `stack` |
| **Edit-In** | `export` to disk, `run` for full roundtrip (export → external tool → reimport as stack) |
| **Dev tools** | `bridge reload` (hot-reload Lua handlers without LR restart), `bridge eval` (arbitrary Lua), `bridge tail-log` |
| **Service mgmt** (macOS) | `bridge install-service / uninstall-service / service-status` |

### What's NOT implementable (Adobe SDK gaps, documented)

| Surface | Why |
|---|---|
| **AI Denoise compute** | LR exposes no public trigger for `Enhance → Denoise…`. Stage settings, user clicks Enhance. |
| **Brush mask creation** | `Mask/Paint` schema (`Dabs:` stroke array) not yet probed. Use radial as workaround for v0.6. |
| **Spot removal create** | Not exposed in LR 15.3. |
| **Photo deletion** | `cat:trashPhotos` doesn't exist in 15.3. |
| **Virtual copy delete** | Only creation works. |
| **Lightroom Cloud (LR CC)** | Partner-API gated; we target LR Classic. |

---

## Command cheatsheet

Full reference: [docs/cli-reference.md](docs/cli-reference.md). The 20 most common patterns:

```bash
# === Setup + health ===
lightroom setup                                              # one-shot: plugin + service + skill
lightroom doctor                                             # diagnose install + bridge state
lightroom bridge ping                                        # round-trip test

# === Catalog + cull ===
lightroom catalog open ~/Pictures/Lightroom/MyCatalog.lrcat
lightroom photos list --rating ">=4" --iso ">=400" --since 2026-01-01 --json
lightroom photos count --keyword wedding
lightroom photos select-all
lightroom photos flag-pick --selection
lightroom photos rate-up --selection                         # cycle +1 star

# === Metadata ===
lightroom metadata add-keywords "wedding,bride,People|Family|Mom" --selection
lightroom metadata rate 5 --selection
lightroom metadata set-iptc -f caption="Sunset" -f city="Paris" --selection

# === Global develop ===
lightroom develop list-presets
lightroom develop apply-preset "Pop" --folder "Adaptive: Subject" --selection
lightroom develop apply-settings '{"Exposure2012":0.5,"Contrast2012":20}' --selection
lightroom develop hsl --saturation orange=10 --luminance blue=15 --selection
lightroom develop color-grade --shadow-hue 215 --shadow-sat 20 \
                              --highlight-hue 30 --highlight-sat 25 --selection
lightroom develop curve preset "Medium Contrast" --selection

# === ⭐ Geometry mask creation (v0.6, verified) ===
lightroom develop mask create-radial --left 0.05 --right 0.5 \
    --top 0.4 --bottom 0.95 --exposure 1.0 \
    --name "subject-brighten" --selection
lightroom develop mask create-radial --top 0.15 --bottom 0.85 \
    --left 0.15 --right 0.85 --invert --exposure -1.0 --feather 70 --selection
    # ↑ vignette-style darkening (invert = effect OUTSIDE the ellipse)

# === Safety + experimentation ===
lightroom develop snapshot create "Pre-agent-edit" --selection
lightroom develop mask list --selection                      # see what masks are on the photo
lightroom develop mask clear --kind all --selection          # wipe all masks
lightroom develop reset --selection                          # full reset

# === Production export ===
lightroom library export ~/Desktop/finals --selection --format JPEG \
    --quality 88 --resize-long-edge 1920 --sharpening standard --dpi 96

# === External tool roundtrip ===
lightroom edit-in run "magick {input} -auto-level {output}" --selection
```

## Three ways to use

### 1. CLI

```bash
lightroom photos list --rating ">=4" --iso ">=400" --json
lightroom develop apply-preset "Pop" --folder "Adaptive: Subject" --selection
lightroom develop mask create-radial --left 0.05 --right 0.5 --top 0.4 --bottom 0.95 \
    --exposure 1.0 --selection                          # ⭐ verified renders
lightroom library export ~/finals --selection --format JPEG \
    --resize-long-edge 1920 --sharpening standard --dpi 96
```

### 2. Python API

```python
import asyncio
from lightroom import LightroomClient

async def main():
    async with LightroomClient.connect() as lr:
        await lr.catalog.open("~/Pictures/Lightroom/MyCatalog.lrcat")
        keepers = await lr.photos.list(rating_gte=4, iso_gte=400, since="2026-01-01")
        for p in keepers:
            await lr.develop.apply_preset("Pop", folder="Adaptive: Subject", photo_uuids=[p.uuid])
            await lr.develop.mask_create_radial(
                left=0.05, right=0.5, top=0.4, bottom=0.95,
                exposure=1.0, photo_uuids=[p.uuid],
            )

asyncio.run(main())
```

Full async sub-client reference: [docs/python-api.md](docs/python-api.md).

### 3. Claude / agent skill

The package ships a canonical [SKILL.md](SKILL.md) installable via `lightroom skill install` (also done automatically by `lightroom setup`). It activates on `/lightroom` or intent like *"cull these photos"*, *"apply my warm preset to the selection"*, *"export the 5-star photos as JPEGs"*.

For Claude Desktop's MCP integration: `pip install "lightroom-py[mcp]"` + point Claude Desktop's config at the bundled `lightroom-mcp` binary. See [docs/mcp.md](docs/mcp.md).

### 4. DeepSeek Harness (dsh)

This repository is also a [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) plugin bundle (`package.json` + `cordis.patch.yml` at the root — pure configuration, no build step):

```bash
pip install "lightroom-py[mcp]"                        # the MCP server (0.6.1+; on 0.6.0 add "mcp<2")
dsh plugin add github:drshy-org/lightroom-py           # the bundle; tools appear as mcp__lightroom_py__*
```

All 15 MCP tools become native dsh tools; the agent skill is shipped as `dsh/skills/lightroom/SKILL.md`. Details and the skill-discovery note: [dsh/README.md](dsh/README.md). Any other MCP client (Codex CLI, Cursor, Gemini CLI, OpenCode) works the same way — point it at the `lightroom-mcp` binary.

---

## Why this exists

LR Classic is the most locked-down RAW editor for automation: no AppleScript, no COM, no UXP. The Lua plugin SDK is the only door, and `LrSocket` / `LrHttp` are outbound-only — a plugin physically cannot host a server. `lightroom-py` is the missing Python-side counterpart: a tiny `.lrplugin` polls a local Python HTTP server, and Python (or Claude via the bundled agent skill / MCP server) drives Lightroom by enqueueing commands.

```
Claude Desktop / Code / CLI ──HTTP──▶  lightroom-py (Python aiohttp)
                                              ▲
                                              │ poll / respond
                                              │
                              .lrplugin ──────┘  (Lua, runs inside LR)
```

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `LIGHTROOM_HOME` | `~/.lightroom` | Config root |
| `LIGHTROOM_PROFILE` | `default` | Per-agent isolation |

The bridge server reads `host` / `port` / `token` from `$LIGHTROOM_HOME/profiles/$LIGHTROOM_PROFILE/bridge.json` — auto-generated on first `lightroom setup`. **bridge.json is the single source of truth**; the LR plugin reads it directly.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `doctor` says "Bridge plugin not installed" | `lightroom setup` |
| `doctor` says "loaded but not currently running" + last_exit=256 | macOS TCC blocked the venv. Reinstall outside `~/Documents/`. |
| `bridge ping` times out | `lightroom bridge install --force && lightroom bridge reload`. For Lua changes outside `Handlers.lua`: `Cmd+Q` LR + relaunch. |
| Plugin disabled after a Lua error | LR auto-disables on plugin init crash. `File → Plug-in Manager` → re-enable. |
| `Yielding is not allowed within a C or metamethod call` | Use `LrTasks.pcall` instead of bare `pcall`. See CHANGELOG v0.1.2 / v0.3.1 / v0.4.1. |
| AI mask preset applied but export looks unchanged | Click **Export** on the "AI Updates Required" modal with the "Update affected photos" box checked. |

For the developer log: `lightroom bridge tail-log -n 50`.

---

## Development

```bash
git clone https://github.com/drshy-org/lightroom-py.git
cd lightroom-py
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
pre-commit install
ruff format . && ruff check . && mypy && pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the ranked backlog, architecture details, the LR sandbox gotchas list, and the hot-reload dev loop.

---

## Roadmap

| Version | Status |
|---|---|
| v0.1–v0.3 | Scaffold, bridge protocol, SQLite read, metadata writes, Collections/Library/Edit-In, MCP server, hot-reload tooling |
| v0.4 | Feature catch-up: tone curve, snapshots, process version, paste-settings, mask read/clear, AI staging |
| v0.4.2 | Install simplification — `setup`, LaunchAgent, token auto-load, TCC defensive check |
| v0.5 | Typed Develop wrappers, EXIF query layer, production exports |
| **v0.6 (current)** | **Geometry mask CREATION (radial verified). Unified `MaskGroupBasedCorrections` mask_list rewrite.** |
| v0.7 | Brush mask schema probe + create, linear mask empirical verification, Windows LaunchAgent, `.mcpb` Claude Desktop bundle |
| Out of scope | LR Cloud, AppleScript (LR doesn't expose), photo deletion + virtual-copy delete + AI compute trigger (SDK gaps) |

---

## Contact

Built by **drshy** — [drshy.xyz](http://www.drshy.xyz). Issues + PRs at [github.com/drshy-org/lightroom-py](https://github.com/drshy-org/lightroom-py). If `lightroom-py` saves you time, a star ⭐ is appreciated.

## Citation

If you use `lightroom-py` in research, blog posts, papers, or talks, please cite it. GitHub auto-detects [CITATION.cff](CITATION.cff) and shows a "Cite this repository" button on the right sidebar.

**Plain-text / APA:**

> drshy. (2026). *lightroom-py: A Python and Claude agent driver for Adobe Lightroom Classic* (v0.6.0) [Software]. Retrieved from https://github.com/drshy-org/lightroom-py — http://www.drshy.xyz

**BibTeX:**

```bibtex
@software{drshy_lightroom_py_2026,
  author       = {drshy},
  title        = {{lightroom-py}: {A} {Python} and {Claude} agent driver for {Adobe} {Lightroom} {Classic}},
  url          = {https://github.com/drshy-org/lightroom-py},
  version      = {0.6.0},
  date         = {2026-05-10},
  note         = {Author homepage: \url{http://www.drshy.xyz}}
}
```

If your work uses one of the specific empirical results from this project (the verified geometry mask creation pixel-diff, the AI mask compute path, the LR Classic 15.3 sandbox gotchas catalog), please link to the relevant [CHANGELOG.md](CHANGELOG.md) version entry so readers can find the original evidence.

## License

MIT — see [LICENSE](LICENSE). Use freely; no warranty; not affiliated with Adobe.
