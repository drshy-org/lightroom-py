--[[
  Library menu: "lightroom-py: Start bridge"
]]

local LrDialogs = import "LrDialogs"
local LrPrefs   = import "LrPrefs"

require "LightroomBridge"  -- ensures _G.LightroomPyBridge exists
local Runner = require "BridgeRunner"

local prefs = LrPrefs.prefsForPlugin()
if not prefs.bridge_token or prefs.bridge_token == "" then
  LrDialogs.message(
    "lightroom-py bridge",
    "Bridge token is not configured.\n\n" ..
    "Run `lightroom bridge start` once to generate a token, then use " ..
    "'lightroom-py: Configure...' to paste the token from " ..
    "~/.lightroom/profiles/default/bridge.json.",
    "warning"
  )
  return
end

local ok, err = Runner.start()
if ok then
  LrDialogs.message(
    "lightroom-py bridge",
    "Bridge started.\n\nTarget: http://" .. prefs.bridge_host ..
      ":" .. tostring(prefs.bridge_port) ..
      "\n\nThe plugin is now polling for commands.",
    "info"
  )
else
  LrDialogs.message("lightroom-py bridge", "Could not start: " .. (err or "unknown"), "warning")
end
