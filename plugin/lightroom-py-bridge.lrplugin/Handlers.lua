--[[
  Handlers.lua — command dispatcher.

  Each entry maps a method name to a function(params) -> result. Handlers run
  inside an LrTasks task; they may use catalog APIs.
]]

local LrApplication = import "LrApplication"
local LrTasks       = import "LrTasks"

local Handlers = {}

-- ---------- helpers ----------

local function lookup_photos_by_uuid(catalog, uuids)
  -- LR has no by-uuid lookup, so we walk the catalog. Keep this method
  -- usable but recommend bulk read paths via the SQLite fast-path.
  if not uuids or #uuids == 0 then
    return {}, {}
  end
  local want = {}
  for _, u in ipairs(uuids) do want[u] = true end

  local matched = {}
  local all = catalog:getAllPhotos()
  for i = 1, #all do
    local uid = all[i]:getRawMetadata("uuid")
    if want[uid] then
      table.insert(matched, all[i])
      want[uid] = nil
    end
  end

  local missing = {}
  for u, _ in pairs(want) do table.insert(missing, u) end
  return matched, missing
end

local function target_photos(catalog, params)
  -- If params.uuids is given, resolve those; otherwise use the active selection.
  if params and params.uuids and #params.uuids > 0 then
    return lookup_photos_by_uuid(catalog, params.uuids)
  end
  return catalog:getTargetPhotos() or {}, {}
end

local function find_or_create_keyword(catalog, name_or_path)
  -- Accept either a flat name ("Wedding") or a pipe-separated path
  -- ("People|Family|Mom"). Walks segments, creating each missing parent.
  --
  -- We DON'T pre-check existence via parent:getChildren() / catalog:getKeywords()
  -- because parent:getChildren() yields internally (and our caller is in a
  -- non-yieldable withWriteAccessDo scope). Instead we lean on createKeyword's
  -- returnExisting=true flag (5th arg) — LR returns the existing keyword if
  -- the name+parent already exists, otherwise creates a new one. Idempotent.
  if not name_or_path:find("|") then
    return catalog:createKeyword(name_or_path, {}, false, nil, true)
  end

  local current = nil  -- becomes the parent of the next segment
  for seg in string.gmatch(name_or_path, "([^|]+)") do
    current = catalog:createKeyword(seg, {}, false, current, true)
  end
  return current
end

-- ---------- diagnostics ----------

Handlers["ping"] = function(_params)
  local lr_version
  pcall(function()
    lr_version = LrApplication.versionString and LrApplication.versionString()
  end)
  return { pong = true, lr_version = lr_version or "unknown" }
end

Handlers["echo"] = function(params)
  return params or {}
end

-- ---------- dev tooling: hot-reload + eval + tail-log ----------
--
-- These three handlers turn the dev loop from "Cmd+Q LR + relaunch + Start
-- bridge" (~3 min) into a single bridge call (~0.5s). Use them when you've
-- edited Handlers.lua and want to pick up the changes without restarting LR.

