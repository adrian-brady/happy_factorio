"""Color transforms.

Category types (set with `type:` in palette.yaml):

  passthrough  File is copied unchanged.
  remap        General transform: lightness lift with detail preservation,
               hue remapping, neutral tinting and chroma shaping.
  transfer     Moves the category's overall color (measured across all files
               in the category) to a target color, keeping the variation
               around it. Used for terrain and ores.
  shadow       Softens opacity and optionally tints.
  lut          Color lookup tables (see lut.py).
"""
import numpy as np
from scipy.ndimage import gaussian_filter

from . import pngio
from .color import (srgb_to_oklab, lab_to_lch, lch_to_srgb_gamut, hex_to_lch,
                    hex_to_rgb255)


def _wrap(d):
    """Wrap hue differences into -180..180."""
    return (d + 180.0) % 360.0 - 180.0


def hue_remap(h, anchors):
    """Piecewise-linear, order-preserving remap of the hue circle.

    anchors: list of [source_hue, target_hue]. Hues between two anchors are
    interpolated; the mapping wraps around the circle.
    """
    if not anchors:
        return h
    a = sorted(([float(s) % 360, float(t)] for s, t in anchors), key=lambda x: x[0])
    if len(a) == 1:
        return (h + _wrap(a[0][1] - a[0][0])) % 360
    src = np.array([x[0] for x in a])
    tgt = np.array([x[1] for x in a])
    # Unwrap targets so consecutive anchors move by their shortest path.
    offs = np.array([_wrap(t - s) for s, t in zip(src, tgt)])
    # Extend with a wrapped copy of the first anchor to close the circle.
    src_ext = np.append(src, src[0] + 360)
    off_ext = np.append(offs, offs[0])
    hh = np.where(h < src[0], h + 360, h)
    off = np.interp(hh, src_ext, off_ext)
    return (h + off) % 360


def soft_max(L, knee):
    """Roll off lightness above `knee` smoothly instead of clipping to white,
    so bright specks keep some color and texture."""
    if knee is None:
        return L
    k = float(knee)
    over = np.maximum(L - k, 0.0)
    return np.where(L > k, k + (1 - k) * (1 - np.exp(-over / (1 - k))), L)


def _weighted_blur(L, alpha, sigma):
    if sigma <= 0:
        return L
    if alpha is None:
        return gaussian_filter(L, sigma, mode="reflect")
    w = alpha
    num = gaussian_filter(L * w, sigma, mode="constant")
    den = gaussian_filter(w, sigma, mode="constant")
    out = np.where(den > 1e-4, num / np.maximum(den, 1e-4), L)
    return out


