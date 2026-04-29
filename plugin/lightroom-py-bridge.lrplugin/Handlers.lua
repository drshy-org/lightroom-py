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
  if type(rating) ~= "number" or rating < 0 or rating > 5 then
    error("metadata.set_rating: 'rating' must be an integer 0..5")
  end

  local touched = 0
  cat:withWriteAccessDo("lightroom-py: set rating", function()
    for _, photo in ipairs(photos) do
      photo:setRawMetadata("rating", rating)
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

return Handlers
