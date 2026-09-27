"""Factorio color lookup tables (core/graphics/color_luts/*.png).

Each file is a 16x16x16 3D LUT stored as a 256x16 RGB image: 16 tiles of
16x16 pixels side by side. Within a tile, red increases left to right and
green top to bottom; blue increases from tile to tile.
"""
import numpy as np
from PIL import Image

from .color import hex_to_rgb255

N = 16


def decode(im):
    """(16,16,16,3) float table indexed [b, g, r], values 0..1."""
    a = np.asarray(im.convert("RGB")).astype(float) / 255.0
    if a.shape != (N, N * N, 3):
        raise ValueError(f"unexpected LUT size {a.shape}")
    return a.reshape(N, N, N, 3).transpose(1, 0, 2, 3)  # [g, b, r] -> [b, g, r]


def encode(table):
    a = table.transpose(1, 0, 2, 3).reshape(N, N * N, 3)
    return Image.fromarray(np.clip(np.round(a * 255), 0, 255).astype(np.uint8), "RGB")


def identity():
    v = np.arange(N) / (N - 1)
    b, g, r = np.meshgrid(v, v, v, indexing="ij")
    return np.stack([r, g, b], axis=-1)


def soften(table, softness=0.0, moon=None, moon_strength=0.0, tint=None, tint_strength=0.0):
    """Make a LUT gentler.

    softness       0..1, blends each output color back toward its input
                   (0 = unchanged, 1 = identity / no grading at all).
    moon           hex color; the darkest outputs are lifted toward it with a
                   screen blend, so night shadows become dim violet, not black.
    moon_strength  0..1 strength of that lift.
    tint, tint_strength   optional multiplicative color cast (e.g. warm dusk).
    """
    ident = identity()
    out = table + softness * (ident - table)
    if tint and tint_strength:
        t = np.array(hex_to_rgb255(tint), dtype=float) / 255
        out = out * (1 - tint_strength + tint_strength * t)
    if moon and moon_strength:
        m = np.array(hex_to_rgb255(moon), dtype=float) / 255 * moon_strength
        out = 1 - (1 - out) * (1 - m)
    return np.clip(out, 0, 1)


def apply(table, rgb):
    """Grade float RGB (...x3, 0..1) through a table with trilinear interpolation."""
    x = np.clip(rgb, 0, 1) * (N - 1)
    i0 = np.floor(x).astype(int)
    i0 = np.minimum(i0, N - 2)
    f = x - i0
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    out = 0
    for db, wb in ((0, 1 - fb), (1, fb)):
        for dg, wg in ((0, 1 - fg), (1, fg)):
            for dr, wr in ((0, 1 - fr), (1, fr)):
                out = out + table[b0 + db, g0 + dg, r0 + dr] * (wb * wg * wr)
    return out


def transform_file(im, file_cfg):
    """Return the softened LUT image, or None to leave the file unchanged."""
    if not file_cfg:
        return None
    table = decode(im)
    new = soften(table,
                 softness=float(file_cfg.get("softness", 0)),
                 moon=file_cfg.get("moon"),
                 moon_strength=float(file_cfg.get("moon_strength", 0)),
                 tint=file_cfg.get("tint"),
                 tint_strength=float(file_cfg.get("tint_strength", 0)))
    return encode(new).convert(im.mode) if im.mode != "RGB" else encode(new)
