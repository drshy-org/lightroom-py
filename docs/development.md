# Development

```bash
git clone https://github.com/henryshen/lightroom-py
cd lightroom-py
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Run checks

```bash
ruff format .
ruff check .
mypy
pytest
```

## Smoke test

```bash
lightroom --help
lightroom doctor
python -c "import asyncio; from lightroom import LightroomClient; \
  asyncio.run((lambda: __import__('asyncio').get_event_loop().run_until_complete(_smoke()))())"
```

## Project layout

```
src/lightroom/
  __init__.py         public surface
  client.py           LightroomClient async context manager
  _core.py            shared transport core
  _catalog.py         …    one file per noun, mirroring notebooklm-py
  _photos.py          …
  _develop.py         …
  _metadata.py        …
  _collections.py     …
  _library.py         …
  _ai.py              …
  _edit_in.py         …
  bridge/
    __init__.py
    server.py         aiohttp local bridge server
    protocol.py       JSON envelope shapes
  cli/
    __init__.py
    doctor.py
    bridge.py
    catalog.py
    photos.py
    skill.py
  data/               (populated at build time: SKILL.md + bundled .lrplugin)
  paths.py            $LIGHTROOM_HOME / per-profile dirs / LR Modules dir
  exceptions.py
  types.py
  _logging.py
  lightroom_cli.py    Click root group → cli/*

plugin/lightroom-py-bridge.lrplugin/   (the Lua bridge — copied into LR's Modules dir)
  Info.lua
  LightroomBridge.lua
  StartBridge.lua / StopBridge.lua / Status.lua / Shutdown.lua

tests/                                  (pytest + asyncio mode)
docs/                                   (this folder)
PLAN.md                                  full design + research log
```
