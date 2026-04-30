---
name: lightroom
description: Automate Adobe Lightroom Classic — list/filter photos, apply develop presets and settings, manage keywords/ratings/IPTC, export for external editors. Activates on /lightroom or intent like "cull these photos", "apply my warm preset", "tag this batch", "export these as TIFF".
---

# Lightroom Automation

Programmatic control of Adobe Lightroom Classic via a local Python bridge. Use this skill to drive culling, develop adjustments, metadata management, and exports from Claude.

> **Status (v0.2.0):** Verified end-to-end against Lightroom Classic 15.3 with a real photo catalog. Bug-fix releases v0.1.1 / v0.1.2 caught real LR API mismatches that the unit-test mock plugin couldn't see — see [CHANGELOG.md](CHANGELOG.md) for the field log.

## Prerequisites

```bash
lightroom doctor              # checks plugin install + bridge status
lightroom bridge install      # one-time: copies .lrplugin into LR's Modules dir
lightroom bridge start        # leave running in a terminal — generates token
```

Then in Lightroom Classic:
1. **File → Plug-in Manager** → enable `lightroom-py bridge`.
2. **Library → "lightroom-py: Configure…"** → paste the token (from `~/.lightroom/profiles/default/bridge.json`).
3. **Library → "lightroom-py: Start bridge"**.

`lightroom bridge ping` should now return `pong`.

## Verified workflows

### Culling

```bash
lightroom catalog open ~/Pictures/Lightroom/MyCatalog.lrcat
lightroom catalog stats
lightroom photos list --rating ">=4" --camera Sony --since 2026-01-01
lightroom photos count --keyword wedding
```

All photos queries hit the SQLite read fast-path — no bridge round-trip per photo, fast even on 50k+ catalogs.

### Tagging / rating

```bash
lightroom metadata add-keywords "wedding,bride" <uuid> <uuid>
lightroom metadata rate 5 <uuid>            # 0 clears the rating
lightroom metadata color red <uuid>         # "" clears
lightroom metadata set-iptc -f caption="Sunset" -f city="Paris" <uuid>
```

Pass `--selection` instead of UUIDs to act on whatever's currently selected in Lightroom's Library module.

### Develop module

```bash
lightroom develop list-presets
lightroom develop apply-preset "Pop" --folder "Adaptive: Subject" <uuid>
lightroom develop apply-settings '{"Exposure2012": 0.5, "Contrast2012": 25}' <uuid>
lightroom develop get-settings <uuid>       # dumps the full settings table
lightroom develop copy <src-uuid> <dst-uuid> <dst-uuid>
lightroom develop reset <uuid>              # back to camera defaults
lightroom develop set Exposure=0.3 Contrast=15 Vibrance=20   # live, requires Develop module open
```

### Edit-In (external tools)

```bash
# Export only (verified working):
lightroom edit-in export ~/Desktop/exports <uuid> --format JPEG

# Full round-trip (export → tool → reimport): EXPERIMENTAL in v0.2.0.
lightroom edit-in run "magick {input} -auto-level {output}" <uuid>
```

The reimport-as-stack step is best-effort against LR 15.3 — see "honest limits" below. Workaround for failures: use `edit-in export` and drag the result back into LR manually.

## Honest limits to mention upfront

- **AI Denoise / AI Masks staging is a no-op** in v0.2.0. The Lua handler writes settings keys, but LR ignores them silently — Adobe hasn't documented public AI-feature keys for plugin authors. For real AI Denoise compute, the user must run **Enhance → Denoise…** from LR's UI manually. `lightroom ai prompt-update` shows a dialog reminding them.
- **Edit-In reimport-as-stack is experimental** — the export side works perfectly, but `catalog:addPhoto` has yieldability issues we haven't solved against LR Classic 15.3.
- **Direct `.lrcat` writes are never attempted.** All writes go through the bridge plugin. The SQLite reader is read-only against a WAL-aware copy.
- **Lightroom Cloud (formerly LR CC) is not supported.** Partner-API gated.
- **Keyword hierarchy paths** (`"People|Family|Mom"`) not supported — top-level keywords only.

## When this skill activates

- Explicit: `/lightroom`, "use lightroom-py".
- Cull: "find my best photos", "rate keepers", "show me 5-star photos from last week".
- Develop: "apply my warm portrait preset to the selection", "boost exposure by 0.5 stops".
- Metadata: "add wedding+bride keywords to the selection", "write IPTC captions".
- Export: "export the 5-star photos as JPEGs to ~/Desktop/finals".

## Troubleshooting

If a write command fails with a Lua error from the bridge:
1. Run `lightroom doctor` — confirm the plugin handshake.
2. Note the LR version reported (`lr=15.3` etc.). Some errors are LR-version-specific.
3. The `Library → "lightroom-py: Status"` menu item shows `last_error` from the most recent dispatch.

If the bridge server connection is refused: it's not running. Restart with `lightroom bridge start` in a terminal.

## See also

- Project plan and architecture: [PLAN.md](https://github.com/henryshen/lightroom-py/blob/main/PLAN.md)
- CLI reference: `lightroom --help`
- Changelog with field-tested bugs and fixes: [CHANGELOG.md](https://github.com/henryshen/lightroom-py/blob/main/CHANGELOG.md)
