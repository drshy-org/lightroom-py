# Troubleshooting

## `lightroom doctor` says the bridge plugin is not installed

Run:

```bash
lightroom bridge install
```

This copies `lightroom-py-bridge.lrplugin` into Lightroom's Modules folder:

- macOS: `~/Library/Application Support/Adobe/Lightroom/Modules/`
- Windows: `%APPDATA%\Adobe\Lightroom\Modules\`

Then in Lightroom Classic: **File → Plug-in Manager → enable lightroom-py bridge**.

## `RuntimeError: Lightroom Classic is not supported on this OS`

`lightroom-py` runs only where Lightroom Classic runs — macOS and Windows. Linux is unsupported because LR Classic doesn't ship for Linux.

## Bridge port already in use

Set a different port:

```bash
export LIGHTROOM_BRIDGE_PORT=8766
```

Then restart both the Python bridge server (`lightroom bridge start`) and the Lua plugin (Library → "lightroom-py: Stop bridge" / "Start bridge").

## AI Denoise / Masks settings staged but not actually computed

Known and intentional limit: the LR SDK does not let plugins trigger AI compute. After `lightroom ai stage-*`, click **Update AI Settings** in Lightroom yourself.
