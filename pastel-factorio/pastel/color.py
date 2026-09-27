"""Vectorized sRGB <-> OKLab / OKLCH conversion and gamut mapping.

All functions take and return float arrays with a trailing axis of 3.
sRGB values are in 0..1.
"""
import numpy as np

_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])
_M2_INV = np.linalg.inv(_M2)
_M1_INV = np.linalg.inv(_M1)


def _mat3(x, M):
    """x (...x3) times the 3x3 matrix M, row by row: out[..., i] = sum_j M[i, j] * x[..., j].

    Written as plain element-wise arithmetic instead of `x @ M.T` on purpose:
    matmul hands large arrays to the system BLAS library, and some macOS
    numpy builds crash (segmentation fault) there on multi-megapixel images.
    """
    x0, x1, x2 = x[..., 0], x[..., 1], x[..., 2]
    return np.stack([M[i, 0] * x0 + M[i, 1] * x1 + M[i, 2] * x2 for i in range(3)], axis=-1)


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0.0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def srgb_to_oklab(rgb):
    lms = _mat3(srgb_to_linear(rgb), _M1)
    return _mat3(np.cbrt(lms), _M2)


def oklab_to_linear(lab):
    lms = _mat3(lab, _M2_INV) ** 3
    return _mat3(lms, _M1_INV)


def oklab_to_srgb(lab):
    return linear_to_srgb(oklab_to_linear(lab))


def lab_to_lch(lab):
    L = lab[..., 0]
    C = np.hypot(lab[..., 1], lab[..., 2])
    h = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360.0
    return L, C, h


def lch_to_lab(L, C, h):
    hr = np.radians(h)
    return np.stack([L, C * np.cos(hr), C * np.sin(hr)], axis=-1)


def lch_to_srgb_gamut(L, C, h, iters=14):
    """Convert OKLCH to sRGB, pulling out-of-gamut colors back by reducing chroma.

    Lightness and hue are kept exactly; only chroma is lowered (binary search),
    so colors never shift hue the way plain RGB clipping would.
    """
    L = np.clip(L, 0.0, 1.0)
    lin = oklab_to_linear(lch_to_lab(L, C, h))
    eps = 1e-4
    bad = np.any((lin < -eps) | (lin > 1 + eps), axis=-1)
    if np.any(bad):
        Lb, Cb, hb = L[bad], C[bad], h[bad]
        lo = np.zeros_like(Cb)
        hi = Cb.copy()
        for _ in range(iters):
            mid = (lo + hi) / 2
            lb = oklab_to_linear(lch_to_lab(Lb, mid, hb))
            ok = np.all((lb >= -eps) & (lb <= 1 + eps), axis=-1)
            lo = np.where(ok, mid, lo)
            hi = np.where(ok, hi, mid)
        C = C.copy()
        C[bad] = lo
        lin = oklab_to_linear(lch_to_lab(L, C, h))
    return np.clip(linear_to_srgb(np.clip(lin, 0, 1)), 0.0, 1.0)


def hex_to_lch(hexstr):
    hexstr = hexstr.lstrip('#')
    rgb = np.array([int(hexstr[i:i + 2], 16) for i in (0, 2, 4)], dtype=float) / 255.0
    L, C, h = lab_to_lch(srgb_to_oklab(rgb[None, :]))
    return float(L[0]), float(C[0]), float(h[0])


def hex_to_rgb255(hexstr):
    hexstr = hexstr.lstrip('#')
    return tuple(int(hexstr[i:i + 2], 16) for i in (0, 2, 4))


def hsv_card(w, h):
    """Test image: hues left to right; from light at the top, through full
    color, to dark at the bottom. Float RGB (h, w, 3)."""
    hue = np.linspace(0, 1, w, endpoint=False)[None, :].repeat(h, 0)
    t = np.linspace(0, 1, h)[:, None].repeat(w, 1)
    s = np.clip(t * 2, 0, 1)
    v = np.clip(2 - t * 2, 0, 1) * 0.95 + 0.05
    i = np.floor(hue * 6).astype(int) % 6
    f = hue * 6 - np.floor(hue * 6)
    p, q, u = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, u, v])
    g = np.choose(i, [u, v, v, q, p, p])
    b = np.choose(i, [p, p, u, v, v, q])
    return np.stack([r, g, b], axis=-1)