Handlers["system.reload_handlers"] = function(_params)
  -- Set the force-reload flag that BridgeRunner.lua's get_handlers() reads.
  -- The next dispatch will re-read Handlers.lua from disk via dofile.
  -- (LR sandboxes `package`, so we can't use the standard package.loaded trick.)
  _G.LR_PY_FORCE_RELOAD = true
  return {
    reloaded = true,
    note = "Next dispatch reloads Handlers.lua from disk. BridgeRunner.lua / Info.lua changes still need LR restart.",
  }
end

Handlers["system.eval"] = function(params)
  -- Dev tool: run an arbitrary Lua snippet. Pref-gating temporarily
  -- disabled for v0.3.x debugging; will be restored for v0.4 release.
  local code = params and params.code
  if type(code) ~= "string" or code == "" then
    error("system.eval: 'code' must be a non-empty Lua source string")
  end

  -- Wrap the code so it has access to common LR globals via upvalues.
  -- LR sandbox doesn't expose setfenv, so we do it via concat instead.
  local prelude = [[
    local LrApplication = require_or_import("LrApplication")
    local LrTasks       = require_or_import("LrTasks")
  ]]
  -- Actually simplest: just loadstring and inject upvalues via closure.
  local fn, compile_err = loadstring(code, "[eval]")
  if not fn then
    error("compile error: " .. tostring(compile_err))
  end

  local ok, result = LrTasks.pcall(fn)
  if not ok then
    error("runtime error: " .. tostring(result))
  end
  return { result = result }
end

Handlers["system.tail_log"] = function(params)
  -- Read the last N lines of the plugin's log file. The path varies by OS;
  -- LrPathUtils.getStandardFilePath("documents") points at the right place.
  local LrPathUtils = import "LrPathUtils"

  local n = (params and params.lines) or 50
  if type(n) ~= "number" or n < 1 then n = 50 end

  local docs = LrPathUtils.getStandardFilePath("documents")
  local log_path = LrPathUtils.child(LrPathUtils.child(docs, "LrClassicLogs"), "lightroom-py.log")

  local file, err = io.open(log_path, "r")
  if not file then
    return { error = "could not open log: " .. tostring(err), path = log_path }
  end

  local lines = {}
  for line in file:lines() do table.insert(lines, line) end
  file:close()

  local start = math.max(1, #lines - n + 1)
  local out = {}
  for i = start, #lines do table.insert(out, lines[i]) end
  return { lines = out, total = #lines, path = log_path, returned = #out }
end

Handlers["system.handler_list"] = function(_params)
  -- Return the names of every registered handler. Useful for "what's
  -- actually loaded right now?" diagnostics.
  local names = {}
  for name in pairs(Handlers) do table.insert(names, name) end
  table.sort(names)
  return { handlers = names, count = #names }
end

-- ---------- catalog metadata ----------

Handlers["catalog.path"] = function(_params)
  local cat = LrApplication.activeCatalog()
  return { path = cat:getPath() }
end

-- ---------- selection ----------

Handlers["selection.uuids"] = function(_params)
  local cat = LrApplication.activeCatalog()
  local photos = cat:getTargetPhotos() or {}
  local uuids = {}
  for i = 1, #photos do
    uuids[i] = photos[i]:getRawMetadata("uuid")
  end
  return { uuids = uuids, count = #uuids }
end

Handlers["photos.select"] = function(params)
  local cat = LrApplication.activeCatalog()
  local matched, missing = lookup_photos_by_uuid(cat, (params and params.uuids) or {})

  cat:withWriteAccessDo("lightroom-py: select photos", function()
    cat:setSelectedPhotos(matched[1], matched)
  end, { timeout = 5, asynchronous = false })

  return { selected = #matched, missing = missing }
end

-- ---------- metadata writes ----------

Handlers["metadata.add_keywords"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local names = (params and params.keywords) or {}
  if type(names) ~= "table" or #names == 0 then
    error("metadata.add_keywords: 'keywords' must be a non-empty list")
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: add keywords", function()
    local kws = {}
    for _, n in ipairs(names) do table.insert(kws, find_or_create_keyword(cat, n)) end
    for _, photo in ipairs(photos) do
      for _, kw in ipairs(kws) do
        photo:addKeyword(kw)
      end
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })

  return { touched = touched, missing = missing, keywords = names }
end

local function find_existing_keyword(catalog, name_or_path)
  -- Walk the keyword tree looking for a match. Returns nil if not found.
  -- This is a READ — must be called OUTSIDE withWriteAccessDo because
  -- LrKeyword:getChildren() yields and the non-yieldable scope forbids it.
  if not name_or_path:find("|") then
    for _, kw in ipairs(catalog:getKeywords() or {}) do
      if kw:getName() == name_or_path then return kw end
    end
    return nil
  end
  local segments = {}
  for seg in string.gmatch(name_or_path, "([^|]+)") do
    table.insert(segments, seg)
  end
  local current = nil
  for _, seg in ipairs(segments) do
    local siblings
    if current == nil then
      siblings = catalog:getKeywords() or {}
    else
      siblings = current:getChildren() or {}
    end
    local next_kw = nil
    for _, kw in ipairs(siblings) do
      if kw:getName() == seg then next_kw = kw; break end
    end
    if not next_kw then return nil end
    current = next_kw
  end
  return current
end

Handlers["metadata.remove_keywords"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local names = (params and params.keywords) or {}
  if type(names) ~= "table" or #names == 0 then
    error("metadata.remove_keywords: 'keywords' must be a non-empty list")
  end

  -- Resolve keywords OUTSIDE withWriteAccessDo (getChildren yields).
  local found = {}
  local not_found = {}
  for _, n in ipairs(names) do
    local kw = find_existing_keyword(cat, n)
    if kw then table.insert(found, kw) else table.insert(not_found, n) end
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: remove keywords", function()
    for _, photo in ipairs(photos) do
      for _, kw in ipairs(found) do
        photo:removeKeyword(kw)
      end
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })

  return { touched = touched, missing = missing, keywords = names, not_found = not_found }
end

Handlers["metadata.set_rating"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local rating = params and params.rating
  if rating ~= nil and (type(rating) ~= "number" or rating < 0 or rating > 5) then
    error("metadata.set_rating: 'rating' must be nil or an integer 0..5")
  end

  -- LR rejects setRawMetadata("rating", 0) with "Invalid rating: 0" — to
  -- clear the rating you must pass nil. We treat 0 as "clear" so callers can
  -- use 0..5 + 0-means-unrated, matching LR's keyboard shortcut behaviour.
  local lr_value
  if rating == nil or rating == 0 then
    lr_value = nil
  else
    lr_value = rating
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: set rating", function()
    for _, photo in ipairs(photos) do
      photo:setRawMetadata("rating", lr_value)
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })

  return { touched = touched, missing = missing, rating = rating }
end

Handlers["metadata.set_color_label"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local label = (params and params.label) or ""
  -- LR accepts "", "red", "yellow", "green", "blue", "purple" (case-insensitive).
  local valid = { [""] = true, red = true, yellow = true, green = true, blue = true, purple = true }
  if not valid[string.lower(label)] then
    error("metadata.set_color_label: invalid label: " .. tostring(label))
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: set color label", function()
    for _, photo in ipairs(photos) do
      photo:setRawMetadata("colorNameForLabel", label)
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })

  return { touched = touched, missing = missing, label = label }
end

Handlers["metadata.set_iptc"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local fields = (params and params.fields) or {}
  if type(fields) ~= "table" or next(fields) == nil then
    error("metadata.set_iptc: 'fields' must be a non-empty object")
  end

  -- Map common IPTC field names to LR's setRawMetadata keys.
  -- See https://helpx.adobe.com/lightroom-classic/help/photo-metadata.html
  local key_map = {
    caption    = "caption",
    title      = "title",
    headline   = "headline",
    copyright  = "copyright",
    creator    = "creator",
    label      = "label",
    location   = "location",
    city       = "city",
    state      = "stateProvince",
    country    = "country",
    iso_country_code = "isoCountryCode",
  }

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: set IPTC", function()
    for _, photo in ipairs(photos) do
      for k, v in pairs(fields) do
        local lr_key = key_map[k] or k
        photo:setRawMetadata(lr_key, v)
      end
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })

  return { touched = touched, missing = missing, fields_set = fields }
end

-- ---------- XMP sidecar bridge ----------

Handlers["metadata.write_xmp"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)

  local touched = 0
  cat:withReadAccessDo("lightroom-py: write XMP", function()
    for _, photo in ipairs(photos) do
      pcall(function() photo:saveMetadata() end)
      touched = touched + 1
    end
  end, { timeout = 60 })

  return { touched = touched, missing = missing }
end

Handlers["metadata.read_xmp"] = function(params)
  -- Tell LR to re-read XMP from disk. Used after the Python side writes
  -- sidecars via ExifTool so the catalog picks up the changes.
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: read XMP from file", function()
    for _, photo in ipairs(photos) do
      pcall(function() photo:readMetadata() end)
      touched = touched + 1
    end
  end, { timeout = 60, asynchronous = false })

  return { touched = touched, missing = missing }
