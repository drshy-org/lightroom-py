--[[
  Library menu: "lightroom-py: Start bridge"

  Re-syncs from bridge.json before starting so token rotation is picked up.
]]

local LrDialogs = import "LrDialogs"
local LrPrefs   = import "LrPrefs"

require "LightroomBridge"  -- ensures _G.LightroomPyBridge exists
local Runner = require "BridgeRunner"
local BridgeState = require "BridgeState"

local prefs = LrPrefs.prefsForPlugin()

-- Re-sync from bridge.json right before starting — picks up any token rotation
-- since LR launched.
local synced = BridgeState.sync_into_prefs(prefs)

if not prefs.bridge_token or prefs.bridge_token == "" then
  LrDialogs.message(
    "lightroom-py bridge",
    "No bridge token found.\n\n" ..
    "Run `lightroom bridge start` once in a terminal " ..
    "(it generates a token and writes ~/.lightroom/profiles/default/bridge.json), " ..
    "then try this menu item again — the token will be auto-detected.",
    "warning"
  )
  return
end

local ok, err = Runner.start()
if ok then
  local note = ""
  if synced then
    note = "\n\n(Token auto-loaded from bridge.json — no manual config needed.)"
  end
  LrDialogs.message(
    "lightroom-py bridge",
    "Bridge started.\n\nTarget: http://" .. prefs.bridge_host ..
      ":" .. tostring(prefs.bridge_port) ..
      "\n\nThe plugin is now polling for commands." .. note,
    "info"
  )
else
  LrDialogs.message("lightroom-py bridge", "Could not start: " .. (err or "unknown"), "warning")
end
