---
name: lightroom
description: Automate Adobe Lightroom Classic — list photos, apply develop presets, manage keywords/ratings/collections, run AI metadata workflows. Activates on /lightroom or intent like "cull these photos", "apply my warm preset", "tag this batch".
---

# Lightroom Automation

> **⚠️ Phase 0 scaffold — most operations are not yet implemented.** This skill describes the planned surface; check `lightroom doctor` for current state.

Programmatic control of Adobe Lightroom Classic via a local Python bridge. Use this skill to drive culling, develop adjustments, metadata management, and exports from Claude.

## Prerequisites

Before any command, verify the install:

```bash
lightroom doctor          # checks plugin install + bridge status
lightroom bridge install  # one-time: copies .lrplugin into LR's Modules dir
```

Then in Lightroom Classic: **File → Plug-in Manager → enable "lightroom-py bridge"**, and **Library menu → "lightroom-py: Start bridge"**.

## When this skill activates

- Explicit: "/lightroom", "use lightroom-py"
- Cull / select: "find my best photos from last weekend", "rate keepers from this shoot"
- Develop: "apply my warm portrait preset to the selection", "boost exposure on the underexposed ones"
- Metadata: "add wedding+bride keywords to the selection", "write IPTC captions"
- Export: "export the 5-star photos to ~/Desktop/finals as JPEGs"

## Honest limits (mention upfront)

- **AI Denoise / AI Masks / Generative Remove**: settings can be staged, but the SDK cannot trigger the AI compute step. Use `lightroom ai stage-*` to set the parameters, then ask the user to click **Update AI Settings** in Lightroom.
- **Live slider control** (`develop.set`) only works while the user is in the **Develop module** on the target photo.
- **Direct `.lrcat` writes** are not supported — corruption risk. All writes go through the bridge plugin.
- **Lightroom Cloud** (formerly LR CC) is not supported in v1 — partner-API gated.

## Common workflows

(Implementation lands incrementally — check `lightroom <cmd> --help` for what's wired.)

```bash
# Cull
lightroom photos list --rating ">=4" --since 2026-04-01
lightroom photos select <uuid>...
lightroom metadata rate 5 --selection

# Develop
lightroom develop apply-preset "My/Warm Portrait" --selection
lightroom develop set exposure +0.30 contrast +15

# Metadata
lightroom metadata add-keywords "wedding,bride" --selection
lightroom metadata write-xmp --selection

# AI staging
lightroom ai stage-denoise --strength 50 --selection
lightroom ai prompt-update            # tells user to run Update AI

# Export
lightroom library export --selection ~/Desktop/finals --preset "JPEG 2K"
```

## See also

- Project plan and architecture: [PLAN.md](https://github.com/henryshen/lightroom-py/blob/main/PLAN.md)
- CLI reference: `lightroom --help`