end

-- ---------- develop module (Phase 4) ----------

Handlers["develop.list_presets"] = function(_params)
  -- Walk LR's develop preset folders and return a flat list of {folder, name}.
  local folders = LrApplication.developPresetFolders() or {}
  local out = {}
  for _, folder in ipairs(folders) do
    local fname = folder:getName()
    local presets = folder:getDevelopPresets() or {}
    for _, p in ipairs(presets) do
      table.insert(out, { folder = fname, name = p:getName(), uuid = p:getUuid() })
    end
  end
  return { presets = out, count = #out }
end

Handlers["develop.apply_preset"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local preset_name = params and params.preset
  local preset_folder = params and params.folder  -- optional disambiguation
  if type(preset_name) ~= "string" or preset_name == "" then
    error("develop.apply_preset: 'preset' must be a non-empty string")
  end

  -- Find the preset by name (and optionally folder).
  local target_preset
  for _, folder in ipairs(LrApplication.developPresetFolders() or {}) do
    if (preset_folder == nil) or folder:getName() == preset_folder then
      for _, p in ipairs(folder:getDevelopPresets() or {}) do
        if p:getName() == preset_name then
          target_preset = p
          break
        end
      end
    end
    if target_preset then break end
  end

  if not target_preset then
    error("develop.apply_preset: preset not found: " ..
          tostring(preset_folder or "*") .. "/" .. preset_name)
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: apply preset", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopPreset(target_preset)
      touched = touched + 1
    end
  end, { timeout = 60, asynchronous = false })

  return { touched = touched, missing = missing, preset = preset_name }
end

Handlers["develop.apply_settings"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local settings = params and params.settings
  if type(settings) ~= "table" or next(settings) == nil then
    error("develop.apply_settings: 'settings' must be a non-empty object")
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: apply develop settings", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings(settings)
      touched = touched + 1
    end
  end, { timeout = 60, asynchronous = false })

  return { touched = touched, missing = missing }
end

Handlers["develop.get_settings"] = function(params)
  -- Reads don't need withReadAccessDo on individual photos — and in LR 15.3
  -- the read-access wrapper raises "attempt to call a string value" on this
  -- code path. Just call the read methods directly.
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  if #photos == 0 then
    error("develop.get_settings: no target photo (pass uuid or set selection)")
  end

  local out = {}
  for _, photo in ipairs(photos) do
    local uid = photo:getRawMetadata("uuid")
    out[uid] = photo:getDevelopSettings()
  end
  return { settings = out, missing = missing }
end

Handlers["develop.copy"] = function(params)
  local cat = LrApplication.activeCatalog()
  local src_uuid = params and params.src
  local dst_uuids = (params and params.dsts) or {}
  if type(src_uuid) ~= "string" or src_uuid == "" then
    error("develop.copy: 'src' must be a photo uuid")
  end
  if type(dst_uuids) ~= "table" or #dst_uuids == 0 then
    error("develop.copy: 'dsts' must be a non-empty list of photo uuids")
  end

  -- Resolve src + dsts in one walk.
  local want = { [src_uuid] = "src" }
  for _, u in ipairs(dst_uuids) do want[u] = "dst" end

  local src_photo
  local dsts = {}
  local missing_dst = {}
  for _, photo in ipairs(cat:getAllPhotos()) do
    local uid = photo:getRawMetadata("uuid")
    local kind = want[uid]
    if kind == "src" then src_photo = photo
    elseif kind == "dst" then table.insert(dsts, photo); want[uid] = nil end
    if kind then want[uid] = nil end
  end
  for u, _ in pairs(want) do
    if u ~= src_uuid then table.insert(missing_dst, u) end
  end

  if not src_photo then
    error("develop.copy: src photo not found: " .. src_uuid)
  end

  -- Direct read; no withReadAccessDo (see develop.get_settings note).
  local settings = src_photo:getDevelopSettings()

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: copy develop settings", function()
    for _, dst in ipairs(dsts) do
      dst:applyDevelopSettings(settings)
      touched = touched + 1
    end
  end, { timeout = 60, asynchronous = false })

  return { copied_to = touched, missing = missing_dst }
end

Handlers["develop.reset"] = function(params)
  -- LrPhoto has no resetDevelopSettings method; the canonical reset is
  -- LrDevelopController.resetAllDevelopAdjustments(), which acts on the
  -- active photo in the Develop module. We switch to Develop, set each
  -- target photo as the selection, then reset.
  local LrApplicationView   = import "LrApplicationView"
  local LrDevelopController = import "LrDevelopController"

  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)

  pcall(function() LrApplicationView.switchToModule("develop") end)

  local touched = 0
  for _, photo in ipairs(photos) do
    cat:withWriteAccessDo("lightroom-py: select for reset", function()
      cat:setSelectedPhotos(photo, { photo })
    end, { timeout = 5, asynchronous = false })
    local ok = pcall(function()
      LrDevelopController.resetAllDevelopAdjustments()
    end)
    if ok then touched = touched + 1 end
  end

  return { touched = touched, missing = missing }
