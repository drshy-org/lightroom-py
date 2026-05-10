--[[
  BridgeState.lua — read connection info written by `lightroom bridge start`.

  Eliminates manual token paste: when the plugin loads, prefs are auto-synced
  from $LIGHTROOM_HOME/profiles/$LIGHTROOM_PROFILE/bridge.json
  (default ~/.lightroom/profiles/default/bridge.json).

  Honours $LIGHTROOM_HOME and $LIGHTROOM_PROFILE so multi-profile setups work.
  bridge.json is the source of truth; LrPrefs is a cache.
]]

local LrPathUtils = import "LrPathUtils"
local LrFileUtils = import "LrFileUtils"

local json = require "json"

local M = {}

local function home_dir()
  return LrPathUtils.getStandardFilePath("home")
end

local function expand_tilde(p)
  if not p or p == "" then return p end
  if p:sub(1, 2) == "~/" then
    return LrPathUtils.child(home_dir(), p:sub(3))
  end
  if p == "~" then return home_dir() end
  return p
end

-- LR's Lua sandbox does NOT expose os.getenv (caught against real LR 15.3
-- 2026-05-10 — same class as the v0.4.1 "no package.loaded" / "no setfenv"
-- gotchas). Wrap in a safe accessor so missing-env-var lookup degrades to
-- defaults instead of crashing plugin init.
local function safe_getenv(name)
  if type(os) ~= "table" or type(os.getenv) ~= "function" then
    return nil
  end
  local ok, val = pcall(os.getenv, name)
  if ok then return val end
  return nil
end

local function lightroom_home()
  local env = safe_getenv("LIGHTROOM_HOME")
  if env and env ~= "" then
    return expand_tilde(env)
  end
  return LrPathUtils.child(home_dir(), ".lightroom")
end

local function active_profile()
  local p = safe_getenv("LIGHTROOM_PROFILE")
  if p and p ~= "" then return p end
  return "default"
end

function M.bridge_state_path()
  return LrPathUtils.child(
    LrPathUtils.child(
      LrPathUtils.child(lightroom_home(), "profiles"),
      active_profile()
    ),
    "bridge.json"
  )
end

-- Returns (state_table, nil) on success or (nil, error_string) on failure.
-- state_table = { host = "...", port = N, token = "..." }
function M.read()
  local path = M.bridge_state_path()
  if not LrFileUtils.exists(path) then
    return nil, "not_found"
  end
  local f, err = io.open(path, "r")
  if not f then
    return nil, "open_failed: " .. tostring(err)
  end
  local body = f:read("*a")
  f:close()
  if not body or body == "" then
    return nil, "empty"
  end
  local ok, parsed = pcall(json.decode, body)
  if not ok or type(parsed) ~= "table" then
    return nil, "parse_failed"
  end
  return {
    host  = parsed.host or "127.0.0.1",
    port  = tonumber(parsed.port) or 8765,
    token = parsed.token or "",
  }, nil
end

-- Sync into LrPrefs: bridge.json values take precedence when the file exists.
-- This means re-running `lightroom bridge start` (which rewrites bridge.json)
-- automatically updates the plugin without any user action.
-- Returns true if a sync happened, false otherwise.
function M.sync_into_prefs(prefs)
  local state, err = M.read()
  if not state then
    return false, err
  end
  prefs.bridge_host  = state.host
  prefs.bridge_port  = state.port
  prefs.bridge_token = state.token
  return true, nil
end

return M