def remap_lch(L, C, h, alpha, p, g, image_shaped=True):
    """The general 'remap' transform on OKLCH arrays."""
    brightness = float(g.get("brightness", 1.0))
    saturation = float(g.get("saturation", 1.0))

    # 1. Lightness lift, applied to a blurred base; local detail added back.
    lift = p.get("lift", {})
    det = p.get("detail", {})
    sigma = float(det.get("sigma", 0)) if image_shaped else 0.0
    gain = float(det.get("gain", 1.0))
    L_base = _weighted_blur(L, alpha, sigma)

    # Smooth the color (not the lightness) a little before remapping, so
    # grain in grayish areas doesn't turn into rainbow speckles once chroma
    # is boosted. Gives cleaner, flatter, more cartoon-like color areas.
    cb = float(det.get("color_blur", 0)) if image_shaped else 0.0
    if cb > 0:
        from .color import lch_to_lab
        lab = lch_to_lab(L, C, h)
        a = _weighted_blur(lab[..., 1], alpha, cb)
        b = _weighted_blur(lab[..., 2], alpha, cb)
        C = np.hypot(a, b)
        h = np.degrees(np.arctan2(b, a)) % 360.0
    floor = float(lift.get("floor", 0.0))
    ceil = float(lift.get("ceil", 1.0))
    gamma = float(lift.get("gamma", 1.0))
    lifted = floor + (ceil - floor) * np.power(np.clip(L_base, 0, 1), gamma)
    lifted = L_base + brightness * (lifted - L_base)
    L2 = np.clip(lifted + gain * (L - L_base), 0.0, 1.0)

    # 1b. Outline: near the sprite's edge (where it meets transparency), pull
    #     lightness back toward the original dark contour, so the silhouette
    #     stays crisp against light ground instead of fading into it.
    ol = p.get("outline")
    if ol and alpha is not None and image_shaped:
        width = float(ol.get("width", 2.0))
        solid = (alpha > 0.5).astype(float)
        edge = np.clip((1.0 - gaussian_filter(solid, width, mode="constant")) * 2.0, 0.0, 1.0) * solid
        L2 = L2 + edge * float(ol.get("strength", 0.6)) * (np.minimum(L, L2) - L2)

    # 2. Hue remap. Optionally only for muted colors, so saturated accents
    #    (belt yellow, inserter blue) keep their hue while drab panels shift.
    h2 = hue_remap(h, p.get("hue_anchors"))
    rng = p.get("hue_chroma_range")
    if rng:
        lo, hi = float(rng[0]), float(rng[1])
        w = np.clip((hi - C) / max(hi - lo, 1e-6), 0.0, 1.0)
        h2 = (h + w * _wrap(h2 - h)) % 360

    # 3. Neutral tint: near-gray pixels pick up a category hue.
    C2 = C.copy()
    neu = p.get("neutral")
    if neu:
        below = float(neu.get("chroma_below", 0.03))
        w = np.clip(1.0 - C / below, 0.0, 1.0)
        nh = float(neu.get("hue", 0.0))
        h2 = (h2 + w * _wrap(nh - h2)) % 360
        C2 = C2 + w * float(neu.get("chroma", 0.02))

    # 3b. Cartoon shading: the originally dark areas lean toward a cool
    #     shade hue (lavender) instead of reading as gray-black once lifted.
    sh = p.get("shade")
    if sh:
        below = float(sh.get("below", 0.35))
        w = np.clip((below - L_base) / below, 0.0, 1.0) * float(sh.get("strength", 0.6))
        h2 = (h2 + w * _wrap(float(sh.get("hue", 290)) - h2)) % 360
        C2 = C2 + w * float(sh.get("chroma", 0.03))

    # 4. Chroma shaping.
    ch = p.get("chroma", {})
    C2 = C2 * float(ch.get("scale", 1.0)) + float(ch.get("add", 0.0))
    C2 = np.minimum(C2, float(ch.get("max", 0.4)))
    C2 = np.maximum(C2, 0.0) * saturation
    return L2, C2, h2


def transfer_lch(L, C, h, p, g, stats):
    """The 'transfer' transform: move the category's median color to a target."""
    brightness = float(g.get("brightness", 1.0))
    saturation = float(g.get("saturation", 1.0))
    tL, tC, tH = hex_to_lch(p["target"])
    sL, sC, sH = stats["L"], stats["C"], stats["h"]
    tL = sL + brightness * (tL - sL)
    sp = p.get("spread", {})
    L2 = tL + (L - sL) * float(sp.get("L", 1.0))
    L2 = soft_max(L2, p.get("soft_max"))
    C2 = np.maximum(tC + (C - sC) * float(sp.get("C", 1.0)), 0.0) * saturation
    C2 = np.minimum(C2, float(p.get("chroma_max", 0.4)))
    h2 = (tH + _wrap(h - sH) * float(sp.get("h", 1.0))) % 360
    # Optional fine hue remap after the transfer (e.g. push patches apart).
    h2 = hue_remap(h2, p.get("hue_anchors"))
    return np.clip(L2, 0, 1), C2, h2


def recolor_rgb(rgb, alpha, cat, g, stats=None, image_shaped=True):
    """Recolor float RGB (…x3) with alpha (… or None) according to a category."""
    lab = srgb_to_oklab(rgb)
    L, C, h = lab_to_lch(lab)
    if cat["type"] == "remap":
        L2, C2, h2 = remap_lch(L, C, h, alpha, cat, g, image_shaped)
    elif cat["type"] == "transfer":
        L2, C2, h2 = transfer_lch(L, C, h, cat, g, stats)
    else:
        raise ValueError(cat["type"])
    # strength: 1 = full recolor, 0 = original, 0.5 = halfway. Blended in OKLab,
    # so halfway is a perceptually even mix of the original and the new color.
    s = float(cat.get("strength", 1.0))
    if s != 1.0:
        from .color import lch_to_lab
        mixed = lab + s * (lch_to_lab(L2, C2, h2) - lab)
        L2, C2, h2 = lab_to_lch(mixed)
    return lch_to_srgb_gamut(L2, C2, h2)


