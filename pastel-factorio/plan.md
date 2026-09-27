# Pastel Factorio: Recolor Pipeline Plan

Status: **v5**. Phase 0 code done; waiting on the in-game check. Decisions are in section 12.

## 1. Goal

Produce a drop-in replacement for Factorio's graphics folders in which every PNG has the **same filename, dimensions, pixel layout and alpha shape** as the original, but recolored toward a bright, happy, modern, cartoony look.

**Target feel:** a more pastel, slightly brighter Stardew Valley. That means warm, soft, sunny colors with clear readable shapes. It should not be as saturated or candy-like as Animal Crossing, and not washed out to white either.

- No mod, no Lua, no prototype changes. The game should not be able to tell anything changed.
- The pipeline is **re-runnable**: after a game update, copy in fresh vanilla folders and run it again.
- The pipeline is **deterministic**: same input + same config produces byte-identical output.

### Hard constraints (the pipeline verifies each of these on every file)

1. Same set of files and relative paths as the source. Every non-PNG file is copied through byte-for-byte (see 2.2).
2. Same width and height.
3. **Same PNG color mode.** RGB stays RGB, RGBA stays RGBA, palette (`P`) stays palette, grayscale stays grayscale. Several important files are not RGBA (see 2.3).
4. **Same PNG metadata.** The `gAMA` chunk (many files carry gamma 0.45455) and any `sRGB`/`iCCP` chunks are preserved, so the game decodes the colors exactly as before.
5. Alpha unchanged, except for shadows, which get softer opacity (6.6). Which pixels are visible never changes.
6. Fully transparent pixels keep their original RGB (avoids fringe artifacts under texture filtering).
7. `.DS_Store` files are skipped (they're macOS folder metadata, not game files).

## 2. What's actually in the folders (from your listing)

### 2.1 Counts

**4,739 PNGs** in total.

| Folder | PNGs | Notes |
|---|---|---|
| `base/graphics/entity` | 2,344 | Buildings, trees (559), enemies, vehicles, effects |
| `base/graphics/decorative` | 759 | Rocks, bushes, grass tufts, decals |
| `base/graphics/icons` | 580 | Item/entity icons plus signal, fluid, shortcut and arrow subfolders |
| `base/graphics/particle` | 170 | Ore chunks, wood, stone, leaves |
| `base/graphics/terrain` | 156 | Tiles, transitions, cliffs, water |
| `base/graphics/technology` | 132 | Research art |
| `base/graphics/achievement`, `equipment`, `item-group` | 79 | GUI-side art |
| `core/graphics` | ~520 | GUI, cursors, core icons, color LUTs, clouds, lights, wires |

### 2.2 Non-PNG files that must be copied through untouched

- **193 `.lua` files inside `base/graphics/entity`** (biter, cargo-hubs, cargo-pod, locomotive, rail signals, ...). These are sprite layout data the game loads. Missing or changed, the game won't start.
- **309 shader files** in `core/graphics/shaders` (`.frag`, `.vert`, `.psh`, `.vsh`, `.metal`, `.cso`).
- `background-image.jpg`, `factorio.icns`, `factorio.ico`, `splash-screen-space-age.dat`.

### 2.3 Findings from the sample files

| File | Format | What it tells us |
|---|---|---|
| `grass-1.png` | RGBA 4096×576 | One sheet holds the main variants plus transition pieces with soft alpha edges. Measured color: dull olive (OKLCH hue ~99°, lightness ~0.40) with brown patches mixed in (hue range 65–113°). It is more brown-olive than green, so grass needs a real **hue rotation**, not just a brightness lift. |
| `dirt-1.png` | RGBA 4096×576 | Already tan-orange (hue ~70°, lightness ~0.65). Needs only a lighter, softer, slightly warmer push. Easy win. |
| `water2.png` | **RGB** 1024×128, no alpha | Dark teal (hue ~217°, lightness ~0.43). Needs a large lift and a shift toward cyan (~200°). |
| `iron-ore.png` | RGBA | Nearly gray (very low chroma) with dark shading down to lightness 0.21. Needs a blue tint and a strong lift. |
| `assembling-machine-1.png` | RGBA | Very dark (5th percentile lightness 0.14) mix of olive-green panels and rust-brown. The gloomiest of the samples. |
| `assembling-machine-1-shadow.png` | **Palette (`P`) mode**, 255 entries, alpha in the `tRNS` chunk | Every palette color is pure black; only the alpha varies. Shadow softening becomes an edit of the palette and `tRNS` table, which is tiny, exact and keeps the file format identical. |
| `color_luts/*.png` | RGB 256×16 | A 16×16×16 3D lookup table stored as 16 tiles of 16×16: red runs across each tile, green down it, blue from tile to tile. Details in 6.10. |

### 2.4 Naming patterns that drive classification

- **Terrain tiles are flat files**, not folders: `terrain/grass-1.png` … `grass-4.png`, `dirt-1..7`, `dry-dirt`, `sand-1..3`, `red-desert-0..3`, `landfill`, `nuclear-ground`. Water, concrete and stone path are folders.
- **Trees** have five layers per variant: `-leaves`, `-trunk`, `-stump`, `-shadow`, `-normal`, plus `tree-NN-reflection.png`.
- **Normal maps** (93 files, all `tree/*-normal.png`): not colors at all. They encode surface direction for lighting. **Must pass through.** Recoloring them would break tree lighting.
- **Masks** (199 files): `*-mask*.png` (biter, spitter, worm, locomotive, car, tank, cargo-wagon, character `leveladdon_*_mask`), plus terrain `masks/` and concrete `*-mask.png`.
- **Shadows**: 527 files contain `shadow`.
- **Lights**: `*-light.png`, `*-lights-N.png` (beacon, boiler, car, ...). The word "light" also appears in `decorative/light-mud-decal`, so rules must match suffixes, not the bare word.
- **Emission/glow**: `*-emission.png`, `*-glow.png` (steel furnace, uranium ore).
- **Tintable**: `*-tintable*.png`, `rocket-tinted-tip.png`.
- **Reflections**: `*-reflection.png`, `*-water-reflection.png`.
- **Remnants** (186 files): wreckage of destroyed buildings. Should match their building.
- **Terrain `effect-maps/`, `masks/`, `effects/water-noise.png`**: shader data, pass through.

## 3. What PNGs can and cannot change

Some of what you see in-game comes from prototype data or shaders rather than from pixels. Since we are not touching Lua, these stay vanilla:

- **Minimap and map view colors** (`map_color` on tiles and entities). The map will still look like vanilla Factorio.
- **Runtime tints**: player color on vehicles and characters, fluid colors in pipes and tanks, biter/spitter/worm tier colors, some particle and smoke tints. These are multiplied over mask sprites.
- **Water shader parameters.** In 2.0, water is rendered by a shader that combines the water tile textures with the effect maps and `water-noise.png`. The PNG textures still drive most of the color, but how far we can push water toward cyan must be tested in Phase 0.
- **Light colors and night darkness levels** are set in prototypes. The rendered frame does pass through the color LUTs, which are the lever for softer nights (6.10).
- **Daytime probably can't be graded by LUT** (see 6.10). The daytime look comes from the sprites.

## 4. Approach overview

Four stages. Each writes its results to disk so any stage can be rerun alone.

```
vanilla data/  ──►  1. Inventory  ──►  2. Classify  ──►  3. Transform  ──►  4. Validate + Report
                    (scan, hash,       (rules.yaml       (palette.yaml,      (constraint checks,
                     stats per PNG)     assigns each      per-category        contact sheets,
                                        file a category)  color transforms)   summary)
```

`--preview` (7.1) runs stages 2 and 3 on a single file in memory, for fast tuning.

### Core idea

Every pixel goes through a **category-specific transform in OKLCH color space** (perceptual lightness, chroma, hue). OKLCH is used instead of RGB or HSV because it lets us raise lightness and soften saturation without hue drift, which is exactly the pastel move.

A transform is made of three parts, all driven by config:

1. **Lightness lift.** Compress the dark range upward: `L' = L_floor + (L_ceil - L_floor) * L^gamma`, starting around `L_floor ≈ 0.40`, `gamma ≈ 0.75`. This removes the gloom while keeping darks the darkest part of each sprite.
2. **Hue remap.** A piecewise-linear mapping of the hue wheel, defined as anchor pairs (`source_hue → target_hue`) per category. Because it's a smooth, order-preserving mapping, variation inside a texture survives: in grass, the olive areas go to fresh green and the brown patches go to a warm yellow-green or tan, rather than everything collapsing to one green. Near-neutral pixels (low chroma: steel, concrete, iron ore) get a category tint hue so they read as soft color instead of gray.
3. **Chroma shaping.** Pastel means high lightness with moderate chroma. Dull pixels get a chroma boost, loud ones get capped: `C' = min(C * k + c_add, C_max(L'))`. The cap is what keeps us at "pastel Stardew" rather than candy. Results are gamut-clipped by reducing chroma, never by clipping RGB channels, so hues stay true.

### Global intensity knobs

Two global multipliers in `palette.yaml` apply on top of every category, so the overall feel can be tuned in one place:

- `global.brightness` scales how far the lightness lift goes (0 = vanilla, 1 = as designed).
- `global.saturation` scales colorfulness everywhere (1 = as designed, below 1 softer and more pastel, above 1 punchier).

### Detail preservation

Lifting lightness flattens texture. To keep sprites crisp and cartoony, lightness is transformed on a blurred copy and the local detail is added back with a gain:

```
L_base  = gaussian_blur(L, sigma)
L_new   = transform(L_base) + detail_gain * (L - L_base)
```

`detail_gain` slightly above 1 gives a punchier, more illustrated look. Tuned per category. The blur is alpha-weighted so transparent neighbors (sprite edges, gaps between frames on a sheet) don't bleed dark values into the edges.

Two more tools came out of Phase 0 testing:
- **Color smoothing** (`detail.color_blur`): the color (a/b channels), but not the lightness, is lightly blurred before remapping. Without it, grain in grayish metal turned into rainbow speckle once chroma was boosted. With it, color areas read as cleaner, flatter and more cartoon-like while texture stays in the lightness.
- **Outline keeping** (`outline`, remap categories): within a couple of pixels of a sprite's edge, lightness is pulled back toward the original dark contour, so buildings stay crisp on light ground instead of fading into it.
- **Highlight roll-off** (`soft_max`, transfer categories): lightness above a knee is compressed smoothly instead of clipping to white, so bright specks in grass and ore keep their color.

### Consistency rules

- **Transforms are per category, never per image.** There is no per-file auto-normalization. Many sprites are split across several sheets, and tiles have variants and transitions that must meet seamlessly.
- Related files share a transform: icons, remnants, particles and water reflections use the transform of the thing they depict. For example, `iron-ore-particle` uses `ore.iron`, and `assembling-machine-1-remnants` uses the entity transform.

## 5. Stage details

### 5.1 Inventory

Walk every `data/*/graphics/**` file. For each PNG record: relative path, size, PNG mode, bit depth, metadata chunks, SHA-256, and quick color stats (median OKLCH, lightness percentiles, fraction transparent). Write `build/inventory.csv`.

This gives a checked list of everything that exists and powers incremental rebuilds: a file is skipped when both its source hash and the hash of its category's config are unchanged.

### 5.2 Classify

`config/rules.yaml` holds ordered rules; **first match wins**. Patterns are globs on the path relative to `data/`. Every PNG must end up in exactly one category, and **unmatched files fail the build loudly** with a list, so nothing gets a silent default.

Order matters: special layers (normal maps, masks, shadows, lights) come first, because those rules must win over the folder the file happens to be in. Draft based on your listing:

```yaml
# ===== 1. Never recolor: data, not color =====
- {match: "base/graphics/icons/quality-normal.png", category: icon}  # an icon, not a normal map
- {match: "**/*-normal.png",            category: passthrough}   # tree normal maps
- {match: "**/*mask*.png",              category: passthrough}   # runtime-tinted, concrete & terrain masks
- {match: "**/*tintable*.png",          category: passthrough}
- {match: "**/*tinted*.png",            category: passthrough}
- {match: "base/graphics/terrain/effect-maps/**", category: passthrough}
- {match: "base/graphics/terrain/effects/**",     category: passthrough}
- {match: "base/graphics/terrain/masks/**",       category: passthrough}

# ===== 2. core: pass-through except whitelisted world files =====
- {match: "core/graphics/color_luts/*.png", category: lut}
- {match: "core/graphics/**",           category: passthrough}   # GUI, cursors, icons, lights, clouds

# ===== 3. Special blend layers =====
- {match: "**/*shadow*.png",            category: shadow}
- {match: "**/*-light.png",             category: light}
- {match: "**/*-lights-*.png",          category: light}
- {match: "**/*-emission*.png",         category: light}
- {match: "**/*-glow.png",              category: light}
- {match: "**/*reflection*.png",        category: reflection}    # follows its entity's transform

# ===== 4. Terrain =====
- {match: "base/graphics/terrain/grass-*.png",        category: terrain.grass}
- {match: "base/graphics/terrain/dirt-*.png",         category: terrain.dirt}
- {match: "base/graphics/terrain/dry-dirt.png",       category: terrain.dirt}
- {match: "base/graphics/terrain/sand-*.png",         category: terrain.sand}
- {match: "base/graphics/terrain/red-desert-*.png",   category: terrain.red_desert}
- {match: "base/graphics/terrain/landfill.png",       category: terrain.landfill}
- {match: "base/graphics/terrain/nuclear-ground.png", category: terrain.nuclear}
- {match: "base/graphics/terrain/water/**",           category: terrain.water}
- {match: "base/graphics/terrain/water-green/**",     category: terrain.water_green}
- {match: "base/graphics/terrain/deepwater/**",       category: terrain.deepwater}
- {match: "base/graphics/terrain/deepwater-green/**", category: terrain.deepwater_green}
- {match: "base/graphics/terrain/water-shallow/**",   category: terrain.water_shallow}
- {match: "base/graphics/terrain/water-mud/**",       category: terrain.water_mud}
- {match: "base/graphics/terrain/water-wube/**",      category: terrain.water}
- {match: "base/graphics/terrain/water-transitions/*grass*",  category: terrain.grass}
- {match: "base/graphics/terrain/water-transitions/*dirt*",   category: terrain.dirt}
- {match: "base/graphics/terrain/water-transitions/*sand*",   category: terrain.sand}
# ... one line per remaining water-transitions / out-of-map-transition file, matched to its tile
- {match: "base/graphics/terrain/stone-path/**",      category: terrain.stone_path}
- {match: "base/graphics/terrain/concrete/refined-*", category: terrain.refined_concrete}
- {match: "base/graphics/terrain/concrete/**",        category: terrain.concrete}
- {match: "base/graphics/terrain/hazard-concrete-*/**", category: terrain.hazard}
- {match: "base/graphics/terrain/cliffs/**",          category: rock}
- {match: "base/graphics/terrain/lab-tiles/**",       category: passthrough}   # editor-only
- {match: "base/graphics/terrain/tutorial-grid/**",   category: passthrough}   # tutorial-only
- {match: "base/graphics/terrain/out-of-map*",        category: passthrough}   # the black void

# ===== 5. Resources and nature =====
- {match: "base/graphics/entity/iron-ore/**",    category: ore.iron}
- {match: "base/graphics/particle/iron-ore-particle/**", category: ore.iron}
- {match: "base/graphics/entity/copper-ore/**",  category: ore.copper}
- {match: "base/graphics/entity/coal/**",        category: ore.coal}
- {match: "base/graphics/entity/stone/**",       category: ore.stone}
- {match: "base/graphics/entity/uranium-ore/**", category: ore.uranium}
- {match: "base/graphics/entity/crude-oil/**",   category: ore.oil}
# ... matching particle folders for copper, coal, stone
- {match: "base/graphics/entity/tree/**/*-leaves.png", category: foliage}
- {match: "base/graphics/entity/tree/**",        category: wood}       # trunk, stump
- {match: "base/graphics/decorative/green-*/**", category: foliage}
- {match: "base/graphics/decorative/brown-*/**", category: foliage.dry}
- {match: "base/graphics/decorative/red-*/**",   category: foliage.red}
- {match: "base/graphics/decorative/*rock*/**",  category: rock}
- {match: "base/graphics/decorative/*-decal/**", category: decal}      # blends into terrain
- {match: "base/graphics/decorative/**",         category: foliage}

# ===== 6. Enemies (pastel too, D11) =====
- {match: "base/graphics/entity/{biter,spitter,worm,spawner}/**", category: enemy}

# ===== 7. Everything else =====
- {match: "base/graphics/icons/**",       category: icon}
- {match: "base/graphics/technology/**",  category: technology}
- {match: "base/graphics/particle/**",    category: entity.default}
- {match: "base/graphics/entity/**",      category: entity.default}
- {match: "base/graphics/{achievement,equipment,item-group}/**", category: icon}
```

The real rules live in `config/rules.yaml`. They were checked against your full listing: **all 4,739 PNGs match a rule**. The biggest groups are entity (1,050), passthrough (831), shadow (527), icon (338), wood (320), icon.gui (312) and foliage (284). `python3 -m pastel classify` writes `build/classification_report.csv` showing each file's category and the rule that matched.

### 5.3 Transform

`config/palette.yaml` defines the named target colors, the global knobs and each category's parameters. Implementation: Python with numpy and Pillow, multiprocessing across files. OKLab math is vectorized in numpy (no per-pixel Python loops).

Per format:

- **RGBA / RGB / grayscale+alpha**: transform RGB, keep alpha (except shadows), write in the original mode.
- **Palette (`P`)**: transform the palette entries and the `tRNS` alpha table, not the pixels. The index data is untouched, so the file stays an identical-structure palette PNG.
- **16-bit or unusual modes**: listed in the report and passed through until handled explicitly.

Output goes to `data/<folder>/updated_graphics/...` with the same internal structure, never in place.

### 5.4 Validate and report

- Constraint checks from section 1 on every output file, including mode and metadata. Any failure fails the build.
- Every non-PNG file in the source exists byte-identical in the output.
- **Contact sheets**: per category, a grid of before/after thumbnails (`build/sheets/<category>.png`).
- **Terrain mosaic**: all tiles laid out next to each other, plus ore on top of dirt, grass and sand, so neighboring colors and contrast can be judged outside the game.
- Summary: files per category, time taken, skipped/unchanged counts, pass-through files.

## 6. Category designs (first pass)

Hex values are starting targets, to be tuned with `--preview`.

### 6.1 Terrain (the biggest visual win)

| Tile | Vanilla (measured or observed) | Target | Notes |
|---|---|---|---|
| Grass 1–4 | Olive-brown, hue ~99°, L ~0.40 | `#A8E39A` to `#C8F0B4` | Needs hue rotation toward ~140° plus a big lift. Brown patches inside grass go to warm yellow-green, keeping the natural patchiness. Keep 1–4 subtly distinct. |
| Dirt 1–7, dry dirt | Tan-orange, hue ~70°, L ~0.65 | `#E6B77E` to `#F0CB95` | Already the right hue family. Lift and soften. |
| Sand 1–3 | | `#F5E2B0` | Pale warm cream. |
| Red desert 0–3 | | `#F2B89A` | Peach-coral rather than brick. |
| Water | Dark teal, hue ~217°, L ~0.43 | `#7FDDE6` | Big lift, rotate to cyan ~200°. |
| Deep water | | `#4FC3D9` | Deeper cyan-teal, still bright. |
| Green water / deep green | | `#8FE3C8` / `#5CCBB0` | Minty version of the water pair. |
| Shallow water / mud water | | `#A6EDE8` / `#D8C99A` | |
| Landfill | | `#DCC9A0` | |
| Nuclear ground | | `#C9C2A8` | Scorched but not black. |
| Stone path | | `#E3DCCF` | Warm light stone. |
| Concrete / refined | | `#ECE7DE` / `#F4F1EA` | Soft cream, not gray. |
| Hazard concrete | | stripes `#FFD57A` / near-white | Must stay legible as hazard. |

Transition files in `water-transitions/` and `out-of-map-transition/` use the transform of the tile they belong to, so shorelines match.

**Method: category-wide color transfer.** The category's median color is moved to the target, and the variation around it is scaled by `spread`. The median is measured from the tile sheets only, not from decals, particles or transition sheets that share the transform (those would skew it). A category can override this with `stats_from: <glob>`. Measurements are cached in `build/stats.json`.

### 6.2 Ores and resources

Must stay instantly distinguishable at a glance, which matters more than any single color being perfectly pastel.

| Resource | Target |
|---|---|
| Iron | `#A9C6E6` light steel blue (vanilla is near-gray, so this is mostly a tint plus lift) |
| Copper | `#F4A67E` peach-orange |
| Coal | `#6F6A92` slate lavender (stays the darkest resource for readability) |
| Stone | `#DCC79A` sandstone |
| Uranium | `#9CF2A6` mint, with `uranium-ore-glow.png` kept bright |
| Crude oil | `#5E5A7A` soft ink with a pastel sheen |

Copper ore on tan-orange dirt is a likely collision, since dirt is already hue ~70°. Plan: push dirt slightly toward yellow-tan and copper toward pink-peach, and check on the terrain mosaic.

### 6.3 Foliage, wood, rocks, decals

- **Foliage** (tree leaves, green decoratives): bright greens with some mint and yellow-green variation.
- **Dry foliage** (`brown-*` decoratives): soft wheat and straw tones.
- **Red foliage** (`red-*` decoratives): coral and rose.
- **Wood** (trunks, stumps): warm light brown, around `#C9966B`.
- **Rocks and cliffs**: warm light stone, with lavender shading in the crevices. This is a common cartoon trick: shade with cool purple instead of black.
- **Decals** (mud, sand, lichen): transformed with the terrain they sit on, so they blend in rather than showing as dark stains.

### 6.4 Entities (buildings, belts, inserters, trains, turrets)

The industrial grays and rust are the heart of the gloomy look. The assembling machine sample confirms it: olive-green panels, rust-brown internals, and shading that goes very dark.

- Neutral grays (steel) become soft cool cream or light blue-gray, with a slight lavender cast in darker areas.
- Rust and brown become warm peach.
- Olive-green panels become sage or mint.
- Existing accent colors (inserter yellow, fast-belt red, express-belt blue, etc.) keep their hue but become pastel. **Tier colors must remain distinguishable**: yellow/red/blue belts and the inserter families.
- Dark areas are lifted but stay the darkest part of the sprite, to keep the 3D read and silhouettes clear.

Split into subcategories (`entity.belt`, `entity.inserter`, `entity.train`, ...) only where one parameter set doesn't fit.

### 6.4a Enemies (decided: pastel too)

Biters, spitters, worms and spawners get lightened with the rest of the world, in a softer, cuter direction: shells lifted to soft lilac-gray and dusty rose, dark internals lifted to muted plum rather than black. Their tier colors (small/medium/big/behemoth) come from runtime tints over their masks, which stay untouched, so tiers remain distinguishable. They should still stand out against pastel grass, so their chroma cap is set a little lower than the terrain around them and their darks are lifted less. Creep and enemy decals (`enemy-decal`, `worms-decal`) follow the same palette.

### 6.5 Pass-through layers

Unchanged, because they are data or get tinted at runtime:

- **Normal maps** (`*-normal.png`): lighting direction data for trees.
- **Masks** (`*mask*.png`): multiplied by player, fluid or enemy tier color. If player colors look too heavy against the pastel world, lightening the masks slightly is a possible later tweak.
- **Tintable layers** (`*tintable*`, `*tinted*`).
- **Terrain shader data**: `effect-maps/`, `masks/`, `effects/water-noise.png`.
- **Editor/tutorial tiles and the out-of-map void.**

### 6.6 Shadows (decided: soften)

Black, heavy shadows are a big part of the grim feel.

- **Opacity**: multiply alpha by a factor, starting at `0.6`. This is the main effect.
- **Tint**: set RGB to a cool indigo, around `#3A3560`. The game very likely draws shadow sprites using only their alpha and applies its own shadow color, in which case the tint does nothing. It costs nothing to try, and Phase 0 will show whether it has an effect. The preview shows the shadow sprite at full strength over grass; the game draws shadows semi-transparently on top of that, so in-game they look lighter than the preview.
- Palette-mode shadows (like the assembling machine one) are edited through their palette and `tRNS` table. RGBA shadows are edited per pixel.
- Tree shadows and cliff shadows are included; the same factor applies everywhere so shadows stay consistent.

### 6.7 Lights, emission, reflections

- **Lights and emission** (`*-light.png`, `*-lights-N.png`, `*-emission*.png`, `*-glow.png`): shift slightly warmer and softer. No lightness lift, since they are already bright and drawn additively, and lifting would blow them out.
- **Reflections** (`*reflection*.png`): shown in water, so they use the transform of the entity or tree they reflect.

### 6.8 Icons and technology

- **Icons** (including their packed mipmap strips) get the same transform as the matching entity or item category, so inventory matches the world.
- **Signal, fluid, arrow and shortcut icons** in `base/graphics/icons/*/`: kept close to vanilla, because they need to stay readable against the dark GUI. A light pastel pass only.
- **Technology art**: a gentler version of the entity transform.
- **Science pack colors** stay recognizable: red, green, blue, purple, yellow, white.

### 6.9 GUI (decided: out of scope by default)

The GUI stays vanilla. That covers all of `core/graphics` except the color LUTs, plus `base/graphics/achievement`, `equipment` and `item-group` (which get the light icon pass only). Reasons:

- It sits in shared sprite atlases, where a mistake can hurt text contrast, slot readability and button states across the whole game.
- Its dark panels frame the world rather than being part of it, and dark UI over a bright world is a common modern look.

`core/graphics` also holds a few files that show up in the world: `clouds*.png` (cloud shadows drifting over the ground), `light-cone/medium/small.png` (light shapes), and the wire sprites. These stay vanilla for now. Clouds are the main candidate to revisit if their shadows look too dark on the pastel ground.

**Possible later option** (Phase 5): if the dark-brown panel frames clash with the pastel world once you've played with it, a "warm frame" pass could lift and warm only the panel borders and backgrounds.

### 6.10 Color LUTs and softer nights (decided: softer nights)

`core/graphics/color_luts/` has 9 files. Each is a 16×16×16 3D lookup table stored as a 256×16 image (16 tiles of 16×16; red runs across each tile, green down it, blue from tile to tile). The pipeline reads it as a table and edits the table's output colors, never the layout.

Measured from your files:

| File | What it does now | Plan |
|---|---|---|
| `lut-night.png` | Very dark and blue: white maps to `(53, 63, 108)` | Soften (main night look) |
| `night.png` | Dark blue: white maps to `(66, 79, 135)` | Soften |
| `lut-dawn.png`, `lut-sunset.png` | Dim, desaturated: white maps to `(160, 160, 160)` | Soften a little, add a warm peach tint |
| `identity-lut.png` | Exact identity | Leave |
| `lut-day.png` | Brightens midtones (gray 136 → 192) | Leave; probably unused in normal play |
| `nightvision.png`, `frozen.png`, `orange-dawn.png` | Night vision equipment and special effects | Leave |

**Softening method.** For each night/dusk LUT: blend each output color partway back toward the input color (controlled by `night.softness`, starting at `0.35`), then lift the darkest outputs toward a moonlit lavender-blue (around `#4A4A78`) so shadows at night are dim violet rather than black. Night stays clearly night.

**Daytime.** As far as I know, Factorio's day uses a built-in `"identity"` setting rather than any of these files, so editing a day LUT would change nothing. The daytime look therefore comes entirely from the sprites. Phase 0 confirms which files the game actually uses at each time of day, by making obviously wrong test edits.

## 7. CLI

You're on a Mac, where the command is `python3`. All commands run from `project_dir` and work on `project_dir/data/`. No paths need to be passed.

```
python3 -m pastel inventory
python3 -m pastel classify
python3 -m pastel build     [--only "terrain.*"] [--clean]  # writes updated_graphics folders
python3 -m pastel sheets    [--category terrain.grass]      # contact sheets / terrain mosaic
python3 -m pastel validate
python3 -m pastel --preview <filename> [options]           # section 7.1
```

`build` runs inventory, classify, transform and validate in one go; the separate commands exist for inspecting individual stages. `--clean` deletes the existing `updated_graphics` folders and rebuilds from scratch instead of incrementally.

### 7.1 `--preview`: side-by-side single file

Fast tuning loop: pick one PNG by name, see before and after, adjust `palette.yaml`, run again.

```
python3 -m pastel --preview grass-1.png
python3 -m pastel --preview iron-ore            # partial names work
python3 -m pastel --preview entity/assembling-machine-1/assembling-machine-1.png
```

**What it does:**

1. Searches `data/*/graphics/` for the name. An exact filename match wins; otherwise a case-insensitive substring match on the path. Including part of the directory narrows it down.
2. If several files match, it prints a numbered list with their paths and categories, and asks which one to use. `--pick N` skips the prompt.
3. Classifies the file and applies its category's transform **in memory only**. Nothing in `updated_graphics` is written or changed.
4. Composes one image: **before | after** side by side (wide sheets like terrain are stacked one above the other instead), each on a checkerboard so transparency is visible. A caption bar shows the relative path, category and image size. Pass-through files say so. Shadows are shown over the new grass color, since they look like nothing on their own. LUTs are shown as a sample image (a built-in color test card) graded by the old and the new table.
5. Saves it to `build/preview/<name>_preview.png` and opens it in Preview (via `open`).

**Options:**

| Option | Purpose |
|---|---|
| `--pick N` | Choose match N without prompting |
| `--zoom F` | Scale factor. Default fits the result to about 1600 px wide; small icons are upscaled with nearest-neighbor so pixels stay sharp |
| `--crop x,y,w,h` | Show only a region. Useful for large sprite sheets where you want one frame |
| `--bg checker\|grass\|light\|dark` | Background behind transparent pixels. `grass` shows entities on the new pastel grass color, which is the closest thing to seeing them in-world |
| `--tile 3` | For terrain: repeat the main variant area in a 3×3 grid to judge how it reads across a large area |
| `--watch` | Keep running and re-render whenever `palette.yaml` or `rules.yaml` changes, so you can tweak numbers and see the result immediately |
| `--no-open` | Save only, don't open a viewer |

## 8. Project layout and setup

```
project_dir/
  plan.md
  requirements.txt
  data/
    base/graphics/          # vanilla copy (you provide; read-only)
    base/updated_graphics/  # generated
    core/graphics/          # vanilla copy (you provide; read-only)
    core/updated_graphics/  # generated
  config/
    rules.yaml          # path -> category
    palette.yaml        # named colors, global knobs, per-category params
  pastel/
    __main__.py         # CLI, including --preview
    inventory.py
    classify.py
    color.py            # sRGB <-> OKLab/OKLCH, vectorized, gamut clipping
    transforms.py       # lift, hue remap, chroma shaping, detail, shadows
    pngio.py            # read/write preserving mode, palette, tRNS, gAMA
    lut.py              # decode / transform / re-encode color LUTs
    build.py            # parallel execution, incremental cache
    preview.py          # single-file side-by-side
    sheets.py           # contact sheets, terrain mosaic
    validate.py
  build/                # cache, reports, previews
```

**One-time setup on your Mac**, from `project_dir`:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

After that, run `source .venv/bin/activate` once per new terminal window. Dependencies: numpy, Pillow, PyYAML, scipy (Gaussian blur). `--watch` polls file modification times, so no extra dependency.

## 9. Installing, updates and safety

**Installing** is manual (section 2): copy each `updated_graphics` folder into the game's `data/base/` or `data/core/`, rename to `graphics`, overwrite. Keep the vanilla copies in `project_dir/data/*/graphics` as your backup; copying them back restores the original look.

On a Mac with Steam, the game's data folder is inside the app bundle: `~/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/data/`. In Finder, right-click `factorio.app` → Show Package Contents to reach it.

**The input must always be vanilla.** Once the recolored folders are installed, the game folder is no longer a clean source. After each build, the pipeline stores the hash of every output file in `build/`. On the next run, if any input file's hash matches a previous output hash, it stops with a clear message ("these files look already recolored").

**After a game update:** the updater replaces changed files with new vanilla ones, while unchanged files stay recolored, so the install becomes a mix. Procedure:
1. Restore vanilla in the game (Steam: right-click Factorio → Properties → Installed Files → "Verify integrity of game files").
2. Copy the fresh `data/base/graphics` and `data/core/graphics` into the project, replacing the old copies.
3. `python3 -m pastel build`. It's incremental: only new and changed files are recomputed.
4. Copy the `updated_graphics` folders back into the game as before.

**Other notes:**
- Recoloring only changes local files. Multiplayer is unaffected, since graphics aren't synced or checksummed like mods.
- **Disk space:** vanilla copy plus output means roughly 2–3× the graphics size free in the project directory.

## 10. Phases

**Phase 0: Spike (prove the approach in-game).** *Status: code done and tested here on your samples; next step is your in-game check.*
Build `pngio`, `color`, the grass/dirt/water/iron/shadow/LUT transforms and `--preview` first, tested here on the sample files you sent. Then you run `build --only` on those categories, copy into the game, and check. This answers:
- Does water respond enough to texture changes?
- Do tile variants and transitions stay seamless?
- Does the shadow opacity change take effect? Does the indigo tint?
- Which LUT files are used at night, dusk and day? (Test with deliberately extreme edits first.)

**Phase 1: Nauvis terrain complete.** All tiles, transitions, decoratives, decals, trees, cliffs, rocks, ores and their particles. Terrain mosaic tuning.

**Phase 2: Entities.** Default entity transform, remnants, then subcategories as needed. Lights and reflections. Enemies (6.4a).

**Phase 3: Icons and technology.** Matched to entities.

**Phase 4: LUT finish.** Final night softness and dusk tint.

**Phase 5 (optional): GUI warm-frame pass and clouds.** Only if they clash after playing with the new world.

Every phase ends with contact sheets and an in-game screenshot set taken at the same spots: starting area, a small smelting setup, a belt line, a water edge, and the same spot at night.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Water color partly set by shader, won't reach cyan | Phase 0 test; push texture harder |
| Seams between tile variants or transitions | Category-wide transforms only; transitions use their tile's transform; terrain mosaic check |
| Readability loss (ores, belt tiers, alerts, pollution) | Explicit distinctness rules; ore-on-terrain mosaic; screenshot checklist |
| Everything pastel turns flat and washed out | Chroma cap tuning, detail gain, darks stay darkest, purple shading |
| Recoloring normal maps or masks breaks lighting or tints | Pass through; these rules come first in `rules.yaml` |
| Missing `.lua` or shader files stops the game from starting | Every non-PNG copied byte-for-byte; validated |
| PNG mode or gamma change alters colors unexpectedly | Mode and metadata preserved and validated |
| Shadow tint ignored by the game | Opacity reduction alone still softens them |
| Day LUT can't be edited | Expected; daytime look comes from sprites |
| Recoloring already-recolored files | Input hashes checked against previous output hashes |
| Unknown or new files after update | Unmatched files fail classification loudly |
| Minimap stays vanilla | Accepted limitation (would need a mod) |

## 12. Decisions log

| # | Decision |
|---|---|
| D1 | Target: Factorio 2.0 base game only. Folders: `data/base/graphics`, `data/core/graphics`. |
| D2 | Pipeline runs on your Mac, using `python3`. |
| D3 | Game world only. GUI stays vanilla; optional warm-frame pass later if it clashes. |
| D4 | Shadows softened: reduced opacity, indigo tint if the game honors it. |
| D5 | Nights softened via the night and dusk LUTs. |
| D6 | Style: pastel, slightly brighter Stardew Valley; between Stardew and Animal Crossing. |
| D7 | CLI has `--preview <filename>` for a single-file before/after comparison. |
| D8 | Pipeline never touches the game install. You copy the two graphics folders into `project_dir/data/`; output goes to `updated_graphics` next to each; you copy back manually. |
| D9 | Normal maps, masks, tintable layers and terrain shader data are never recolored. |
| D10 | PNG mode and metadata are preserved exactly; palette PNGs are recolored through their palette. |
| D11 | Enemies get the pastel treatment too, while staying readable against the terrain. |
| D12 | Signal, fluid, arrow and shortcut icons stay close to vanilla (light pastel pass only). |
| D13 | Ores stay noticeably deeper than the terrain (iron ended up `#7297C8`); a pastel-light first try read as snow and got lost on the grass. |
| D15 | Buildings use the "v2" look: deeper darks (lift floor 0.25, gamma 0.7), about 30% more color, stronger lavender shading, and a kept dark outline. The first version read as faded on the light grass. |
| D16 | After the first in-game test: terrain is right. Everything else (entities, enemies, icons, technology, foliage, wood, rocks, ores) felt too bright and rainbow-like, so those categories now use `strength: 0.5`, halfway between vanilla and the full recolor, blended in OKLab. |
| D17 | Water color is handled by a separate tiny mod, `pastel-water`, which blends the water tiles' `effect_color` toward the palette's cyan (strength and colors are startup mod settings). It's the one exception to the no-mod rule, kept separate so the graphics recolor stays mod-free. The PNG water recolor stays in place but has no visible effect. |
| D18 | Ground grass tufts and small bushes (`decorative/green-*`, `garballo`, 170 files) get their own category, `foliage.ground`. It uses a full-strength color transfer to `#66D37A`, a true vivid green, less lime than the grass (first try `#8FD46E` read as lime), at `strength: 0.6`, with highlights capped (`soft_max: 0.8`) so bright spots stay green, instead of the halfway foliage look, which read too dark in-game. Tree leaves stay in `foliage`. |
| D19 | Grass color is `#A0D680` with hue spread 0.35 (was 0.45): halfway between the first grass `#A5DC8C` (read as a bit lime) and a richer, warmer `#9BD073`. Chosen from side-by-side renders. |
| D20 | Grass uses `per_file_match: 0.7`: each grass sheet is also measured on its own and pulled most of the way to the target, because the four vanilla sheets start from different colors and one of them came out cool and too bright ("puke-slime") under one shared adjustment. |
| D21 | Grass target moved slightly toward yellow: `#A8D57B` (hue 130°, was `#A0D680` at 135°), same lightness and colorfulness. |
| D22 | Sand gets a highlight cap (`soft_max: 0.9`) and a slightly smaller lightness spread (0.85), like the grass tufts, because its very light target left bright grains clipping to white. |
| D14 | Night LUTs: softness 0.2, moon lift 0.25. A first try at 0.35/0.35 made night look like dusk. |

## 13. Open questions

From Phase 0 in-game testing:
- **Water:** a magenta test showed the game doesn't use the water PNGs for color at all. The water shader takes its colors from the tiles' `effect_color` / `effect_color_secondary` in the game's Lua data. See D17.
- Does the shadow tint show, or only the opacity change?
- Which LUT files are active at night and dusk?
- Tree leaves may be tinted by the game at runtime (per-tree color variation). If so, recoloring them green again could double up. To check in Phase 1 with a leaves sample.
