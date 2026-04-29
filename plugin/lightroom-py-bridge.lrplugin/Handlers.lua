--[[
  Handlers.lua — command dispatcher.

  Each entry maps a method name to a function(params) -> result. Handlers run
  inside an LrTasks task; they may use catalog APIs.
]]

local LrApplication = import "LrApplication"

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

local function find_or_create_keyword(catalog, name)
  -- Search top-level keywords by name. (Hierarchical paths like "A|B" not yet supported.)
  local existing = catalog:getKeywords() or {}
  for _, kw in ipairs(existing) do
    if kw:getName() == name then return kw end
  end
  return catalog:createKeyword(name, {}, false, nil, true)
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

Handlers["metadata.remove_keywords"] = function(params)
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  local names = (params and params.keywords) or {}
  if type(names) ~= "table" or #names == 0 then
    error("metadata.remove_keywords: 'keywords' must be a non-empty list")
  end

  -- Build set of existing keyword name->kw for quick lookup.
  local existing = {}
  for _, kw in ipairs(cat:getKeywords() or {}) do existing[kw:getName()] = kw end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: remove keywords", function()
    for _, photo in ipairs(photos) do
      for _, n in ipairs(names) do
        local kw = existing[n]
        if kw then photo:removeKeyword(kw) end
      end
      touched = touched + 1
    end
  end, { timeout = 30, asynchronous = false })

  return { touched = touched, missing = missing, keywords = names }
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
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)
  if #photos == 0 then
    error("develop.get_settings: no target photo (pass uuid or set selection)")
  end

  local out = {}
  cat:withReadAccessDo("lightroom-py: get develop settings", function()
    for _, photo in ipairs(photos) do
      local uid = photo:getRawMetadata("uuid")
      out[uid] = photo:getDevelopSettings()
    end
  end, { timeout = 30 })

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

  local settings
  cat:withReadAccessDo("lightroom-py: read src settings", function()
    settings = src_photo:getDevelopSettings()
  end, { timeout = 10 })

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
  local cat = LrApplication.activeCatalog()
  local photos, missing = target_photos(cat, params)

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: reset develop", function()
    for _, photo in ipairs(photos) do
      photo:resetDevelopSettings()
      touched = touched + 1
    end
  end, { timeout = 60, asynchronous = false })

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
  -- After Python has run an external tool on the exported files and dropped
  -- result paths next to (or on top of) the originals, this re-imports them
  -- into the catalog and stacks each result with the source photo.
  local cat = LrApplication.activeCatalog()
  local pairs_ = (params and params.pairs) or {}
  if type(pairs_) ~= "table" or #pairs_ == 0 then
    error("edit_in.import_as_stack: 'pairs' must be a non-empty list of {src_uuid, result_path}")
  end

  -- Build src lookup.
  local want = {}
  for _, p in ipairs(pairs_) do want[p.src_uuid] = true end
  local src_by_uuid = {}
  for _, photo in ipairs(cat:getAllPhotos()) do
    local uid = photo:getRawMetadata("uuid")
    if want[uid] then src_by_uuid[uid] = photo end
  end

  local imported = {}
  local errors = {}
  cat:withWriteAccessDo("lightroom-py: import edit-in result", function()
    for _, p in ipairs(pairs_) do
      local src = src_by_uuid[p.src_uuid]
      if not src then
        table.insert(errors, { src_uuid = p.src_uuid, error = "src not found" })
      else
        local ok, new_photo_or_err = pcall(function()
          return cat:addPhoto(p.result_path, src, "above")
        end)
        if ok then
          table.insert(imported, {
            src_uuid = p.src_uuid,
            new_uuid = new_photo_or_err and new_photo_or_err:getRawMetadata("uuid"),
          })
        else
          table.insert(errors, {
            src_uuid = p.src_uuid,
            result_path = p.result_path,
            error = tostring(new_photo_or_err),
          })
        end
      end
    end
  end, { timeout = 120, asynchronous = false })

  return { imported = imported, errors = errors }
end

return Handlers
