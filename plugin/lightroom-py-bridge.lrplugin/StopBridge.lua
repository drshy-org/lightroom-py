--[[
  Library menu: "lightroom-py: Stop bridge"
]]

local LrDialogs = import "LrDialogs"

require "LightroomBridge"
local Runner = require "BridgeRunner"

local ok, err = Runner.stop()
if ok then
  LrDialogs.message("lightroom-py bridge", "Stopping at next poll iteration.", "info")
else
  LrDialogs.message("lightroom-py bridge", "Not running: " .. (err or ""), "info")
end
