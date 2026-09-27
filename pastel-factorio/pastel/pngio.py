"""PNG reading and writing that preserves the file's color mode and metadata.

Factorio's PNGs come in several modes (RGBA, RGB, palette with tRNS alpha,
grayscale) and many carry a gAMA chunk. The recolored file must keep all of
that, so the game decodes it exactly as it did the original.
"""
import struct

import numpy as np
from PIL import Image, PngImagePlugin

# Modes the transforms know how to handle. Anything else is passed through.
SUPPORTED_MODES = {"RGBA", "RGB", "LA", "L", "P"}


def open_png(path):
    im = Image.open(path)
    im.load()
    return im


def metadata_signature(im):
    """The metadata that must survive recoloring, as a comparable dict."""
    info = im.info
    return {
        "mode": im.mode,
        "size": im.size,
        "gamma": info.get("gamma"),
        "srgb": info.get("srgb"),
        "icc": info.get("icc_profile") is not None,
    }


def save_like(new_im, original, path):
    """Save new_im to path with the original's mode-related options and metadata."""
    info = original.info
    pnginfo = PngImagePlugin.PngInfo()
    if info.get("gamma") is not None:
        pnginfo.add(b"gAMA", struct.pack(">I", int(round(info["gamma"] * 100000))))
    if info.get("srgb") is not None:
        pnginfo.add(b"sRGB", bytes([int(info["srgb"])]))
    kwargs = {"pnginfo": pnginfo, "optimize": False, "compress_level": 9}
    if info.get("icc_profile"):
        kwargs["icc_profile"] = info["icc_profile"]
    # tRNS: palette alpha table, or a single transparent color for RGB / L.
    # For palette images the caller may have replaced it; prefer new_im's.
    trans = new_im.info.get("transparency", info.get("transparency"))
    if trans is not None:
        kwargs["transparency"] = trans
    if info.get("dpi"):
        kwargs["dpi"] = info["dpi"]
    new_im.save(path, "PNG", **kwargs)


# ---------------------------------------------------------------------------
# Array views. Each returns (rgb float HxWx3 in 0..1, alpha float HxW in 0..1)
# and a function to rebuild an image of the same mode from new arrays.
# ---------------------------------------------------------------------------

def palette_arrays(im):
    """For a 'P' image: palette as (N,3) floats and per-entry alpha (N,) floats."""
    pal = np.array(im.getpalette() or [], dtype=np.uint8).reshape(-1, 3)
    n = len(pal)
    alpha = np.full(n, 255, dtype=np.uint8)
    trans = im.info.get("transparency")
    if isinstance(trans, (bytes, bytearray)):
        t = np.frombuffer(bytes(trans), dtype=np.uint8)[:n]
        alpha[: len(t)] = t
    elif isinstance(trans, int) and trans < n:
        alpha[trans] = 0
    return pal.astype(float) / 255.0, alpha.astype(float) / 255.0


def rebuild_palette(im, pal_rgb, pal_alpha):
    """New 'P' image with the same index data and a replaced palette/tRNS."""
    out = im.copy()
    pal = np.clip(np.round(pal_rgb * 255), 0, 255).astype(np.uint8)
    out.putpalette(pal.reshape(-1).tolist())
    orig_trans = im.info.get("transparency")
    if orig_trans is not None or np.any(pal_alpha < 1):
        a = np.clip(np.round(pal_alpha * 255), 0, 255).astype(np.uint8)
        if isinstance(orig_trans, (bytes, bytearray)):
            a = a[: len(orig_trans)]  # keep the tRNS table the same length
        out.info["transparency"] = bytes(a.tolist())
    return out


def to_arrays(im):
    """RGB and alpha arrays for RGBA / RGB / LA / L images."""
    a = np.asarray(im)
    if im.mode == "RGBA":
        return a[..., :3].astype(float) / 255.0, a[..., 3].astype(float) / 255.0
    if im.mode == "RGB":
        return a.astype(float) / 255.0, None
    if im.mode == "LA":
        g = a[..., 0].astype(float) / 255.0
        return np.repeat(g[..., None], 3, axis=-1), a[..., 1].astype(float) / 255.0
    if im.mode == "L":
        g = a.astype(float) / 255.0
        return np.repeat(g[..., None], 3, axis=-1), None
    raise ValueError(f"to_arrays does not handle mode {im.mode}")


def from_arrays(mode, rgb, alpha):
    """Build an image of `mode` from float arrays."""
    rgb8 = np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8)
    a8 = None if alpha is None else np.clip(np.round(alpha * 255), 0, 255).astype(np.uint8)
    if mode == "RGBA":
        return Image.fromarray(np.dstack([rgb8, a8]), "RGBA")
    if mode == "RGB":
        return Image.fromarray(rgb8, "RGB")
    # Grayscale: use Rec. 709 luma of the recolored result.
    g = np.clip(np.round((rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722) * 255),
                0, 255).astype(np.uint8)
    if mode == "LA":
        return Image.fromarray(np.dstack([g, a8]), "LA")
    if mode == "L":
        return Image.fromarray(g, "L")
    raise ValueError(f"from_arrays does not handle mode {mode}")


def to_rgba_display(im):
    """Any image as an RGBA uint8 array, for previews and statistics."""
    return np.asarray(im.convert("RGBA"))
