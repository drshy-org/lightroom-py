# CLI reference

Every `lightroom` subcommand, current to v0.6.0. Each verb accepts `-h/--help` for full details. Commands that take photo UUIDs also accept `--selection` to use Lightroom's current selection instead.

## Top-level groups

```
ai           AI develop settings (Denoise, Masks)
bridge       Bridge plugin + server lifecycle + dev tools
catalog      Catalog-level operations (read fast-path via SQLite)
collections  Manage regular + smart collections
develop      Develop module: presets, settings, masks, curves
doctor       Diagnose install
edit-in      Export → external tool → reimport as stack
library      Folders, exports, virtual copies, stacks
metadata     Keywords, ratings, IPTC, XMP
photos       Cull / select / nav / rate / flag / color
setup        One-command installer
skill        Install / inspect agent skill
```

## setup + diagnostics

```bash
lightroom setup [--no-service] [--no-skill] [--no-open-lr] [--force]
                                              # one-command: plugin + LaunchAgent + skill + opens LR
lightroom doctor                              # full health check + actionable Next: hint
lightroom --version
```

## bridge — plugin + server + dev tools

```bash
lightroom bridge install [--force]            # copy .lrplugin into LR's Modules dir
lightroom bridge start [--host 127.0.0.1] [--port 8765] [--token ...]
                                              # foreground server (or use install-service)
lightroom bridge install-service [--host] [--port] [--force]
                                              # macOS LaunchAgent — auto-start on login
lightroom bridge uninstall-service
lightroom bridge service-status
lightroom bridge status                       # probe /health + plugin handshake
lightroom bridge ping [--timeout 10]
lightroom bridge reload                       # hot-reload Handlers.lua (no LR restart)
lightroom bridge eval 'LUA-CODE'              # arbitrary Lua in plugin context (dev tool)
lightroom bridge tail-log [-n 50]             # read plugin's recent log lines
lightroom bridge handlers                     # list registered handlers
```

## catalog

```bash
lightroom catalog open PATH                   # set the active catalog
lightroom catalog info [--json]
lightroom catalog stats [--json]              # counts: photos/folders/keywords/collections
lightroom catalog which                       # print active catalog path
lightroom catalog clear                       # forget active catalog
```

## photos — read, cull, navigate

### Read (SQLite fast-path, no bridge round-trip)

```bash
lightroom photos list [--rating ">=4"] [--camera Sony] [--lens "50mm"]
                      [--keyword wedding] [--since 2026-01-01] [--until 2026-12-31]
                      [--file-format RAW|JPG|TIFF|PSD|DNG|VIDEO]
                      [--path-substring "Wedding/2026"]
                      [--color red|yellow|green|blue|purple|""]
                      [--iso ">=400"] [--aperture "<=2.8"] [--focal ">=85"]
                      [--gps/--no-gps]
                      [--limit 50] [--json]
lightroom photos count [filters as above]
lightroom photos find-by-path SUBSTRING [--limit 50]
```

### Selection + navigation

```bash
lightroom photos select UUID...               # set LR's active selection
lightroom photos select-extend UUID...        # add to existing selection
lightroom photos select-all
lightroom photos select-none
lightroom photos select-inverse
lightroom photos next [--selection]
lightroom photos previous [--selection]
```

### Rating / flag / color

```bash
lightroom photos rate-up [UUIDS or --selection]   # cycle rating +1 (caps at 5)
lightroom photos rate-down [UUIDS or --selection] # cycle rating −1 (floor at 0)
lightroom photos flag-pick [UUIDS or --selection]
lightroom photos flag-reject [UUIDS or --selection]
lightroom photos flag-clear [UUIDS or --selection]
lightroom photos color-cycle [--reverse] [UUIDS or --selection]
```

## metadata — keywords, IPTC, XMP

```bash
lightroom metadata add-keywords "k1,k2,People|Family|Mom" UUID... | --selection
                                              # pipe-separated paths build hierarchy
lightroom metadata remove-keywords "k1,k2" UUID... | --selection
lightroom metadata rate 0..5 UUID... | --selection
                                              # 0 clears
lightroom metadata color red|yellow|green|blue|purple|"" UUID... | --selection
lightroom metadata set-iptc -f caption=... -f title=... -f headline=...
                            -f copyright=... -f creator=... -f city=...
                            -f state=... -f country=... UUID... | --selection
lightroom metadata read-xmp UUID... | --selection      # re-read XMP sidecar into catalog
lightroom metadata write-xmp UUID... | --selection     # flush catalog metadata to sidecar
```

