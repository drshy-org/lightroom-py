# lightroom-py

> **⚠️ Pre-alpha — Phase 0 scaffold.** Architecture and CLI surface are in place; the bridge protocol and Lua poll loop are not yet implemented. See [PLAN.md](PLAN.md) for the full design and roadmap.

**Unofficial Python library, CLI, and Claude/Codex agent skill for automating Adobe Lightroom Classic.** Architecturally modeled after [`teng-lin/notebooklm-py`](https://github.com/teng-lin/notebooklm-py).

> **Unofficial — use at your own risk.** Not affiliated with Adobe. Uses the Lightroom Classic Lua plugin SDK plus a local HTTP bridge; behaviour can change with LR updates.

## Why this exists

Lightroom Classic exposes only a Lua plugin SDK — no AppleScript, no COM, no UXP. Its `LrSocket` and `LrHttp` modules are outbound-only, so a plugin physically cannot host a server. `lightroom-py` is the missing Python-side counterpart: a tiny Lua bridge plugin polls a local Python HTTP server, and Python code (or Claude via the agent skill) drives Lightroom by enqueueing commands.

## Three faces

| | |
|---|---|
| **Python API** | `async with LightroomClient.connect() as lr:` — namespaced sub-clients (`catalog`, `photos`, `develop`, `metadata`, `collections`, `library`, `ai`, `edit_in`). |
| **CLI** | `lightroom doctor`, `lightroom bridge install`, `lightroom photos list --rating ">=4"`, `lightroom develop apply-preset "..."`, `lightroom skill install`, … |
| **Agent skill** | `SKILL.md` installable via `lightroom skill install` into Claude Code (`~/.claude/skills/lightroom`) and `.agents` skill dirs. |

## Architecture (one-liner)

`Python (async client + local bridge HTTP server) ←→ poll/respond ←→ tiny Lua .lrplugin` running inside Lightroom Classic. Plus read-only SQLite for bulk catalog queries, ExifTool/XMP for batch metadata writes, and Topaz-style "Edit In" for pixel-level escape hatches.

Full design rationale, prior-art survey, and decision log: [PLAN.md](PLAN.md).

## Status (Phase 0)

```
✓ Project layout, pyproject.toml (hatchling), MIT, ruff/mypy/pre-commit
✓ Async LightroomClient skeleton with all sub-clients (NotImplementedError stubs)
✓ Click CLI with doctor / bridge / catalog / photos / skill commands
✓ aiohttp bridge server skeleton (only /health responds)
✓ Lua bridge plugin skeleton (Info.lua + menu items, no poll loop)
☐ Phase 1: bridge protocol (poll/respond, command queue, plugin handshake)
☐ Phase 2: SQLite read fast-path, photos.list / catalog.info / collections.list
☐ Phase 3: keyword / rating / IPTC writes, XMP fast-path
☐ Phase 4: develop module presets + slider control
☐ Phase 5: AI staging + Edit-In escape hatch
☐ Phase 6: SKILL.md content, ship 0.1.0 to PyPI
```

## Install (development)

```bash
git clone https://github.com/henryshen/lightroom-py.git
cd lightroom-py
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
lightroom doctor
```

## License

MIT. See [LICENSE](LICENSE).
