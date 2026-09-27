-- Startup settings: change them in Settings > Mod settings > Startup.
-- Changing a startup setting makes the game restart to apply it.
data:extend({
  {
    type = "double-setting",
    name = "pastel-water-strength",
    setting_type = "startup",
    default_value = 1.0,
    minimum_value = 0,
    maximum_value = 1,
    order = "a"
  },
  {
    type = "string-setting",
    name = "pastel-water-color",
    setting_type = "startup",
    default_value = "#7FDDE6",
    order = "b"
  },
  {
    type = "string-setting",
    name = "pastel-water-deep-color",
    setting_type = "startup",
    default_value = "#4FC3D9",
    order = "c"
  },
})
