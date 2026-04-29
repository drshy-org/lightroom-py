# lightroom-py — Codex / agent guide

`lightroom-py` automates Adobe Lightroom Classic via a Python async client + a small Lua bridge plugin. See [SKILL.md](SKILL.md) for the canonical agent skill (also installable via `lightroom skill install`). This file is the Codex pointer.

## Quick orientation

- **Two pieces**: `src/lightroom/` (Python) and `plugin/lightroom-py-bridge.lrplugin/` (Lua).
- **Transport**: Python hosts an aiohttp server on `127.0.0.1:8765`; Lua plugin polls `/poll`, posts to `/respond`. `LrSocket`/`LrHttp` are outbound-only — that's why Python is the server.
- **Sub-clients** mirror nouns: `catalog`, `photos`, `develop`, `metadata`, `collections`, `library`, `ai`, `edit_in`.
- **CLI** is `lightroom <noun> <verb>`, dispatched from `src/lightroom/lightroom_cli.py`.

## Status

Phase 0 scaffold — see [PLAN.md](PLAN.md) for the roadmap. Most handlers raise `NotImplementedError`. Don't promise capabilities the bridge protocol doesn't yet wire up.

## Style

- async-first; httpx for outbound HTTP, aiohttp for the server.
- Click + Rich for CLI.
- ruff format, mypy on `src/lightroom`.
- Default: no comments unless the WHY is non-obvious.
