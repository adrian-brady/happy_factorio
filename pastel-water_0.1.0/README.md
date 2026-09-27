# Pastel Water

A tiny Factorio 2.0 mod that turns water a bright, pastel cyan. It's the companion to the
Pastel Factorio graphics recolor, and it's needed because the game draws water with a shader.
The water color comes from the water tiles' settings in the game data, not from any PNG, so
recoloring graphics can't change it.

It changes only the color values of the water tiles (`effect_color` and
`effect_color_secondary`). Nothing else.

## Install (Mac)

1. Quit Factorio.
2. Put **`pastel-water_0.1.0.zip` itself** (don't unzip it) into your mods folder:
   `~/Library/Application Support/factorio/mods/`
   (In Finder: Go → Go to Folder…, then paste that path.)
3. Start Factorio. It should appear under **Mods** and be enabled.
   If it isn't, tick it and let the game restart.

## Adjust

**Settings → Mod settings → Startup**:

- **Strength**: 0 = vanilla water, 1 = fully the new color. Default 1.0.
- **Water color** / **Deep water color**: hex codes. Defaults `#7FDDE6` and `#4FC3D9`,
  the same as in the graphics recolor.

Changing a startup setting makes the game restart once to apply it.
Green (swampy) water is tinted toward mint, and muddy shallows toward light sand.

## Turn it off

Disable or remove it in the **Mods** menu (or delete the zip from the mods folder).

## Good to know

- **Multiplayer:** like any mod, everyone in a game has to have it with the same settings.
  To join vanilla servers, disable it first.
- **Achievements** keep working with a mod that only changes visuals like this,
  as far as I know, but that isn't guaranteed.
- **If the game shows an error at startup**, the error message names the file and line.
  Disable the mod to get back in, and share the message so it can be fixed.
- The game's log file lists which water tiles were changed:
  `~/Library/Application Support/factorio/factorio-current.log`, search for "Pastel Water".
  If it says "recolored 0 water tile(s)", the mod found nothing to change, so the water
  color is set somewhere else in this game version. Share that line so the mod can be adjusted.