def shadow_image(im, cat):
    """Soften a shadow sprite: scale alpha, set RGB to the tint color."""
    scale = float(cat.get("alpha_scale", 0.6))
    tint = cat.get("tint")
    tint_rgb = np.array(hex_to_rgb255(tint), dtype=float) / 255 if tint else None

    def soften(a):
        # Scale opacity, but never turn a visible pixel fully invisible,
        # so the shadow's shape stays exactly the same.
        return np.where(a > 0, np.maximum(a * scale, 1 / 255), 0.0)

    if im.mode == "P":
        pal, pal_a = pngio.palette_arrays(im)
        if tint_rgb is not None:
            pal = np.where(pal_a[:, None] > 0, tint_rgb[None, :], pal)
        return pngio.rebuild_palette(im, pal, soften(pal_a))
    if im.mode in ("RGBA", "LA"):
        rgb, a = pngio.to_arrays(im)
        if tint_rgb is not None and im.mode == "RGBA":
            rgb = np.where(a[..., None] > 0, tint_rgb, rgb)
        return pngio.from_arrays(im.mode, rgb, soften(a))
    return None  # no alpha to soften: leave unchanged


def _color_key_mask(im, rgb):
    """Pixels matching an RGB/L tRNS color key must keep their exact value."""
    key = im.info.get("transparency")
    if key is None or im.mode not in ("RGB", "L"):
        return None
    a = np.asarray(im)
    if im.mode == "RGB" and isinstance(key, tuple):
        return np.all(a == np.array(key, dtype=a.dtype), axis=-1)
    if im.mode == "L" and isinstance(key, int):
        return a == key
    return None


def recolor_image(im, cat, g, stats=None):
    """Return the recolored image, or None if the file should be copied unchanged."""
    t = cat["type"]
    if t == "passthrough" or im.mode not in pngio.SUPPORTED_MODES:
        return None
    if t == "shadow":
        return shadow_image(im, cat)
    if t not in ("remap", "transfer"):
        raise ValueError(f"recolor_image cannot apply type {t}")

    if im.mode == "P":
        pal, pal_a = pngio.palette_arrays(im)
        if len(pal) == 0:
            return None
        new = recolor_rgb(pal, pal_a, cat, g, stats, image_shaped=False)
        new = np.where(pal_a[:, None] > 0, new, pal)
        return pngio.rebuild_palette(im, new, pal_a)

    rgb, alpha = pngio.to_arrays(im)
    new = recolor_rgb(rgb, alpha, cat, g, stats)
    keep = alpha == 0 if alpha is not None else None
    key = _color_key_mask(im, rgb)
    if key is not None:
        keep = key if keep is None else (keep | key)
    if keep is not None:
        new = np.where(keep[..., None], rgb, new)
    return pngio.from_arrays(im.mode, new, alpha)


def color_stats(rgba_list, max_pixels=400_000):
    """Median OKLCH of the opaque pixels across a list of RGBA uint8 arrays."""
    per = max(1, max_pixels // max(1, len(rgba_list)))
    samples = []
    rng = np.random.default_rng(0)
    for a in rgba_list:
        px = a.reshape(-1, 4)
        px = px[px[:, 3] > 230][:, :3]
        if len(px) > per:
            px = px[rng.choice(len(px), per, replace=False)]
        samples.append(px)
    px = np.concatenate(samples) if samples else np.zeros((0, 3))
    if len(px) == 0:
        return {"L": 0.5, "C": 0.0, "h": 0.0, "n": 0}
    lab = srgb_to_oklab(px.astype(float) / 255)
    L, C, _ = lab_to_lch(lab)
    h = float(np.degrees(np.arctan2(lab[:, 2].mean(), lab[:, 1].mean())) % 360)
    return {"L": float(np.median(L)), "C": float(np.median(C)), "h": h, "n": int(len(px))}
