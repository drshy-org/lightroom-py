--[[
  Tiny JSON encoder/decoder.

  Minimal but correct enough for the bridge protocol envelopes we send:
    - encode: nil/null, bool, number, string, table (object or array)
    - decode: same set, with support for nested objects and arrays

  Adapted from rxi/json.lua (MIT License). Trimmed for our needs.
]]

local json = {}

-- ---------- encode ----------

local encode

local escape_char_map = {
  [ "\\" ] = "\\\\",
  [ "\"" ] = "\\\"",
  [ "\b" ] = "\\b",
  [ "\f" ] = "\\f",
  [ "\n" ] = "\\n",
  [ "\r" ] = "\\r",
  [ "\t" ] = "\\t",
}

local function escape_char(c)
  return escape_char_map[c] or string.format("\\u%04x", c:byte())
end

local function encode_nil(_) return "null" end

local function encode_string(val)
  return '"' .. val:gsub('[%z\1-\31\\"]', escape_char) .. '"'
end

local function encode_number(val)
  if val ~= val or val <= -math.huge or val >= math.huge then
    error("invalid number: " .. tostring(val))
  end
  return string.format("%.14g", val)
end

local function encode_table(val, stack)
  stack = stack or {}
  if stack[val] then error("circular reference") end
  stack[val] = true

  -- Detect array vs object.
  local n = 0
  for k, _ in pairs(val) do
    if type(k) ~= "number" then n = -1; break end
    n = math.max(n, k)
  end

  local res = {}
  if n >= 0 and n == #val then
    for i = 1, n do res[i] = encode(val[i], stack) end
    stack[val] = nil
    return "[" .. table.concat(res, ",") .. "]"
  else
    for k, v in pairs(val) do
      if type(k) ~= "string" then error("non-string key: " .. tostring(k)) end
      table.insert(res, encode_string(k) .. ":" .. encode(v, stack))
    end
    stack[val] = nil
    return "{" .. table.concat(res, ",") .. "}"
  end
end

encode = function(val, stack)
  local t = type(val)
  if val == nil then return "null" end
  if t == "string"  then return encode_string(val) end
  if t == "number"  then return encode_number(val) end
  if t == "boolean" then return tostring(val) end
  if t == "table"   then return encode_table(val, stack) end
  error("cannot encode " .. t)
end

function json.encode(val)
  return encode(val)
end

-- ---------- decode ----------

local parse

local function skip_ws(s, i)
  while i <= #s do
    local c = s:sub(i,i)
    if c ~= " " and c ~= "\t" and c ~= "\n" and c ~= "\r" then break end
    i = i + 1
  end
  return i
end

local function parse_string(s, i)
  local res = {}
  i = i + 1
  while i <= #s do
    local c = s:sub(i,i)
    if c == "\\" then
      local n = s:sub(i+1, i+1)
      if     n == "\""  then table.insert(res, "\"")
      elseif n == "\\"  then table.insert(res, "\\")
      elseif n == "/"   then table.insert(res, "/")
      elseif n == "b"   then table.insert(res, "\b")
      elseif n == "f"   then table.insert(res, "\f")
      elseif n == "n"   then table.insert(res, "\n")
      elseif n == "r"   then table.insert(res, "\r")
      elseif n == "t"   then table.insert(res, "\t")
      elseif n == "u"   then
        local hex = s:sub(i+2, i+5)
        local code = tonumber(hex, 16)
        if code and code < 128 then table.insert(res, string.char(code))
        else table.insert(res, "?") end
        i = i + 4
      else
        error("bad escape \\" .. n)
      end
      i = i + 2
    elseif c == "\"" then
      return table.concat(res), i + 1
    else
      table.insert(res, c)
      i = i + 1
    end
  end
  error("unterminated string")
end

local function parse_number(s, i)
  local j = i
  while j <= #s and s:sub(j,j):match("[%-%+%.%deE]") do j = j + 1 end
  local num = tonumber(s:sub(i, j-1))
  if not num then error("bad number at " .. i) end
  return num, j
end

local function parse_literal(s, i)
  if s:sub(i, i+3) == "true"  then return true,  i + 4 end
  if s:sub(i, i+4) == "false" then return false, i + 5 end
  if s:sub(i, i+3) == "null"  then return nil,   i + 4, true end
  error("bad literal at " .. i)
end

local function parse_array(s, i)
  local res, n = {}, 0
  i = skip_ws(s, i + 1)
  if s:sub(i,i) == "]" then return res, i + 1 end
  while true do
    local v, was_null
    v, i, was_null = parse(s, i)
    n = n + 1
    if not was_null then res[n] = v else res[n] = json.null end
    i = skip_ws(s, i)
    local c = s:sub(i,i)
    if c == "," then i = skip_ws(s, i + 1)
    elseif c == "]" then return res, i + 1
    else error("expected , or ] in array") end
  end
end

local function parse_object(s, i)
  local res = {}
  i = skip_ws(s, i + 1)
  if s:sub(i,i) == "}" then return res, i + 1 end
  while true do
    if s:sub(i,i) ~= "\"" then error("expected string key in object") end
    local key
    key, i = parse_string(s, i)
    i = skip_ws(s, i)
    if s:sub(i,i) ~= ":" then error("expected ':' after key") end
    i = skip_ws(s, i + 1)
    local v, was_null
    v, i, was_null = parse(s, i)
    if not was_null then res[key] = v else res[key] = json.null end
    i = skip_ws(s, i)
    local c = s:sub(i,i)
    if c == "," then i = skip_ws(s, i + 1)
    elseif c == "}" then return res, i + 1
    else error("expected , or } in object") end
  end
end

parse = function(s, i)
  i = skip_ws(s, i)
  local c = s:sub(i,i)
  if c == "\"" then local v; v,i = parse_string(s, i); return v, i end
  if c == "{"  then return parse_object(s, i) end
  if c == "["  then return parse_array(s, i) end
  if c == "-" or c:match("%d") then local v; v,i = parse_number(s, i); return v, i end
  if c == "t" or c == "f" or c == "n" then return parse_literal(s, i) end
  error("unexpected char '" .. c .. "' at " .. i)
end

json.null = {}  -- sentinel

function json.decode(s)
  local v = parse(s, 1)
  return v
end

return json
