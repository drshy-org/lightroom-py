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

-- Auto-start the poll loop when Lightroom loads this plugin (opt-out:
-- prefs.auto_start = false). Reality check (LR Classic 15.5.1,
-- 2026-09-05, see lightroom-py-bridge.log): Lightroom defers plugin
-- initialisation until the plugin is first used — the init script
-- runs at the first Plug-in Extras click, not at app launch. So this
-- block cannot remove the per-launch "Start bridge" click on current
-- LR builds; it makes that click idempotent and self-diagnosing, and
-- will start at launch on any LR build that initialises plugins
-- eagerly. Silent by design; the Python side retries, so starting
-- before the daemon is up is safe.
if prefs.auto_start == nil then prefs.auto_start = true end
-- A bridge configured without a token (bridge.json present, token "") is
-- valid — the menu Start path connects fine that way — so gate on "a
-- bridge.json was synced OR a token exists", not on a non-empty token.
local bridge_known = _G.LightroomPyBridge.token_auto_synced
  or (prefs.bridge_token ~= nil and prefs.bridge_token ~= "")
-- Outcome goes to ~/Documents/LrClassicLogs/lightroom-py-bridge.log so an
-- auto-start failure is diagnosable without opening the Status menu.
local LrLogger = import "LrLogger"
local log = LrLogger("lightroom-py-bridge")
log:enable("logfile")
log:infof("init: auto_start=%s synced=%s token_present=%s host=%s port=%s",
  tostring(prefs.auto_start), tostring(_G.LightroomPyBridge.token_auto_synced),
  tostring(prefs.bridge_token ~= nil and prefs.bridge_token ~= ""),
  tostring(prefs.bridge_host), tostring(prefs.bridge_port))
if prefs.auto_start and bridge_known then
  local run_ok, Runner = pcall(require, "BridgeRunner")
  if run_ok and Runner then
    local started, err = pcall(Runner.start)
    _G.LightroomPyBridge.auto_started = started and true or false
    if started then
      log:info("auto-start: Runner.start returned ok")
    else
      _G.LightroomPyBridge.last_error = "auto-start failed: " .. tostring(err)
      log:errorf("auto-start failed: %s", tostring(err))
    end
  else
    log:errorf("auto-start: require BridgeRunner failed: %s", tostring(Runner))
  end
else
  log:info("auto-start skipped (auto_start off or no bridge.json/token)")
end

return {}