## develop — global, typed wrappers, curves, masks, snapshots

### Presets + raw settings

```bash
lightroom develop list-presets [--json]
lightroom develop apply-preset PRESET_NAME [--folder "Adaptive: Subject"] UUID...
lightroom develop apply-settings 'JSON' UUID... | --selection
                                              # raw dict, e.g. '{"Exposure2012": 0.5}'
                                              # pass '-' to read from stdin
lightroom develop paste-settings JSON [--subset Exposure2012,Contrast2012] UUID...
lightroom develop get-settings UUID           # dump raw settings dict
lightroom develop copy SRC_UUID DST_UUID...   # copy verbatim
lightroom develop reset UUID... | --selection
lightroom develop set Exposure=0.3 Contrast=15 ...   # live slider (requires Develop module open)
```

### Typed wrappers (v0.5)

```bash
lightroom develop crop --top 0.05 --left 0.05 --right 0.95 --bottom 0.95
                       --angle 1.5 [--constrain-to-warp] UUID...
lightroom develop hsl --hue red=10 --saturation orange=-5 --luminance blue=12 UUID...
                                              # bands: red orange yellow green aqua blue purple magenta
lightroom develop color-grade --shadow-hue 215 --shadow-sat 20 --shadow-lum 5
                              --midtone-hue 90 --midtone-sat 15
                              --highlight-hue 30 --highlight-sat 25
                              --global-hue 0 --global-sat 0
                              --blending 50 --balance 10 UUID...
lightroom develop transform --vertical 0 --horizontal 0 --rotate 0
                            --upright off|auto|level|vertical|full UUID...
lightroom develop lens-correction [--enable-profile] [--distortion-amount 100]
                                  [--vignetting-amount 100]
                                  [--remove-chromatic-aberration] UUID...
lightroom develop calibration --profile "Adobe Color"
                              --shadow-tint 0 --red-hue 0 --red-sat 0
                              --green-hue 0 --blue-hue 0 UUID...
lightroom develop detail --sharpness 70 --sharpen-radius 1.0 --sharpen-detail 25
                         --sharpen-masking 0 --luminance-nr 25 --color-nr 25 UUID...
lightroom develop effects --vignette-amount -25 --vignette-midpoint 50
                          --grain-amount 12 --grain-size 25 UUID...
```

### Tone curve (v0.4)

```bash
lightroom develop curve get UUID [--channel rgb|red|green|blue]
lightroom develop curve set '[0,0,64,52,128,138,255,250]' UUID...
                            [--channel rgb|red|green|blue]
lightroom develop curve preset "Linear|Medium Contrast|Strong Contrast" UUID...
lightroom develop curve linear UUID...
lightroom develop curve s-curve UUID...
```

### Snapshots + process version + targeted resets (v0.4)

```bash
lightroom develop snapshot create "Pre-agent-edit" UUID... | --selection
lightroom develop snapshot list UUID... | --selection

lightroom develop process-version get UUID
lightroom develop process-version set "11.0" UUID... | --selection
                                              # 5.0=PV2003, 6.7=PV2010, 11.0=PV2012

lightroom develop reset-crop UUID... | --selection
lightroom develop reset-masking UUID... | --selection
lightroom develop reset-spot UUID... | --selection
lightroom develop reset-redeye UUID... | --selection
lightroom develop reset-transforms UUID... | --selection
```

### Masks — list, clear, CREATE (v0.4 + v0.6 ⭐)

