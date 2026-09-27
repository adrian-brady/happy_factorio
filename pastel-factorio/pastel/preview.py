"""--preview: recolor one file in memory and show before and after together."""
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import lut as lutmod
from . import pngio
from .color import hex_to_rgb255, hsv_card

TARGET_WIDTH = 1600
CAPTION_H = 30
LABEL_H = 24
GAP = 12


def find_matches(project, query):
    """Exact filename matches first; otherwise substring matches on the path."""
    q = query.lower().replace("\\", "/")
    files = project.pngs()
    exact = [f for f in files if Path(f).name.lower() == q or f.lower() == q or f.lower().endswith("/" + q)]
    if exact:
        return exact
    return [f for f in files if q in f.lower()]


def choose(project, query, pick):
    matches = find_matches(project, query)
    if not matches:
        raise SystemExit(f"No PNG under data/*/graphics matches '{query}'.")
    if len(matches) == 1:
        return matches[0]
    if pick is not None:
        if not 1 <= pick <= len(matches):
            raise SystemExit(f"--pick {pick} is out of range (1-{len(matches)}).")
        return matches[pick - 1]
    print(f"{len(matches)} files match '{query}':")
    for i, f in enumerate(matches[:200], 1):
        print(f"  {i:3d}. {f}   [{project.cfg.classify(f)}]")
    if len(matches) > 200:
        print(f"  ... and {len(matches) - 200} more; type more of the name to narrow it down.")
    if not sys.stdin.isatty():
        raise SystemExit("Several matches; rerun with --pick N.")
    while True:
        ans = input("Which one? (number, or Enter to cancel) ").strip()
        if not ans:
            raise SystemExit(0)
        if ans.isdigit() and 1 <= int(ans) <= min(len(matches), 200):
            return matches[int(ans) - 1]


# ---------------------------------------------------------------------------

