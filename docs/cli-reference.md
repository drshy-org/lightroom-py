# CLI Reference

Every `lightroom` subcommand, with the same shape used in real-LR validation.

## Diagnostics

```bash
lightroom doctor                                Diagnose install + bridge
lightroom --version                             Print version
```

## Bridge lifecycle

```bash
lightroom bridge install [--force]              Copy .lrplugin into LR's Modules dir
lightroom bridge start [--host] [--port] [--token]
                                                Run the bridge server in foreground
lightroom bridge status                         Probe /health, report plugin state
lightroom bridge ping                           Round-trip a ping through LR
```

## Catalog (read-only via SQLite fast-path)

```bash
lightroom catalog open PATH                     Set the active catalog
lightroom catalog info [--json]                 Photo count, capture-time bounds
lightroom catalog stats [--json]                Counts: photos/folders/keywords/collections
lightroom catalog which                         Print active catalog path
lightroom catalog clear                         Forget the active catalog
```

## Photos

```bash
lightroom photos list [--rating ">=4"] [--camera Sony] [--lens "50mm"]
                      [--keyword wedding] [--since 2026-01-01] [--until ...]
                      [--limit 50] [--json]
lightroom photos count [filters...]
lightroom photos select UUID...                 Set LR's active selection (bridge)
```

## Metadata

All commands accept either positional UUIDs or `--selection` (use whatever's selected in LR).

```bash
lightroom metadata add-keywords "k1,k2[,People|Family|Mom]" UUID...
                                                Pipe-separated paths supported
lightroom metadata remove-keywords "k1" UUID...
lightroom metadata rate 0..5 UUID...            0 clears the rating
lightroom metadata color [red|yellow|green|blue|purple|""] UUID...
                                                "" clears
lightroom metadata set-iptc -f KEY=VALUE [-f ...] UUID...
lightroom metadata write-xmp UUID...            Flush XMP sidecars to disk
lightroom metadata read-xmp UUID...             Re-read XMP from disk
lightroom metadata fast-write-xmp PAYLOAD_JSON  Bulk via ExifTool, then sync to LR
                                                ('-' reads JSON from stdin)
```

## Develop

```bash
lightroom develop list-presets [--json]
lightroom develop apply-preset NAME [--folder FOLDER] UUID...
lightroom develop apply-settings PAYLOAD_JSON UUID...
                                                e.g. '{"Exposure2012": 0.5, "Contrast2012": 25}'
lightroom develop get-settings UUID             Dump full settings table
lightroom develop copy SRC DST...               Copy SRC's settings to one or more DSTs
lightroom develop reset UUID...                 Back to camera defaults
lightroom develop set SLIDER=VALUE [SLIDER=VALUE ...]
                                                Live LrDevelopController; requires Develop module
```

## Collections

```bash
lightroom collections list [--json]
lightroom collections create NAME [--parent SET]
lightroom collections add COLLECTION UUID...
lightroom collections remove COLLECTION UUID...
lightroom collections delete COLLECTION         Confirms before deleting
lightroom collections get-photos COLLECTION [--json]
```

## Library

```bash
lightroom library list-folders [--json]
lightroom library export OUT_DIR UUID... [--format TIFF|JPEG|PSD|DNG|ORIGINAL]
                          [--quality 0..100] [--color-space AdobeRGB]
lightroom library make-virtual-copy UUID [--copy-name NAME]
lightroom library stack UUID UUID [UUID...]    First UUID becomes top of stack
```

## Edit-In (external-tool round-trip)

```bash
lightroom edit-in export OUT_DIR UUID...        Render selected photos to disk
lightroom edit-in run COMMAND UUID...           Export → run cmd → reimport-as-stack
                                                Use {input} and {output} placeholders
                                                e.g. "magick {input} -auto-level {output}"
```

## AI staging (experimental)

```bash
lightroom ai stage-denoise UUID... [--strength 0..100]
                                                Stages settings; LR currently ignores
lightroom ai prompt-update                      Modal dialog asking user to click Update AI
```

## Skill / agent integration

```bash
lightroom skill install                         Install SKILL.md into Claude Code dirs
lightroom skill status                          Show installed skill dirs
```

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `LIGHTROOM_HOME` | `~/.lightroom` | Config root |
| `LIGHTROOM_PROFILE` | `default` | Per-agent isolation |
| `LIGHTROOM_BRIDGE_HOST` | `127.0.0.1` | Bridge bind host |
| `LIGHTROOM_BRIDGE_PORT` | `8765` | Bridge bind port |
| `LIGHTROOM_BRIDGE_TOKEN` | (auto) | Shared secret with the plugin |
| `LIGHTROOM_LOG_LEVEL` | `WARNING` | Library log level |
