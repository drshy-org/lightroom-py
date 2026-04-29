# Architecture

Mirrors `teng-lin/notebooklm-py` shape. Full rationale and prior-art survey lives in [`PLAN.md`](../PLAN.md) at the project root; this file is a quick orientation for contributors.

## Two pieces

```
Python (src/lightroom/)            Lua plugin (plugin/lightroom-py-bridge.lrplugin/)
  LightroomClient                    Info.lua + LightroomBridge.lua + menu items
  ├ catalog / photos / develop       LrTasks loop:
  ├ metadata / collections / lib       poll Python /poll
  ├ ai / edit_in                       dispatch (LrCatalog/LrPhoto/LrDevelopController)
  └ bridge.LocalBridgeServer (HTTP)    POST result to /respond
        ▲   ▲                        ▲
        │   │       HTTP polling     │
        │   └────────────────────────┘
        │
        └─ optional read-only SQLite to .lrcat copy (bulk queries)
```

## Why polling instead of `LrSocket`

`LrSocket` is localhost+outbound-only and `LrHttp` is outbound-only. The plugin physically cannot host a server. Forcing Python to be the server gives standard tooling (uvicorn/aiohttp), trivial debugging (`curl localhost:8765/health`), and survives plugin restarts. Pattern proven by [`Automaat/lightroom-mcp`](https://github.com/Automaat/lightroom-mcp).

## Why a separate Lua plugin

The plugin owns no domain logic — only transport and dispatch. Adobe SDK churn between LR versions is the load-bearing risk; keeping the Lua surface tiny minimizes breakage.

## Fast paths

- **SQLite read** for bulk catalog queries (orders of magnitude faster than per-photo bridge calls; read-only on a copy when LR is running).
- **ExifTool/XMP** for batch metadata writes; bridge call to "Read Metadata from File" syncs LR.
- **Edit-In** (Topaz pattern) for pixel-level ops the SDK can't reach.

## Hard limits

- AI Denoise / Masks / Generative Remove: stage settings, can't trigger compute.
- Cloud LR: partner-API gated; out of scope for v1.
