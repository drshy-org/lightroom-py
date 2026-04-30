--[[
  BridgeRunner.lua — the long-poll loop.

  Lifecycle:
    1. POST /handshake to establish a session_id.
    2. loop while running:
         GET /poll  (long-poll up to ~25s)
         if 204 → re-poll
         if 200 → dispatch handler, POST /respond
         if error → backoff and retry
    3. on stop → set running=false; loop exits at next iteration.

  This file is required from StartBridge.lua and runs inside LrTasks.startAsyncTask.
]]

local LrHttp     = import "LrHttp"
local LrLogger   = import "LrLogger"
local LrTasks    = import "LrTasks"
local LrPrefs    = import "LrPrefs"
local LrApplication = import "LrApplication"

local json     = require "json"
local Handlers = require "Handlers"

local logger = LrLogger("lightroom-py")
logger:enable("logfile")

local PLUGIN_VERSION = "0.3.0"

local M = {}

local function url_encode(s)
  if s == nil then return "" end
  s = tostring(s)
  s = s:gsub("([^%w%-_%.~])", function(c)
    return string.format("%%%02X", string.byte(c))
  end)
  return s
end

local function http_get_with_status(url, headers, timeout)
  -- LrHttp.get returns (body, headers); newer SDKs include status in headers.status.
  local body, hdrs = LrHttp.get(url, headers, timeout)
  local status = (hdrs and hdrs.status) or (body and 200) or 0
  return body, status, hdrs
end

local function http_post_with_status(url, body, headers, timeout)
  local resp_body, resp_hdrs = LrHttp.post(url, body, headers, "POST", timeout)
  local status = (resp_hdrs and resp_hdrs.status) or (resp_body and 200) or 0
  return resp_body, status, resp_hdrs
end

local function base_url()
  local prefs = LrPrefs.prefsForPlugin()
  return string.format("http://%s:%d", prefs.bridge_host, prefs.bridge_port)
end

local function token()
  return LrPrefs.prefsForPlugin().bridge_token or ""
end

local function poll_wait()
  local n = LrPrefs.prefsForPlugin().poll_wait_seconds
  return tonumber(n) or 25
end

local function lr_version_string()
  local ok, v = pcall(function() return LrApplication.versionString and LrApplication.versionString() end)
  if ok and v then return v end
  return "unknown"
end

local function do_handshake()
  local headers = {
    { field = "Content-Type", value = "application/json" },
  }
  local payload = json.encode({
    token = token(),
    plugin_version = PLUGIN_VERSION,
    lr_version = lr_version_string(),
  })
  local body, status = http_post_with_status(base_url() .. "/handshake", payload, headers, 10)
  if status ~= 200 or not body then
    return nil, "handshake failed: status=" .. tostring(status)
  end
  local ok, parsed = pcall(json.decode, body)
  if not ok or not parsed.session_id then
    return nil, "handshake: bad response"
  end
  return parsed.session_id, nil
end

-- Lua 5.1's `pcall` is implemented in C and is NOT yieldable — calling any
-- yielding LR API (e.g. cat:withWriteAccessDo waiting for a write lock) inside
-- regular pcall raises "Yielding is not allowed within a C or metamethod call".
--
-- LrTasks.pcall is LR's yield-aware pcall: same return shape as Lua's pcall
-- (success, result_or_err) but the wrapped function may yield. This is the
-- canonical idiom in Adobe's own SDK examples.
local function dispatch(method, params)
  local handler = Handlers[method]
  if not handler then
    return false, nil, "unknown_method", "no handler for: " .. tostring(method)
  end

  local ok, result_or_err = LrTasks.pcall(handler, params)
  if not ok then
    return false, nil, "handler_error", tostring(result_or_err)
  end
  return true, result_or_err, nil, nil
end

local function send_response(session_id, payload)
  local headers = {
    { field = "Content-Type", value = "application/json" },
  }
  local url = base_url() ..
    "/respond?token=" .. url_encode(token()) ..
    "&session_id=" .. url_encode(session_id)
  http_post_with_status(url, json.encode(payload), headers, 10)
end

function M.start()
  if _G.LightroomPyBridge.running then
    return false, "already running"
  end
  _G.LightroomPyBridge.running = true
  _G.LightroomPyBridge.last_error = nil
  _G.LightroomPyBridge.started_at = os.time()
  _G.LightroomPyBridge.handler_count = 0

  LrTasks.startAsyncTask(function()
    logger:info("lightroom-py bridge starting; target=" .. base_url())

    local session_id
    local backoff = 1

    while _G.LightroomPyBridge.running do
      if not session_id then
        local sid, err = do_handshake()
        if sid then
          session_id = sid
          _G.LightroomPyBridge.session_id = sid
          backoff = 1
          logger:info("handshake ok; session=" .. sid)
        else
          _G.LightroomPyBridge.last_error = err
          logger:error(err)
          LrTasks.sleep(math.min(backoff, 30))
          backoff = backoff * 2
        end
      end

      if session_id then
        local poll_url = base_url() ..
          "/poll?token=" .. url_encode(token()) ..
          "&session_id=" .. url_encode(session_id) ..
          "&wait=" .. poll_wait()
        local body, status = http_get_with_status(poll_url, nil, poll_wait() + 5)

        if status == 204 then
          _G.LightroomPyBridge.last_poll_ok = os.time()
          -- empty queue, immediate re-poll
        elseif status == 200 and body then
          _G.LightroomPyBridge.last_poll_ok = os.time()
          local ok, cmd = pcall(json.decode, body)
          if ok and cmd and cmd.id then
            local success, result, code, message = dispatch(cmd.method, cmd.params or {})
            local payload
            if success then
              payload = { id = cmd.id, ok = true, result = result }
            else
              payload = {
                id = cmd.id,
                ok = false,
                error = { code = code or "error", message = message or "unknown" },
              }
            end
            send_response(session_id, payload)
            _G.LightroomPyBridge.handler_count = _G.LightroomPyBridge.handler_count + 1
          else
            logger:error("could not parse command body")
          end
        elseif status == 401 then
          -- session likely expired; re-handshake.
          logger:warn("poll 401; re-handshaking")
          session_id = nil
          _G.LightroomPyBridge.session_id = nil
          LrTasks.sleep(2)
        else
          _G.LightroomPyBridge.last_error = "poll status " .. tostring(status)
          logger:warn(_G.LightroomPyBridge.last_error)
          LrTasks.sleep(math.min(backoff, 30))
          backoff = math.min(backoff * 2, 30)
        end
      end
    end

    logger:info("lightroom-py bridge stopped")
    _G.LightroomPyBridge.session_id = nil
  end)

  return true
end

function M.stop()
  if not _G.LightroomPyBridge.running then
    return false, "not running"
  end
  _G.LightroomPyBridge.running = false
  return true
end

return M