```bash
lightroom develop mask list UUID... | --selection
                                              # counts: ai_subject, ai_sky, ai_other, circular,
                                              # gradient, paint, retouch_areas, red_eye, total
lightroom develop mask clear [--kind all|ai|gradient|circular|paint] UUID... | --selection

# v0.6 ⭐ — verified 35.4% pixel-diff on real LR 15.3
lightroom develop mask create-radial
    --top 0.40 --bottom 0.95 --left 0.05 --right 0.50    # ellipse bounding box (0..1 normalized)
    [--angle 0] [--feather 50] [--midpoint 50] [--roundness 0]
    [--invert]                                            # apply OUTSIDE ellipse
    --exposure 1.0 [--contrast 12] [--highlights -25] [--shadows 15]
    [--whites 0] [--blacks 0] [--clarity 10] [--dehaze 5]
    [--saturation 8] [--hue 0] [--temperature 200] [--tint 0]
    [--sharpness 0] [--texture 8] [--luminance-noise 0]
    [--defringe 0] [--moire 0] [--toning-hue 0] [--toning-sat 0] [--grain 0]
    [--name "subject-brighten"]
    UUID... | --selection

# v0.6 — schema best-effort (needs LR-side empirical verification)
lightroom develop mask create-linear
    --zero-x 0.5 --zero-y 0 --full-x 0.5 --full-y 0.4    # gradient line endpoints
    [adjustment flags as above]
    UUID... | --selection
```

Multiple `create-radial` / `create-linear` calls **append** masks (each in its own correction group). To wipe: `lightroom develop mask clear`.

### AI mask compute path (v0.4.2 verified, 20.9% pixel-diff)

```bash
# Stage AI mask via Adaptive preset, then export — LR pops "AI Updates Required" dialog,
# you click Export with "Update affected photos" box checked → mask renders.

lightroom develop apply-preset "Pop" --folder "Adaptive: Subject" UUID
lightroom library export ~/finals UUID --format JPEG
#    ↑ LR shows "AI Updates Required" — click Export to compute + render
```

## library — folders, export, virtual copy, stack

```bash
lightroom library list-folders [--json]

lightroom library export OUT_DIR
    [--format TIFF|JPEG|PSD|DNG|ORIGINAL]
    [--quality 0..100]                          # JPEG only
    [--color-space AdobeRGB|sRGB|ProPhotoRGB]
    [--sharpening low|standard|high]
    [--sharpening-media screen|matte|glossy]
    [--resize-long-edge 1920]                   # cap longest edge
    [--resize-max-width 1920] [--resize-max-height 1080]
    [--dpi 96]
    [--filename-template "{{image_name}}_web"]  # LR token format
    [--watermark] [--watermark-name "MyWatermark"]
    [--minimize-metadata]
    UUID... | --selection

lightroom library make-virtual-copy UUID [--copy-name "Color version"]
lightroom library stack UUID...                # combine 2+ photos into a stack
```

## edit-in — external tool roundtrip

```bash
lightroom edit-in export OUT_DIR UUID... [--format TIFF|JPEG|...] [--quality ...]
lightroom edit-in run "magick {input} -auto-level {output}" UUID...
                                              # export → run command → reimport as stack
                                              # {input} and {output} get substituted
```

## collections

```bash
lightroom collections list [--json]
lightroom collections create "Picks 2026"
lightroom collections add "Picks 2026" UUID... | --selection
lightroom collections remove "Picks 2026" UUID... | --selection
lightroom collections delete "Picks 2026"
lightroom collections get-photos "Picks 2026" [--json]
```

## ai — staging only

The AI compute step is gated by LR's UI. These verbs stage the settings; user clicks the relevant Enhance / Update button.

```bash
lightroom ai stage-denoise --strength 50 UUID... | --selection
lightroom ai stage-select-subject UUID... | --selection
lightroom ai stage-select-sky UUID... | --selection
lightroom ai prompt-update                    # modal reminder for the user
```

For an end-to-end AI mask path that renders without user interaction beyond the Export dialog, use `develop apply-preset --folder "Adaptive: *"` + `library export` — see "AI mask compute path" above.

## skill — install agent skill

```bash
lightroom skill install                       # copy SKILL.md to ~/.claude/skills/lightroom
                                              # and ~/.agents/skills/lightroom
lightroom skill status
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LIGHTROOM_HOME` | `~/.lightroom` | Config root |
| `LIGHTROOM_PROFILE` | `default` | Per-agent isolation |

The bridge server reads `host` / `port` / `token` from `$LIGHTROOM_HOME/profiles/$LIGHTROOM_PROFILE/bridge.json` — auto-generated on first `lightroom setup`.

## See also

- [Python API reference](python-api.md) — `LightroomClient` async sub-clients
- [MCP server setup](mcp.md) — Claude Desktop integration
- [Architecture](architecture.md) — bridge protocol, Lua plugin internals
- [Troubleshooting](troubleshooting.md)
- [CHANGELOG](../CHANGELOG.md) — every released bug-fix and feature with real-LR validation evidence
