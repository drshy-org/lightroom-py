--[[
  LightroomBridge.lua — module-level state container.

  The actual poll loop runs in BridgeRunner.lua, kicked off by StartBridge.lua.
  We keep state in `_G.LightroomPyBridge` so all menu commands can see it.
]]

local LrPrefs = import "LrPrefs"

if not _G.LightroomPyBridge then
  _G.LightroomPyBridge = {
    running       = false,
    session_id    = nil,
    last_poll_ok  = nil,
    last_error    = nil,
    handler_count = 0,
    started_at    = nil,
  }
end

-- Defaults stored in plugin prefs. Configurable via Configure.lua.
local prefs = LrPrefs.prefsForPlugin()
if prefs.bridge_host == nil then prefs.bridge_host = "127.0.0.1" end
if prefs.bridge_port == nil then prefs.bridge_port = 8765 end
if prefs.bridge_token == nil then prefs.bridge_token = "" end
if prefs.poll_wait_seconds == nil then prefs.poll_wait_seconds = 25 end

return {}