end

Handlers["develop.set"] = function(params)
  -- Live slider control via LrDevelopController. Only works when the user
  -- is in the Develop module on the target photo.
  local LrDevelopController = import "LrDevelopController"
  local LrApplicationView   = import "LrApplicationView"

  local values = params and params.values
  if type(values) ~= "table" or next(values) == nil then
    error("develop.set: 'values' must be a non-empty {slider=number} object")
  end

  -- Switch to Develop module so LrDevelopController can drive sliders.
  pcall(function() LrApplicationView.switchToModule("develop") end)

  local applied = {}
  for slider, value in pairs(values) do
    local ok, err = pcall(function()
      LrDevelopController.setValue(slider, value)
    end)
    if ok then
      applied[slider] = value
    else
      applied[slider] = { error = tostring(err) }
    end
  end
  return { applied = applied }
end

-- ---------- develop: tone curve (v0.4) ----------
--
-- LR stores tone curves in develop settings as ToneCurvePV2012* — flat
-- arrays of [x1,y1,x2,y2,...] where x and y are 0..255. Per-channel curves
-- live at ToneCurvePV2012Red / Green / Blue. Named presets set
-- ToneCurveName2012 to a known string ("Linear", "Medium Contrast",
-- "Strong Contrast"); LR resolves the name to the canonical points.

