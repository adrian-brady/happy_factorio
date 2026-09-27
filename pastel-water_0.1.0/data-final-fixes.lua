-- Pastel Water: moves the water tiles' shader colors toward pastel cyan.
--
-- In Factorio 2.0 water is drawn by a shader, and its color comes from each
-- water tile's `effect_color` (main color) and `effect_color_secondary`
-- properties, not from the water PNGs. This file blends those existing values
-- toward the target colors, so it adapts to whatever the vanilla values are.

local strength = settings.startup["pastel-water-strength"].value
local water_hex = settings.startup["pastel-water-color"].value
local deep_hex = settings.startup["pastel-water-deep-color"].value

local function parse_hex(hex, fallback)
  local h = (hex or ""):gsub("#", ""):gsub("%s", "")
  if #h ~= 6 or not h:match("^%x+$") then
    log("Pastel Water: '" .. tostring(hex) .. "' is not a valid hex color, using " .. fallback)
    h = fallback:gsub("#", "")
  end
  return {
    r = tonumber(h:sub(1, 2), 16) / 255,
    g = tonumber(h:sub(3, 4), 16) / 255,
    b = tonumber(h:sub(5, 6), 16) / 255,
  }
end

-- Factorio colors can be {r=,g=,b=,a=} or {r, g, b, a}, in 0..1 or 0..255.
local function to_unit(c)
  local r = c.r or c[1] or 0
  local g = c.g or c[2] or 0
  local b = c.b or c[3] or 0
  local a = c.a or c[4]
  if r > 1 or g > 1 or b > 1 or (a and a > 1) then
    r, g, b = r / 255, g / 255, b / 255
    if a then a = a / 255 end
  end
  return r, g, b, a
end

local function blend(c, target, s)
  local r, g, b, a = to_unit(c)
  local out = {
    r = r + (target.r - r) * s,
    g = g + (target.g - g) * s,
    b = b + (target.b - b) * s,
  }
  if a then out.a = a end
  return out
end

local function mix(t1, t2, k)
  return {r = t1.r + (t2.r - t1.r) * k, g = t1.g + (t2.g - t1.g) * k, b = t1.b + (t2.b - t1.b) * k}
end

local water = parse_hex(water_hex, "#7FDDE6")
local deep = parse_hex(deep_hex, "#4FC3D9")
local mint = {r = 0.56, g = 0.89, b = 0.78}   -- for the green (swampy) water variants
local mud = {r = 0.85, g = 0.79, b = 0.60}    -- muddy shallows stay sandy, just lighter

-- tile name -> target color
local targets = {
  ["water"]           = water,
  ["water-wube"]      = water,
  ["water-shallow"]   = mix(water, {r = 1, g = 1, b = 1}, 0.2),
  ["water-mud"]       = mud,
  ["deepwater"]       = deep,
  ["water-green"]     = mix(water, mint, 0.6),
  ["deepwater-green"] = mix(deep, mint, 0.5),
}

local changed = {}
for name, target in pairs(targets) do
  local tile = data.raw.tile[name]
  -- Only tiles drawn by the water shader (they have an `effect`) use these colors.
  if tile and tile.effect then
    -- If vanilla doesn't set the color explicitly, start from the target itself.
    tile.effect_color = blend(tile.effect_color or target, target, strength)
    if tile.effect_color_secondary then
      -- The secondary color is a subtle second tint; move it less.
      tile.effect_color_secondary = blend(tile.effect_color_secondary, target, strength * 0.5)
    end
    table.insert(changed, name)
  end
end

table.sort(changed)
log("Pastel Water: recolored " .. #changed .. " water tile(s): " .. table.concat(changed, ", "))
