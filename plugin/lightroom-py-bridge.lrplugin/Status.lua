--[[
  Library menu: "lightroom-py: Status"
]]

local LrDialogs = import "LrDialogs"
local LrPrefs   = import "LrPrefs"

require "LightroomBridge"

local prefs = LrPrefs.prefsForPlugin()
local s = _G.LightroomPyBridge

local lines = {
  "Plugin: lightroom-py-bridge",
  "Target: http://" .. prefs.bridge_host .. ":" .. tostring(prefs.bridge_port),
  "Token : " .. (((prefs.bridge_token or "") ~= "") and "(set)" or "(not set)"),
  "",
  "Running       : " .. tostring(s.running),
  "Session       : " .. tostring(s.session_id or "—"),
  "Last poll OK  : " .. tostring(s.last_poll_ok or "—"),
  "Handlers run  : " .. tostring(s.handler_count or 0),
  "Last error    : " .. tostring(s.last_error or "—"),
}

LrDialogs.message("lightroom-py bridge — status", table.concat(lines, "\n"), "info")
