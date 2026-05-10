--[[
  Library menu: "lightroom-py: Configure..."

  In v0.4.2+ the token is auto-loaded from
  ~/.lightroom/profiles/default/bridge.json on every plugin load and every
  Start, so most users never need to open this dialog. It's still here for:
    - Manual override (custom host/port for a remote bridge)
    - Inspecting current values
    - Forcing a re-sync from bridge.json
]]

local LrDialogs   = import "LrDialogs"
local LrPrefs     = import "LrPrefs"
local LrView      = import "LrView"
local LrFunctionContext = import "LrFunctionContext"
local LrBinding   = import "LrBinding"

local BridgeState = require "BridgeState"

LrFunctionContext.callWithContext("lightroom-py-configure", function(context)
  local prefs = LrPrefs.prefsForPlugin()

  -- Try a fresh re-sync first so the dialog reflects what's actually on disk.
  -- Wrapped in pcall so a BridgeState-side bug doesn't block opening Configure.
  local sync_ok, synced = pcall(BridgeState.sync_into_prefs, prefs)
  if not sync_ok then synced = false end
  local path_ok, state_path = pcall(BridgeState.bridge_state_path)
  if not path_ok then state_path = "(unavailable)" end

  local props = LrBinding.makePropertyTable(context)
  props.bridge_host  = prefs.bridge_host or "127.0.0.1"
  props.bridge_port  = tostring(prefs.bridge_port or 8765)
  props.bridge_token = prefs.bridge_token or ""

  local f = LrView.osFactory()
  local hint
  if synced then
    hint = "✓ Auto-loaded from " .. state_path
  else
    hint = "bridge.json not found at " .. state_path ..
           "\nRun `lightroom bridge start` to create it."
  end

  local contents = f:column {
    bind_to_object = props,
    spacing = f:control_spacing(),
    f:row { f:static_text { title = "Host:",  width = 60 },
            f:edit_field { value = LrView.bind("bridge_host"),  width_in_chars = 24 } },
    f:row { f:static_text { title = "Port:",  width = 60 },
            f:edit_field { value = LrView.bind("bridge_port"),  width_in_chars = 8 } },
    f:row { f:static_text { title = "Token:", width = 60 },
            f:edit_field { value = LrView.bind("bridge_token"), width_in_chars = 40 } },
    f:static_text {
      title = hint,
      text_color = import("LrColor")(0.4, 0.4, 0.4),
      width_in_chars = 70,
      height_in_lines = 2,
    },
  }

  local action = LrDialogs.presentModalDialog {
    title  = "lightroom-py — Configure bridge",
    contents = contents,
    actionVerb = "Save",
  }

  if action == "ok" then
    prefs.bridge_host  = props.bridge_host
    prefs.bridge_port  = tonumber(props.bridge_port) or 8765
    prefs.bridge_token = props.bridge_token
    LrDialogs.message("lightroom-py bridge", "Saved.", "info")
  end
end)
