# Contributing to lightroom-py

Thanks for your interest! lightroom-py is a Python + Lua bridge for Adobe Lightroom Classic — every change has to survive both a Python test suite and Adobe's Lua plugin sandbox. This guide describes how to work effectively in that constraint.

## TL;DR for contributors

```bash
git clone https://github.com/drshy-org/lightroom-py.git
cd lightroom-py
python3 -m venv ~/.lightroom/venv          # NOT under ~/Documents (TCC blocks LaunchAgents there)
source ~/.lightroom/venv/bin/activate
pip install -e ".[all]"
pre-commit install
ruff format . && ruff check . && mypy && pytest
```

When you find something interesting in the LR Lua sandbox, **document it in `CHANGELOG.md`** under the version you're targeting. The CHANGELOG is the project's lessons log; every bug we've ever caught lives there.

---

## Where help is most needed

We rank backlog items by **what a master photographer can't yet do**. Top-of-mind items, ordered by impact:

### 🎯 High-impact (close real coverage gaps)

| Need | What it unlocks |
|---|---|
| **Brush mask creation** (`Mask/Paint`) — probe the `Dabs:` stroke array | Manual dodge/burn, fine portrait retouch. Last major gap for portrait/fashion pros. |
| **Linear mask schema verification** | Currently writes via best-effort schema (`ZeroX/Y → FullX/Y`); accepted by LR but applies as whole-image effect instead of gradient. Need a user-drawn reference linear mask to get the real geometry keys. |
| **Spot removal create** (`RetouchAreas`) | Dust spots, distractions — wedding/event pros want batch dust-removal. |
| **Smart collection rule authoring** (`createSmartCollection` criteria table) | Authoring filters via API. Read works; write is undocumented. |
| **Module switching + view mode** (`LrApplicationView:switchToModule`) | Lets the agent put LR in Develop module before a `develop set` live-driver call. |
| **History list + revert** | Lets agents experiment without snapshot bookkeeping. |
| **Auto-start bridge inside LR plugin** (plugin pref toggle) | One less click per LR launch. |

### 🟡 Medium-impact (production polish)

| Need | What it unlocks |
|---|---|
| **Windows LaunchAgent equivalent** (Task Scheduler / Startup folder) | Cross-platform parity. macOS has `bridge install-service`; Windows users currently need to run `bridge start` manually. |
| **`.mcpb` Claude Desktop bundle** | One-click install for MCP-only users. |
| **GPS read/write** (`setRawMetadata("gps", …)`) | Geotagging workflows. |
| **Capture-time write** (`setRawMetadata("dateCreated", …)`) | Correcting EXIF date bugs. |
| **Publish services** (Flickr/SmugMug/etc.) | Distribution side of the workflow. |
| **DNG conversion** (`LrCatalog:convertPhotoToDng`) | Archive workflows. |
| **Smart Preview / 1:1 Preview build** | Cull performance. |
| **Custom plugin metadata** (`setPropertyForPlugin`) | Agent state persistence inside the catalog. |
| **Stack extensions** (unstack, collapse, expand, set-position) | Stack creation works; the rest is missing. |

### 🟢 Easy / good-first-issue

- More typed wrappers for any uncovered Adobe key surface (search `apply_settings` raw key usage in CHANGELOG examples)
- Test coverage for new typed wrappers using the existing `_with_plugin` harness in `tests/test_develop_v05.py`
- Documentation: improve `docs/cli-reference.md`, `docs/python-api.md`, add cookbook recipes under `docs/examples/`
- README polish (typos, clearer install order, more screenshots)
- Translating SKILL.md activation triggers for non-English LR locales

### 🔴 Confirmed Adobe-side blockers (please don't reopen)

These have been investigated and confirmed unreachable from the Lightroom Classic Lua plugin SDK as of 15.3:

