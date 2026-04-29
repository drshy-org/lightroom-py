--[[
  lightroom-py-bridge — Info.lua

  Tiny Lightroom Classic plugin that polls a local Python HTTP server for
  commands and POSTs results back. Owns no domain logic — all command shapes,
  validation, and orchestration live in Python.
]]

return {
  LrSdkVersion = 10.0,
  LrSdkMinimumVersion = 6.0,

  LrToolkitIdentifier = "com.henryshen.lightroom-py-bridge",
  LrPluginName = "lightroom-py bridge",
  VERSION = { major = 0, minor = 2, revision = 0, build = 0 },

  LrPluginInfoUrl = "https://github.com/henryshen/lightroom-py",

  LrInitPlugin = "LightroomBridge.lua",

  LrLibraryMenuItems = {
    {
      title = "lightroom-py: Start bridge",
      file  = "StartBridge.lua",
    },
    {
      title = "lightroom-py: Stop bridge",
      file  = "StopBridge.lua",
    },
    {
      title = "lightroom-py: Status",
      file  = "Status.lua",
    },
    {
      title = "lightroom-py: Configure...",
      file  = "Configure.lua",
    },
  },
}
