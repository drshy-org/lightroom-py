# lightroom-py — agent development guide

Python library + CLI + agent Skill + MCP server that drives Adobe
Lightroom Classic through a Lua plugin bridge. **Published on PyPI**
(`pip install lightroom-py`) and the LR backend for `photo-pilot`.
Sibling of `photoshop-py` (same four-surface shape).

## Status

Read `CHANGELOG.md` `[Unreleased]` → `git log` → `ls src/lightroom/`
before trusting any doc header. v0.6.0 shipped publicly; repo is
public at `github.com/drshy-org/lightroom-py`. **Changes here are
immediately visible to the world — behave like a maintainer.**

## Layout

```
src/lightroom/
  client.py            LightroomClient — async, namespaced sub-clients
  _develop.py _library.py _metadata.py _collections.py _photos.py
  _catalog.py _ai.py _edit_in.py …    one module per sub-client
  _core.py             bridge transport + token auth
  _sqlite.py           direct catalog reads (photos.list needs no LR running)
  bridge/server.py     local HTTP server the Lua plugin polls
  mcp_server.py        lightroom-mcp stdio adapter (curated 15 tools)
  cli/                 click commands + setup/doctor/bridge/skill
plugin/lightroom-py-bridge.lrplugin/   Lua plugin source
SKILL.md               the installable agent skill (lightroom skill install)
```

## Commands

```bash
.venv/bin/python -m pytest tests/ -q   # 101 tests, ~2 min — uses THIS repo's venv,
                                       # not system python
lightroom doctor                       # install + bridge diagnosis
lightroom setup                        # one-command: plugin + LaunchAgent + skill
lightroom bridge ping                  # round-trip through a live LR
```

## Conventions & gotchas

- **`Temperature` is absolute Kelvin, not a slider delta.** 5500 ≈
  neutral daylight. Sending a delta like `+8` produces an all-blue
  photo (this happened). Same for downstream consumers (photo-pilot
  presets reference these keys verbatim: `Exposure2012`,
  `Contrast2012`, `Highlights2012`, …).
- **Bridge is poll-based**: LR's Lua sandbox (`LrSocket`/`LrHttp`) is
  outbound-only — a plugin physically cannot host a server. Python
  hosts; the plugin polls. Don't design features needing inbound
  plugin connections.
- **macOS TCC trap**: the bridge runs as a LaunchAgent, which cannot
  read `~/Documents`, `~/Desktop`, `~/Downloads`, `~/Pictures` etc.
  without Full Disk Access. Venvs and exports belong outside those
  dirs (`~/.lightroom/venv` is the documented safe spot). `lightroom
  setup` and `bridge install-service` detect protected paths and
  refuse with instructions — keep that behaviour.
- **`photos.list` is a pure SQLite read** of the catalog — works with
  LR closed. Develop/metadata/export operations need LR running with
  the bridge plugin enabled.
- **MCP tool set is curated (15 tools)** in `mcp_server.py`:
  schema in `_build_tools`, branch in `_dispatch` — keep them in sync
  when adding tools (photoshop-py enforces this pairing with a
  drift-guard test; mirror that if you extend the surface here).
- **Conventional commits** + update `CHANGELOG.md` in the same
  commit. This project follows Keep-a-Changelog strictly and each
  release gets a GitHub release page + PyPI upload.
- **Publishing**: PyPI uploads and version tags only with the
  maintainer's explicit GO.

## Downstream consumers — don't break them

`photo-pilot` (and its Skills) call the MCP tool names and develop
param keys directly: `develop_apply_settings`, `library_export`,
`photos_list`, `metadata_*`. Renaming an MCP tool or changing a
param key is a breaking change for the whole photo-pilot ecosystem —
treat the MCP surface as semver-public API.
