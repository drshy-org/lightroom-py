# CLI Reference

> Phase 0: most subcommands print a "not yet wired" notice. Surface is stable; behaviour lands incrementally.

```text
lightroom doctor                           Diagnose install + bridge
lightroom bridge install [--force]         Copy .lrplugin into LR's Modules dir
lightroom bridge status                    Bridge server + plugin handshake state
lightroom bridge start [--host] [--port]   Run the bridge server in the foreground
lightroom catalog info                     Active catalog info
lightroom catalog open PATH                Set active catalog
lightroom catalog stats                    Photo / collection / keyword counts
lightroom photos list [filters...]         Filter and list photos
lightroom photos select UUID...            Set LR's active selection
lightroom photos count                     Count photos in catalog
lightroom skill install                    Install SKILL.md into ~/.claude/skills/lightroom
lightroom skill status                     Show installed skill dirs
```

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `LIGHTROOM_HOME` | `~/.lightroom` | Config root |
| `LIGHTROOM_PROFILE` | `default` | Active profile (per-agent isolation) |
| `LIGHTROOM_BRIDGE_HOST` | `127.0.0.1` | Bridge server bind host |
| `LIGHTROOM_BRIDGE_PORT` | `8765` | Bridge server bind port |
| `LIGHTROOM_BRIDGE_TOKEN` | (auto) | Shared secret between server and plugin |
| `LIGHTROOM_LOG_LEVEL` | `WARNING` | Library log level |
