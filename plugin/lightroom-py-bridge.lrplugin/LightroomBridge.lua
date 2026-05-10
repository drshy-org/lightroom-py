--[[
  LightroomBridge.lua — module-level state container.

  The actual poll loop runs in BridgeRunner.lua, kicked off by StartBridge.lua.
  We keep state in `_G.LightroomPyBridge` so all menu commands can see it.

  On load, we sync host/port/token from bridge.json (written by
  `lightroom bridge start`) so users never need to copy-paste a token.
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

local prefs = LrPrefs.prefsForPlugin()

-- Defaults — overwritten below if bridge.json exists.
if prefs.bridge_host == nil then prefs.bridge_host = "127.0.0.1" end
if prefs.bridge_port == nil then prefs.bridge_port = 8765 end
if prefs.bridge_token == nil then prefs.bridge_token = "" end
if prefs.poll_wait_seconds == nil then prefs.poll_wait_seconds = 25 end

-- Auto-sync from bridge.json if available — eliminates manual token paste.
-- bridge.json is the source of truth (rewritten on every `lightroom bridge start`).
local ok, BridgeState = pcall(require, "BridgeState")
if ok and BridgeState then
  local synced = BridgeState.sync_into_prefs(prefs)
  _G.LightroomPyBridge.token_auto_synced = synced
end

return {}
