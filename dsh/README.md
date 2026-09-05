# lightroom-py on DeepSeek Harness (dsh)

Adobe **Lightroom Classic** for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness):
this bundle mounts the [lightroom-py](https://github.com/drshy-org/lightroom-py) MCP server so the
agent can read your catalog, apply develop settings and presets, export, and tag photos —
all against the Lightroom Classic running on **your own machine**. No cloud, no upload.

## Install

```bash
pip install lightroom-py                                   # Python side: server + Lightroom plugin installer
lightroom bridge install                                   # one-time: installs the Lightroom plugin
dsh plugin add github:drshy-org/lightroom-py           # this bundle — pure config, no build step
```

Pin a commit if you prefer (`github:drshy-org/lightroom-py#<sha>`). `dsh plugin` needs
`pnpm` on PATH for external packages (`npm i -g pnpm`).

Then start the bridge and open Lightroom Classic:

```bash
lightroom bridge start
```

In Lightroom: **Library → Plug-in Extras → lightroom-py: Start bridge**. Start `dsh web`;
the tools appear as `mcp__lightroom_py__*`.

## What the agent can do

| Tool | Purpose |
|---|---|
| `catalog_info`, `catalog_stats`, `photos_list` | read the catalog (pure SQLite — works even with Lightroom closed) |
| `develop_apply_settings`, `develop_apply_preset`, `develop_list_presets`, `develop_reset` | non-destructive develop edits (`Temperature` is absolute Kelvin on RAW, a −100..100 slider on JPEG) |
| `library_export` | export JPEG/TIFF/PSD/DNG with colour space and quality |
| `metadata_*`, `collections_*` | ratings, labels, keywords, IPTC, collections |

## The bundled skill

`dsh/skills/lightroom/SKILL.md` teaches the agent the Lightroom workflow (culling, presets,
develop semantics, exports). dsh discovers skills from your workspace, not from installed
packages, so make it visible one of two ways:

```bash
# the installed package lives under the profile you added it to, e.g. profile "web":
PKG="$DSH_HOME/profiles/web/node_modules/dsh-lightroom-py"
# a) copy the skill into the workspace you run dsh from
mkdir -p .dsh/skills && cp -r "$PKG/dsh/skills/lightroom" .dsh/skills/
# b) or point dsh's bundled-skill root at the package
export DSH_BUNDLED_SKILL_DIR="$PKG/dsh/skills"
```

## Notes

- Requires a model that can call tools; for looking at exports, pick an image-capable route
  (`deepseek-v4-flash-vision-exp`) so dsh's `read_image` works.
- `LIGHTROOM_MCP=/path/to/lightroom-mcp` if the executable is not on PATH.
- Stdio children get a scrubbed environment; the server needs no secrets.
- This bundle is the Lightroom layer of a larger open-source editing harness (skills, a
  self-growing look library, quantitative convergence) — **photo-pilot**, public release
  pending. Its Photoshop sibling, `photoshop-py`, will get the same bundle treatment.

License: MIT (same as lightroom-py).