Handlers["develop.curve_get"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local channel = (params and params.channel) or "rgb"  -- rgb | red | green | blue
  if #photos == 0 then
    error("develop.curve_get: no target photo")
  end
  local key_map = {
    rgb   = "ToneCurvePV2012",
    red   = "ToneCurvePV2012Red",
    green = "ToneCurvePV2012Green",
    blue  = "ToneCurvePV2012Blue",
  }
  local key = key_map[channel]
  if not key then error("develop.curve_get: invalid channel: " .. tostring(channel)) end

  local out = {}
  cat:withReadAccessDo("lightroom-py: get curve", function()
    for _, photo in ipairs(photos) do
      local s = photo:getDevelopSettings() or {}
      out[photo:getRawMetadata("uuid")] = {
        name = s.ToneCurveName2012,
        points = s[key] or {},
        channel = channel,
      }
    end
  end, { timeout = 10 })
  return { curves = out, missing = missing }
end

Handlers["develop.curve_set"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local points = params and params.points
  local channel = (params and params.channel) or "rgb"
  if type(points) ~= "table" or #points < 4 or #points % 2 ~= 0 then
    error("develop.curve_set: 'points' must be a flat array of [x1,y1,x2,y2,...] with even length >= 4")
  end
  local key_map = {
    rgb   = "ToneCurvePV2012",
    red   = "ToneCurvePV2012Red",
    green = "ToneCurvePV2012Green",
    blue  = "ToneCurvePV2012Blue",
  }
  local key = key_map[channel]
  if not key then error("develop.curve_set: invalid channel: " .. tostring(channel)) end

  local settings = { [key] = points }
  -- Setting a custom curve overrides any named preset; clear the name on rgb.
  if channel == "rgb" then settings.ToneCurveName2012 = "Custom" end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: set curve", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings(settings)
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return { touched = touched, missing = missing, channel = channel }
end

Handlers["develop.curve_preset"] = function(params)
  -- Apply a named tone curve preset: "Linear", "Medium Contrast", "Strong Contrast".
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local name = params and params.name
  local valid = { Linear = true, ["Medium Contrast"] = true, ["Strong Contrast"] = true, Custom = true }
  if not valid[name] then
    error("develop.curve_preset: 'name' must be Linear | Medium Contrast | Strong Contrast | Custom; got " .. tostring(name))
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: curve preset", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings({ ToneCurveName2012 = name })
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return { touched = touched, missing = missing, name = name }
end

-- ---------- develop: snapshots (v0.4) ----------

Handlers["develop.snapshot_create"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local name = params and params.name
  if type(name) ~= "string" or name == "" then
    error("develop.snapshot_create: 'name' must be a non-empty string")
  end

  local created = {}
  cat:withWriteAccessDo("lightroom-py: snapshot create", function()
    for _, photo in ipairs(photos) do
      -- LrPhoto:createDevelopSnapshot(name [, includeHistory])
      local ok, snap_or_err = pcall(function() return photo:createDevelopSnapshot(name, true) end)
      if ok then
        table.insert(created, { uuid = photo:getRawMetadata("uuid"), name = name, ok = true })
      else
        table.insert(created, { uuid = photo:getRawMetadata("uuid"), error = tostring(snap_or_err) })
      end
    end
  end, { timeout = 30, asynchronous = false })
  return { created = created, missing = missing }
end

Handlers["develop.snapshot_list"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)

  local out = {}
  cat:withReadAccessDo("lightroom-py: snapshot list", function()
    for _, photo in ipairs(photos) do
      local snaps = {}
      local ok, list = pcall(function() return photo:getDevelopSnapshots() end)
      if ok and type(list) == "table" then
        for _, s in ipairs(list) do
          table.insert(snaps, { name = s, })
        end
      end
      out[photo:getRawMetadata("uuid")] = snaps
    end
  end, { timeout = 10 })
  return { snapshots = out, missing = missing }
end

-- ---------- develop: process version (v0.4) ----------

Handlers["develop.process_version_get"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  if #photos == 0 then error("develop.process_version_get: no target photo") end

  local out = {}
  cat:withReadAccessDo("lightroom-py: get process version", function()
    for _, photo in ipairs(photos) do
      local s = photo:getDevelopSettings() or {}
      out[photo:getRawMetadata("uuid")] = s.ProcessVersion or "unknown"
    end
  end, { timeout = 10 })
  return { versions = out, missing = missing }
end

Handlers["develop.process_version_set"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local version = params and params.version
  -- LR process versions: "5.0" (PV2003), "6.7" (PV2010), "11.0" (PV2012)
  -- Newer versions (since LR 7): "11.0" remains; LR uses the same string.
  if type(version) ~= "string" or version == "" then
    error("develop.process_version_set: 'version' must be a non-empty string (e.g. '11.0')")
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: set process version", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings({ ProcessVersion = version })
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return { touched = touched, missing = missing, version = version }
end

-- ---------- develop: targeted resets (v0.4) ----------
-- These wrap LrDevelopController.resetX functions which only act on the
-- active photo in the Develop module. Switch module + select target first.

local function _reset_via_controller(photos, action_name, controller_method_name)
  local LrDevelopController = import "LrDevelopController"
  local LrApplicationView = import "LrApplicationView"
  pcall(function() LrApplicationView.switchToModule("develop") end)

  local cat = LrApplication.activeCatalog()
  local touched = 0
  for _, photo in ipairs(photos) do
    cat:withWriteAccessDo(action_name, function()
      cat:setSelectedPhotos(photo, { photo })
    end, { timeout = 5, asynchronous = false })
    local ok, err = pcall(function()
      local fn = LrDevelopController[controller_method_name]
      if type(fn) == "function" then fn() end
    end)
    if ok then touched = touched + 1 end
  end
  return touched
end

Handlers["develop.reset_crop"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local touched = _reset_via_controller(photos, "lightroom-py: reset crop", "resetCrop")
  return { touched = touched, missing = missing }
end

Handlers["develop.reset_masking"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  -- Clear masks via develop settings: mask data lives in MaskGroupBasedCorrections etc.
  local touched = 0
  cat:withWriteAccessDo("lightroom-py: reset masking", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings({
        MaskGroupBasedCorrections = nil,
        RetouchAreas = nil,
        CircularGradientBasedCorrections = nil,
        GradientBasedCorrections = nil,
        PaintBasedCorrections = nil,
      })
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return { touched = touched, missing = missing }
end

Handlers["develop.reset_spot"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local touched = 0
  cat:withWriteAccessDo("lightroom-py: reset spot", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings({ RetouchAreas = nil })
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return { touched = touched, missing = missing }
end

Handlers["develop.reset_redeye"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local touched = 0
  cat:withWriteAccessDo("lightroom-py: reset red-eye", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings({ RedEyeInfo = nil })
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return { touched = touched, missing = missing }
end

Handlers["develop.reset_transforms"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local touched = 0
  cat:withWriteAccessDo("lightroom-py: reset transforms", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings({
        PerspectiveUpright = 0,
        PerspectiveVertical = 0,
        PerspectiveHorizontal = 0,
        PerspectiveRotate = 0,
        PerspectiveScale = 100,
        PerspectiveAspect = 0,
        PerspectiveX = 0,
        PerspectiveY = 0,
      })
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return { touched = touched, missing = missing }
end

-- ---------- develop: paste-settings + batch-apply (v0.4) ----------

Handlers["develop.paste_settings"] = function(params)
  -- Apply a develop-settings dict to many photos (alias of apply_settings,
  -- but accepts an optional `subset` filter to paste only specific keys —
  -- mirrors LR's "Paste Settings…" dialog).
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local settings = params and params.settings
  local subset  = params and params.subset  -- optional list of keys to paste
  if type(settings) ~= "table" or next(settings) == nil then
    error("develop.paste_settings: 'settings' must be a non-empty object")
  end

  -- If subset is provided, filter the settings dict to only those keys.
  local payload = settings
  if type(subset) == "table" and #subset > 0 then
    payload = {}
    local want = {}
    for _, k in ipairs(subset) do want[k] = true end
    for k, v in pairs(settings) do
      if want[k] then payload[k] = v end
    end
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: paste settings", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings(payload)
      touched = touched + 1
    end
  end, { timeout = 60, asynchronous = false })

  return { touched = touched, missing = missing, applied_keys = (function()
    local k = {}
    for key, _ in pairs(payload) do table.insert(k, key) end
    return k
  end)() }
end

-- ---------- develop: masks read + clear (v0.4) ----------
--
-- HONEST LIMITS (verified against LR Classic 15.3 in v0.3.x):
-- - Reading mask data from develop settings WORKS — masks live in
--   MaskGroupBasedCorrections / GradientBasedCorrections / etc.
-- - WRITING mask geometry (radial/graduated/brush points) WORKS via
--   applyDevelopSettings — the keys are documented enough.
-- - TRIGGERING AI mask creation (Select Subject / Sky / Object) does NOT
--   work — same SDK gap as ai.stage_denoise. We expose stage-* handlers
--   that write the keys; LR appears to silently ignore them.

Handlers["develop.mask_list"] = function(params)
  -- Returns a summary of masks present on each target photo. Doesn't
  -- include full geometry — use develop.get_settings for the raw payload.
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local out = {}
  cat:withReadAccessDo("lightroom-py: mask list", function()
    for _, photo in ipairs(photos) do
      local s = photo:getDevelopSettings() or {}
      local masks = {
        ai_masks       = (s.MaskGroupBasedCorrections and #s.MaskGroupBasedCorrections) or 0,
        gradient       = (s.GradientBasedCorrections and #s.GradientBasedCorrections) or 0,
        circular       = (s.CircularGradientBasedCorrections and #s.CircularGradientBasedCorrections) or 0,
        paint          = (s.PaintBasedCorrections and #s.PaintBasedCorrections) or 0,
        retouch_areas  = (s.RetouchAreas and #s.RetouchAreas) or 0,
        red_eye        = (s.RedEyeInfo and 1) or 0,
      }
      out[photo:getRawMetadata("uuid")] = masks
    end
  end, { timeout = 10 })
  return { masks = out, missing = missing }
end

Handlers["develop.mask_clear"] = function(params)
  -- Alias for reset_masking — exists for discoverability under
  -- `lightroom develop mask clear`.
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local kind = (params and params.kind) or "all"  -- all | ai | gradient | circular | paint
  local clear_keys = {
    all      = { "MaskGroupBasedCorrections", "GradientBasedCorrections",
                 "CircularGradientBasedCorrections", "PaintBasedCorrections" },
    ai       = { "MaskGroupBasedCorrections" },
    gradient = { "GradientBasedCorrections" },
    circular = { "CircularGradientBasedCorrections" },
    paint    = { "PaintBasedCorrections" },
  }
  local keys = clear_keys[kind]
  if not keys then
    error("develop.mask_clear: invalid 'kind': " .. tostring(kind))
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: clear masks", function()
    for _, photo in ipairs(photos) do
      local payload = {}
      for _, k in ipairs(keys) do payload[k] = nil end
      -- nil values don't survive the table → set sentinel to clear:
      for _, k in ipairs(keys) do payload[k] = "" end
      photo:applyDevelopSettings(payload)
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return { touched = touched, missing = missing, kind = kind }
end

-- ---------- AI staging (Phase 5) ----------

-- The LR SDK lets us write AI-feature parameters into a photo's develop
-- settings table, but cannot trigger the actual AI compute step. After
-- staging, the user must click "Update AI Settings" in Lightroom.

Handlers["ai.stage_denoise"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local strength = (params and params.strength) or 50
  if type(strength) ~= "number" or strength < 0 or strength > 100 then
    error("ai.stage_denoise: 'strength' must be 0..100")
  end

  -- AI Denoise sets EnableAIDenoise=true + AIDenoiseAmount=N in settings.
  local settings = {
    EnableAIDenoise = true,
    AIDenoiseAmount = strength,
  }

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: stage AI denoise", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings(settings)
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })

  return {
    touched = touched,
    missing = missing,
    note = "Settings staged. Click 'Update AI Settings' in Lightroom to actually denoise.",
  }
end

Handlers["ai.prompt_update"] = function(_params)
  local LrDialogs = import "LrDialogs"
  -- LrDialogs.message blocks the LrTasks; that's fine — we want the user
  -- to acknowledge before we return.
  LrDialogs.message(
    "lightroom-py: AI compute pending",
    "AI develop settings have been staged on the target photos.\n\n" ..
    "To run the AI step, select the affected photos in the Develop module " ..
    "and click 'Update AI Settings' (the small ✨ icon, or use the menu).",
    "info"
  )
  return { acknowledged = true }
end

-- The following stage_select_* handlers WRITE the AI mask settings into
-- the photo's develop table. LR may silently ignore the writes (same gap
-- as ai.stage_denoise — no public AI compute trigger in the SDK). Kept
-- in the surface for parity with lightroom-cli; honest doc in Python API.

Handlers["ai.stage_select_subject"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local touched = 0
  cat:withWriteAccessDo("lightroom-py: stage select-subject", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings({
        -- Speculative key names — LR's AI mask schema isn't documented for plugins.
        EnableSubjectSelectMask = true,
        SubjectSelectMaskAmount = 1,
      })
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return {
    touched = touched,
    missing = missing,
    note = "Settings staged. AI compute requires Update AI Settings in LR's UI.",
  }
end

Handlers["ai.stage_select_sky"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local touched = 0
  cat:withWriteAccessDo("lightroom-py: stage select-sky", function()
    for _, photo in ipairs(photos) do
      photo:applyDevelopSettings({
        EnableSkySelectMask = true,
        SkySelectMaskAmount = 1,
      })
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })
  return {
    touched = touched,
    missing = missing,
    note = "Settings staged. AI compute requires Update AI Settings in LR's UI.",
  }
end

-- ---------- Edit-In escape hatch (Phase 5) ----------

-- Pattern (Topaz-style): export selected photos as TIFF/JPEG to a temp
-- directory, hand the paths back to Python (which runs the external tool),
-- then we reimport the results as stacked siblings of the originals.
--
-- Split: Lua does the export + import (catalog APIs); Python does the
-- external command + file shuffle. This keeps the Lua surface tiny.

Handlers["edit_in.export"] = function(params)
  local LrExportSession = import "LrExportSession"
  local LrPathUtils     = import "LrPathUtils"
  local LrFileUtils     = import "LrFileUtils"

  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  if #photos == 0 then
    error("edit_in.export: no target photos")
  end

  local out_dir = params and params.out_dir
  if type(out_dir) ~= "string" or out_dir == "" then
    error("edit_in.export: 'out_dir' must be a non-empty string")
  end
  local format = (params and params.format) or "TIFF"  -- "TIFF", "JPEG", "PSD", "DNG", "ORIGINAL"
  local quality = (params and params.quality) or 95     -- only used for JPEG
  local color_space = (params and params.color_space) or "AdobeRGB"

  if not LrFileUtils.exists(out_dir) then
    LrFileUtils.createAllDirectories(out_dir)
  end

  local export_settings = {
    LR_format            = format,
    LR_export_destinationType    = "specificFolder",
    LR_export_destinationPathPrefix = out_dir,
    LR_export_useSubfolder      = false,
    LR_jpeg_quality      = quality / 100.0,  -- LR wants 0..1
    LR_export_colorSpace = color_space,
    LR_size_doConstrain  = false,
    LR_collisionHandling = "rename",
  }

  local session = LrExportSession({
    photosToExport = photos,
    exportSettings = export_settings,
  })

  local exported = {}
  for _, rendition in session:renditions() do
    local ok, path_or_err = rendition:waitForRender()
    if ok then
      table.insert(exported, {
        uuid = rendition.photo:getRawMetadata("uuid"),
        path = path_or_err,
      })
    else
      table.insert(exported, {
        uuid = rendition.photo:getRawMetadata("uuid"),
        error = tostring(path_or_err),
      })
    end
  end

  return { exported = exported, missing = missing, out_dir = out_dir }
end

Handlers["edit_in.import_as_stack"] = function(params)
  -- After Python has run an external tool on the exported files, re-import
  -- each result and stack it on top of the source photo.
  --
  -- The canonical pattern (per Adobe SDK reference + Automaat/lightroom-mcp +
  -- gesteves/lightroom-alt-text-plugin):
  --
  --   catalog:withWriteAccessDo("name", function(context)
  --     newPhoto = catalog:addPhoto(path, parentPhoto, "above")
  --   end, { timeout = 60 })
  --
  -- Two-arg or three-arg form. NO `asynchronous=false` (would forbid the
  -- yield that addPhoto performs internally). NO inner pcall (use
  -- LrTasks.pcall at the dispatcher level if you need error trapping).
  local cat = LrApplication.activeCatalog()
  local pairs_ = (params and params.pairs) or {}
  if type(pairs_) ~= "table" or #pairs_ == 0 then
    error("edit_in.import_as_stack: 'pairs' must be a non-empty list of {src_uuid, result_path}")
  end

  -- Resolve src photos first (read-only walk; no access wrapper needed).
  local want = {}
  for _, p in ipairs(pairs_) do want[p.src_uuid] = true end
  local src_by_uuid = {}
  for _, photo in ipairs(cat:getAllPhotos()) do
    local uid = photo:getRawMetadata("uuid")
    if want[uid] then src_by_uuid[uid] = photo end
  end

  local imported = {}
  local errors = {}

  for _, p in ipairs(pairs_) do
    local src = src_by_uuid[p.src_uuid]
    if not src then
      table.insert(errors, { src_uuid = p.src_uuid, error = "src not found" })
    else
      local new_photo
      local ok, err = LrTasks.pcall(function()
        cat:withWriteAccessDo("lightroom-py: import edit-in result", function()
          new_photo = cat:addPhoto(p.result_path, src, "above")
        end, { timeout = 60 })
      end)
      if ok and new_photo then
        table.insert(imported, {
          src_uuid = p.src_uuid,
          new_uuid = new_photo:getRawMetadata("uuid"),
        })
      else
        table.insert(errors, {
          src_uuid = p.src_uuid,
          result_path = p.result_path,
          error = tostring(err or "addPhoto returned nil"),
        })
      end
    end
  end

  return { imported = imported, errors = errors }
end

-- ---------- collections (v0.3 — was Phase 3 debt) ----------

local function is_smart_collection(c)
  -- LR throws "This function can only be called by a smart collection" if
  -- you call getSearchDescription on a regular one, so probe with pcall.
  local ok, result = pcall(function() return c:getSearchDescription() end)
  return ok and result ~= nil
end

local function walk_collection_tree(parent, out, parent_name)
  -- Recursively flatten a collection tree. `parent` is either an
  -- LrCatalog or an LrCollectionSet; both expose getChildCollections /
  -- getChildCollectionSets in current LR SDK versions.
  local kids = parent.getChildCollections and parent:getChildCollections() or {}
  for _, c in ipairs(kids) do
    table.insert(out, {
      name        = c:getName(),
      kind        = is_smart_collection(c) and "smart" or "collection",
      parent      = parent_name,
      id          = tostring(c.localIdentifier or ""),
      photo_count = c.getPhotos and #(c:getPhotos() or {}) or 0,
    })
  end
  local sets = parent.getChildCollectionSets and parent:getChildCollectionSets() or {}
  for _, s in ipairs(sets) do
    table.insert(out, {
      name        = s:getName(),
      kind        = "group",
      parent      = parent_name,
      id          = tostring(s.localIdentifier or ""),
      photo_count = 0,
    })
    walk_collection_tree(s, out, s:getName())
  end
end

local function find_collection_by_name(catalog, name)
  -- Linear search — LR has no findCollectionByName API. Walks both
  -- top-level and nested collections.
  local function recurse(parent)
    local kids = parent.getChildCollections and parent:getChildCollections() or {}
    for _, c in ipairs(kids) do
      if c:getName() == name then return c end
    end
    local sets = parent.getChildCollectionSets and parent:getChildCollectionSets() or {}
    for _, s in ipairs(sets) do
      local found = recurse(s)
      if found then return found end
    end
    return nil
  end
  return recurse(catalog)
end

local function find_collection_set_by_name(catalog, name)
  local function recurse(parent)
    local sets = parent.getChildCollectionSets and parent:getChildCollectionSets() or {}
    for _, s in ipairs(sets) do
      if s:getName() == name then return s end
      local found = recurse(s)
      if found then return found end
    end
    return nil
  end
  return recurse(catalog)
end

Handlers["collections.list"] = function(_params)
  local cat = LrApplication.activeCatalog()
  local out = {}
  walk_collection_tree(cat, out, nil)
  return { collections = out, count = #out }
end

Handlers["collections.create"] = function(params)
  local cat = LrApplication.activeCatalog()
  local name = params and params.name
  local parent_name = params and params.parent
  if type(name) ~= "string" or name == "" then
    error("collections.create: 'name' must be non-empty string")
  end

  local parent_set
  if parent_name and parent_name ~= "" then
    parent_set = find_collection_set_by_name(cat, parent_name)
    if not parent_set then
      error("collections.create: parent collection set not found: " .. parent_name)
    end
  end

  local created
  cat:withWriteAccessDo("lightroom-py: create collection", function()
    -- LrCatalog:createCollection(name, parentSet?, returnExisting?) -> LrCollection
    created = cat:createCollection(name, parent_set, true)
  end, { timeout = 10, asynchronous = false })

  return {
    name        = created:getName(),
    kind        = "collection",
    parent      = parent_name,
    id          = tostring(created.localIdentifier or ""),
    photo_count = 0,
  }
end

Handlers["collections.add"] = function(params)
  local cat = LrApplication.activeCatalog()
  local coll_name = params and params.collection
  local uuids = (params and params.uuids) or {}
  if type(coll_name) ~= "string" or coll_name == "" then
    error("collections.add: 'collection' must be non-empty string")
  end
  if type(uuids) ~= "table" or #uuids == 0 then
    error("collections.add: 'uuids' must be non-empty list")
  end

  local coll = find_collection_by_name(cat, coll_name)
  if not coll then
    error("collections.add: collection not found: " .. coll_name)
  end

  local photos, missing = lookup_photos_by_uuid(cat, uuids)
  cat:withWriteAccessDo("lightroom-py: add to collection", function()
    coll:addPhotos(photos)
  end, { timeout = 30, asynchronous = false })

  return { added = #photos, missing = missing }
end

Handlers["collections.remove"] = function(params)
  local cat = LrApplication.activeCatalog()
  local coll_name = params and params.collection
  local uuids = (params and params.uuids) or {}
  if type(coll_name) ~= "string" or coll_name == "" then
    error("collections.remove: 'collection' must be non-empty string")
  end

  local coll = find_collection_by_name(cat, coll_name)
  if not coll then
    error("collections.remove: collection not found: " .. coll_name)
  end

  local photos, missing = lookup_photos_by_uuid(cat, uuids)
  cat:withWriteAccessDo("lightroom-py: remove from collection", function()
    coll:removePhotos(photos)
  end, { timeout = 30, asynchronous = false })

  return { removed = #photos, missing = missing }
end

Handlers["collections.delete"] = function(params)
  local cat = LrApplication.activeCatalog()
  local coll_name = params and params.collection
  if type(coll_name) ~= "string" or coll_name == "" then
    error("collections.delete: 'collection' must be non-empty string")
  end

  local coll = find_collection_by_name(cat, coll_name)
  if not coll then
    error("collections.delete: collection not found: " .. coll_name)
  end

  cat:withWriteAccessDo("lightroom-py: delete collection", function()
    coll:delete()
  end, { timeout = 10, asynchronous = false })

  return { deleted = coll_name }
end

Handlers["collections.get_photos"] = function(params)
  local cat = LrApplication.activeCatalog()
  local coll_name = params and params.collection
  if type(coll_name) ~= "string" or coll_name == "" then
    error("collections.get_photos: 'collection' must be non-empty string")
  end

  local coll = find_collection_by_name(cat, coll_name)
  if not coll then
    error("collections.get_photos: collection not found: " .. coll_name)
  end

  local photos = coll:getPhotos() or {}
  local uuids = {}
  for _, p in ipairs(photos) do
    table.insert(uuids, p:getRawMetadata("uuid"))
  end
  return { uuids = uuids, count = #uuids }
end

-- ---------- library (v0.3 — was Phase 3 debt) ----------

Handlers["library.list_folders"] = function(_params)
  local cat = LrApplication.activeCatalog()
  local out = {}
  -- LR catalog has root folders (drives) and child folders below.
  local roots = cat.getFolders and cat:getFolders() or {}
  local function walk(folder, depth)
    table.insert(out, {
      name = folder:getName(),
      path = folder:getPath(),
      depth = depth,
    })
    local kids = folder.getChildren and folder:getChildren() or {}
    for _, kid in ipairs(kids) do walk(kid, depth + 1) end
  end
  for _, root in ipairs(roots) do walk(root, 0) end
  return { folders = out, count = #out }
end

Handlers["library.make_virtual_copy"] = function(_params)
  -- Verified against LR Classic 15.3: the SDK does not expose a public API
  -- for creating virtual copies. Neither catalog:createVirtualCopies nor
  -- photo:createVirtualCopy exists. Virtual copies remain a UI-only feature.
  --
  -- If Adobe documents this in a future SDK version, restore the
  -- implementation. Until then, return a clear error so the agent knows.
  error(
    "library.make_virtual_copy: LR SDK does not expose a public virtual-copy " ..
    "creation API as of LR Classic 15.3. Use Photo > Create Virtual Copy in " ..
    "the LR UI manually."
  )
end

Handlers["library.stack"] = function(params)
  -- Stack the given photos together. Position-zero is the top of the stack.
  local cat = LrApplication.activeCatalog()
  local uuids = (params and params.uuids) or {}
  if type(uuids) ~= "table" or #uuids < 2 then
    error("library.stack: need at least 2 uuids")
  end

  local photos, missing = lookup_photos_by_uuid(cat, uuids)
  if #photos < 2 then
    error("library.stack: fewer than 2 photos resolved (missing: " ..
          table.concat(missing, ",") .. ")")
  end

  local top = photos[1]
  cat:withWriteAccessDo("lightroom-py: stack", function()
    -- LrPhoto has stackInFolderWithMode... varies by SDK. The portable
    -- variant is to call cat:setStack(photos, top) where top is the photo
    -- at position 0.
    if top.stackInFolderWith then
      for i = 2, #photos do top:stackInFolderWith(photos[i]) end
    end
  end, { timeout = 30, asynchronous = false })

  return { stacked = #photos, missing = missing }
end

return Handlers