def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def _checker(w, h, s=8):
    y, x = np.mgrid[0:h, 0:w]
    c = (((x // s) + (y // s)) % 2).astype(np.uint8)
    a = np.where(c[..., None] == 1, 204, 244).astype(np.uint8)
    return Image.fromarray(np.repeat(a, 3, axis=2), "RGB")


def _background(kind, w, h, project):
    if kind == "checker":
        return _checker(w, h)
    color = {"light": "#F4F1EA", "dark": "#2A2833"}.get(kind)
    if kind == "grass":
        color = project.cfg.colors.get("grass", "#A8E39A")
    if color is None:
        raise SystemExit(f"unknown --bg '{kind}' (use checker, grass, light or dark)")
    return Image.new("RGB", (w, h), hex_to_rgb255(color))


def _lut_card(project):
    """A test image for LUT previews: hue/lightness sweep, gray ramp, and the
    new world's palette colors as swatches, so you see the pastel world at night."""
    card = hsv_card(512, 160)
    ramp = np.repeat(np.linspace(0, 1, 512)[None, :, None], 3, axis=2)
    ramp = np.repeat(ramp, 24, axis=0)
    names = [n for n in ("grass", "dirt", "sand", "water", "deepwater", "iron", "copper",
                         "coal", "stone", "uranium", "concrete") if n in project.cfg.colors]
    sw = np.zeros((56, 512, 3))
    if names:
        wcell = 512 // len(names)
        for i, n in enumerate(names):
            sw[:, i * wcell:(i + 1) * wcell] = np.array(hex_to_rgb255(project.cfg.colors[n])) / 255
    return np.concatenate([card, ramp, sw], axis=0)


def _parse_crop(s):
    try:
        x, y, w, h = (int(v) for v in s.split(","))
        return x, y, w, h
    except ValueError:
        raise SystemExit("--crop needs x,y,w,h, e.g. --crop 0,320,256,256")


def render(project, rel, args):
    """Build the side-by-side comparison image for one file."""
    cfg = project.cfg
    category = cfg.classify(rel)
    cat = cfg.category(category)
    try:
        src = pngio.open_png(project.src_path(rel))
    except Exception:
        raise SystemExit(f"{rel} isn't a readable image (it may be an empty placeholder file); "
                         "the build copies it unchanged.")
    note = ""

    if cat["type"] == "lut":
        file_cfg = cat.get("files", {}).get(Path(rel).name)
        card = _lut_card(project)
        old_t = lutmod.decode(src)
        before = lutmod.apply(old_t, card)
        new_t = lutmod.soften(old_t, **_lut_kwargs(file_cfg)) if file_cfg else old_t
        after = lutmod.apply(new_t, card)
        to_img = lambda a: Image.fromarray(np.clip(np.round(a * 255), 0, 255).astype(np.uint8), "RGB").convert("RGBA")
        before, after = to_img(before), to_img(after)
        note = "test card graded by the LUT" + ("" if file_cfg else " (not listed in palette.yaml: unchanged)")
        bg = "dark"
    else:
        new = project.recolor(rel, category, src)
        if new is None:
            note = "unchanged (passthrough)" if cat["type"] == "passthrough" else f"unchanged (mode {src.mode})"
            new = src
        before = src.convert("RGBA")
        after = new.convert("RGBA")
        bg = args.bg or ("grass" if cat["type"] == "shadow" else "checker")
        if cat["type"] == "shadow":
            note = "shown over the new grass color"

    if args.crop:
        x, y, w, h = _parse_crop(args.crop)
        before = before.crop((x, y, x + w, y + h))
        after = after.crop((x, y, x + w, y + h))
    if args.tile and args.tile > 1:
        before, after = _tile(before, args.tile), _tile(after, args.tile)

    return _compose(project, rel, category, src, before, after, bg, args.zoom, note)


def _lut_kwargs(fc):
    return {"softness": float(fc.get("softness", 0)), "moon": fc.get("moon"),
            "moon_strength": float(fc.get("moon_strength", 0)), "tint": fc.get("tint"),
            "tint_strength": float(fc.get("tint_strength", 0))}


def _tile(im, n):
    out = Image.new("RGBA", (im.width * n, im.height * n))
    for i in range(n):
        for j in range(n):
            out.paste(im, (i * im.width, j * im.height))
    return out


def _compose(project, rel, category, src, before, after, bg, zoom, note):
    w, h = before.size
    stacked = w > 1.4 * h  # wide sheets go one above the other
    if zoom:
        scale = float(zoom)
    else:
        avail = TARGET_WIDTH if stacked else (TARGET_WIDTH - GAP) / 2
        scale = min(avail / w, 900 / h if not stacked else 420 / h)
        if scale > 1:
            scale = max(1, int(scale))  # integer upscale keeps pixels crisp
    sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
    resample = Image.NEAREST if scale >= 1 else Image.LANCZOS

    def panel(im, label):
        im = im.resize((sw, sh), resample)
        base = _background(bg, sw, sh, project).convert("RGBA")
        base.alpha_composite(im)
        p = Image.new("RGB", (sw, sh + LABEL_H), (32, 30, 40))
        p.paste(base.convert("RGB"), (0, LABEL_H))
        ImageDraw.Draw(p).text((6, 4), label, fill=(235, 235, 240), font=_font(15))
        return p

    pb, pa = panel(before, "BEFORE"), panel(after, "AFTER")
    if stacked:
        W, H = sw, 2 * pb.height + GAP
        pos = [(0, 0), (0, pb.height + GAP)]
    else:
        W, H = 2 * sw + GAP, pb.height
        pos = [(0, 0), (sw + GAP, 0)]
    W = max(W, 700)
    out = Image.new("RGB", (W, H + CAPTION_H), (32, 30, 40))
    out.paste(pb, (pos[0][0], pos[0][1] + CAPTION_H))
    out.paste(pa, (pos[1][0], pos[1][1] + CAPTION_H))
    cap = f"{rel}   [{category}]   {src.size[0]}x{src.size[1]} {src.mode}"
    if note:
        cap += f"   ({note})"
    ImageDraw.Draw(out).text((6, 7), cap, fill=(255, 225, 150), font=_font(15))
    return out


def open_file(path):
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def run(project, args):
    rel = choose(project, args.preview, args.pick)
    out_dir = project.build_dir / "preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (Path(rel).stem + "_preview.png")

    def once():
        t = time.time()
        img = render(project, rel, args)
        img.save(out_path)
        print(f"{rel} -> {out_path.relative_to(project.root)}  ({time.time() - t:.1f}s)")

    once()
    if not args.no_open:
        open_file(out_path)
    if not args.watch:
        return
    print("Watching config/palette.yaml and config/rules.yaml. Ctrl+C to stop.")
    last = project.cfg.mtimes()
    try:
        while True:
            time.sleep(0.5)
            now = project.cfg.mtimes()
            if now == last:
                continue
            last = now
            try:
                project.cfg.reload()
                project._stats.clear()
                once()
            except Exception as e:  # keep watching through config typos
                print(f"  config error: {e}")
    except KeyboardInterrupt:
        print()
