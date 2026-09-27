# Pastel Factorio

Recolors Factorio's graphics into a brighter, pastel look. See `plan.md` for the full design.

## One-time setup (Mac)

From this folder in Terminal:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

In every new Terminal window afterwards, run `source .venv/bin/activate` first.

## Add the game's graphics

Copy these two folders from the game into this project, so you have:

    data/base/graphics/
    data/core/graphics/

On a Mac with Steam, they're in
`~/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/data/`
(in Finder: right-click factorio.app → Show Package Contents).
Copy them from a vanilla install, never from one you've already recolored.

## Try it

    python3 -m pastel --preview grass-1.png
    python3 -m pastel --preview iron-ore --bg grass
    python3 -m pastel --preview assembling-machine-1.png --crop 0,0,214,226 --zoom 2
    python3 -m pastel --preview lut-night

Tune colors live: run a preview with `--watch`, edit `config/palette.yaml`, save.
Preview reloads the image by itself.

## Build

    python3 -m pastel build                       # everything
    python3 -m pastel build --only "terrain.*,ore.*,shadow,lut"   # just these; the rest copied as-is

This writes `data/base/updated_graphics` and `data/core/updated_graphics`. Reruns only redo
files whose source or settings changed. Then:

1. Quit Factorio.
2. In the game's `data/base/`, delete or move away `graphics`, copy in `updated_graphics`, rename it to `graphics`.
3. Same for `data/core/`.

To undo, put the vanilla folders back (your copies in `data/*/graphics`, or Steam's
"Verify integrity of game files").

## Water

The game colors water with a shader whose colors live in its Lua data, not in the graphics,
so this pipeline can't change water. The separate **Pastel Water** mod
(`pastel-water_0.1.0.zip`) does that: put the zip as-is in
`~/Library/Application Support/factorio/mods/`. Its own README has the details.

## Other commands

    python3 -m pastel classify     # which category every PNG falls in → build/classification_report.csv
    python3 -m pastel sheets       # before/after contact sheets per category (after a build)
    python3 -m pastel validate     # re-check output against the source
