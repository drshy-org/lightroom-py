--[[
  Library menu: "lightroom-py: Configure..."
  Lets the user set host / port / token without editing prefs by hand.
]]

local LrDialogs   = import "LrDialogs"
local LrPrefs     = import "LrPrefs"
local LrView      = import "LrView"
local LrFunctionContext = import "LrFunctionContext"
local LrBinding   = import "LrBinding"

LrFunctionContext.callWithContext("lightroom-py-configure", function(context)
  local prefs = LrPrefs.prefsForPlugin()
  local props = LrBinding.makePropertyTable(context)
  props.bridge_host  = prefs.bridge_host or "127.0.0.1"
  props.bridge_port  = tostring(prefs.bridge_port or 8765)
  props.bridge_token = prefs.bridge_token or ""

  local f = LrView.osFactory()
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
      title = "Find your token in ~/.lightroom/profiles/default/bridge.json",
      text_color = import("LrColor")(0.4, 0.4, 0.4),
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