- **AI Denoise compute trigger** — `EnableAIDenoise` schema accepted but `Enhance → Denoise…` cannot be programmatically invoked. Workaround: user clicks UI button.
- **AI Subject/Sky/etc. compute via raw `apply_settings`** — same gap. The `Adaptive: *` preset + Export-dialog path *does* work (one user click per export batch) — see CHANGELOG v0.4.2.
- **Photo deletion** — no `cat:trashPhotos` in LR 15.3.
- **Virtual copy deletion** — only creation works.
- **Lightroom Cloud (LR CC)** — partner-API gated.
- **`getmetatable` on SDK objects** — LR sandbox forbids it.
- **`os.getenv`** — LR sandbox strips it. Use `LrPathUtils.getStandardFilePath("home")` for HOME; defaults for everything else.
- **`package.loaded[…] = nil`** — LR sandbox forbids it. We use `dofile` + a manual cache to invalidate on `bridge reload`.
- **`setfenv`** — LR sandbox forbids it.

---

## Architecture you need to know

```
src/lightroom/                # async Python
  client.py                   # public LightroomClient
  _core.py                    # bridge transport (httpx + aiohttp)
  _<noun>.py                  # one sub-client per noun (catalog, photos, develop, …)
  _sqlite.py                  # read fast-path against .lrcat (WAL-aware, immutable=1)
  bridge/server.py            # aiohttp server the LR plugin polls
  cli/<noun>.py               # one Click module per noun
  mcp_server.py               # MCP server adapter

plugin/lightroom-py-bridge.lrplugin/   # Lua plugin
  Info.lua                    # plugin manifest (LR-required)
  LightroomBridge.lua         # LrInitPlugin entrypoint, global state, BridgeState auto-load
  BridgeState.lua             # reads ~/.lightroom/profiles/default/bridge.json
  BridgeRunner.lua            # the poll loop (handshake → poll → dispatch → respond)
  Handlers.lua                # every command handler in one file
  json.lua                    # tiny JSON encoder/decoder
  Start/Stop/Status/Configure.lua    # menu items
```

### The transport

Lightroom's Lua `LrSocket` and `LrHttp` modules are **outbound-only** — a plugin physically cannot host a server. So Python is the server, the LR plugin is the client. The plugin long-polls `/poll` for commands; Python enqueues them. Responses come back through `/respond`. The bridge token + session-id authenticate; everything's on `127.0.0.1`.

### Adding a new command — checklist

To add a new verb like `develop.mask_create_radial`:

1. **Lua handler** in `plugin/lightroom-py-bridge.lrplugin/Handlers.lua` — `Handlers["develop.mask_create_radial"] = function(params) ... end`. Uses `target_photos(cat, params)` for UUID resolution, `cat:withWriteAccessDo` for write transactions, `LrTasks.pcall` (not bare `pcall`) for anything that may yield.
2. **Python sub-client method** in `src/lightroom/_develop.py` — typed kwargs, validates inputs, calls `self._core.call("develop.mask_create_radial", {...})`.
3. **CLI command** in `src/lightroom/cli/develop.py` — `@develop.command(...)`, Click options matching the Python kwargs.
4. **Tests** in `tests/test_develop_v05.py` (or similar) — use the `_with_plugin` harness to capture wire-level payload; assert keys.
5. **CHANGELOG entry** under `[Unreleased]`.
6. **Real-LR validation**: run the new command against a live LR session. Document any bugs found in the CHANGELOG fix list.

### LR sandbox gotchas

These have all bitten us at least once. Save yourself the time:

| Symptom | Cause | Fix |
|---|---|---|
| `Yielding is not allowed within a C or metamethod call` | Bare `pcall(...)` wrapping a yielding LR API | Use `LrTasks.pcall(...)` |
| `attempt to call field 'getenv' (a nil value)` | LR strips `os.getenv` | Use `LrPathUtils.getStandardFilePath(...)` or pcall-guard |
| `bad argument #1 to 'next' (table expected, got string)` | Passed string sentinel to an Adobe key that expects an array | Pass `{}` (empty array) instead |
| `withReadAccessDo "attempt to call a string value"` | Wrapping a read in a write-access transaction | Read-only ops don't need any wrapper |
| Stale Lua code after edit | Lua `package.loaded` cache; LR sandbox blocks `package.loaded[…] = nil` | `lightroom bridge install --force && lightroom bridge reload`. For changes outside `Handlers.lua`, restart LR. |
| Plugin disabled after a Lua error | LR auto-disables plugins that crash during init | `File → Plug-in Manager` → re-enable manually |

### Hot-reload dev loop

```bash
# Edit Handlers.lua in your repo, then:
lightroom bridge install --force      # copies plugin to LR's Modules dir
lightroom bridge reload               # tells the running plugin to re-read Handlers.lua
lightroom develop <new-verb> ...      # test
lightroom bridge tail-log -n 30       # see Lua-side log output
```

Changes to `Handlers.lua` reload without LR restart. Changes to `BridgeRunner.lua`, `LightroomBridge.lua`, `BridgeState.lua`, or `Info.lua` require `Cmd+Q` LR + relaunch.

For arbitrary in-plugin probing (great for schema discovery), use `bridge eval`:

```bash
lightroom bridge eval 'return import("LrApplication").versionString()'
lightroom bridge eval 'local cat = import("LrApplication").activeCatalog(); return cat:getTargetPhoto():getRawMetadata("uuid")'
```

---

## Code style

- **Python**: ruff + mypy. Format with `ruff format`, lint with `ruff check`. CI runs both — PRs must be clean.
- **No comments unless the WHY is non-obvious.** A hidden constraint, a subtle LR sandbox restriction, a workaround for a specific bug — those deserve comments. WHAT the code does should be clear from naming.
- **Cite real-LR validation in comments and CHANGELOG.** When you fix a bug caught against real LR, write `caught against real LR Classic <version>, <date>` so future maintainers know whether your fix is theoretical or empirical.
- **Async-first.** All client methods are `async def`. CLI handlers wrap with `asyncio.run(...)`.
- **None = leave alone.** Typed wrappers should accept `None` for unset params and skip those keys before dispatch.

## Testing

- `pytest` runs the full suite (~95s for 101 tests as of v0.6.0).
- Unit tests use `tests/test_develop_api.py`'s `_with_plugin` harness — a `LocalBridgeServer` + a `CapturingPlugin` that records the wire-level dispatch. No real LR needed.
- Integration tests against real LR are documented in CHANGELOG entries, not in pytest (real LR is environmental). When you add a new handler, run it manually against real LR before opening the PR.

## Commit + PR conventions

- One logical change per commit. Bug fix + feature in one commit is fine; "fix some random thing in another module" mixed in is not.
- Commit message body should explain **why** the change is needed, not just **what** changed.
- For bug fixes caught against real LR: include the LR error message verbatim in the commit body so it's findable later.
- All commits should pass `ruff check && mypy && pytest` locally before push.

## Reporting bugs

Before opening an issue:

1. Run `lightroom doctor` and paste the full output.
2. Run `lightroom bridge tail-log -n 50` and include relevant Lua errors.
3. State your LR Classic version (`Help → System Info` in LR).
4. Minimal reproduction: the smallest `lightroom <verb>` command that triggers the issue.

For schema-related questions (e.g., "what Adobe key does X correspond to?"), the easiest path is:

1. Apply the setting manually in LR's UI.
2. Run `lightroom develop get-settings <uuid>` and diff against a baseline.
3. Report what you found.

## License

By contributing you agree your contributions are licensed under the project's MIT license — see [LICENSE](LICENSE).

## Questions?

- File a [GitHub issue](https://github.com/drshy-org/lightroom-py/issues)
- Contact: [drshy.xyz](http://www.drshy.xyz)
