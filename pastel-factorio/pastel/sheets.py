"""Contact sheets: before/after thumbnails for a whole category at once."""
import fnmatch

from PIL import Image, ImageDraw

from . import pngio
from .preview import _checker, _font

THUMB = 150


def _thumb(im):
    im = im.convert("RGBA")
    im.thumbnail((THUMB, THUMB), Image.LANCZOS)
    base = _checker(THUMB, THUMB, 6).convert("RGBA")
    base.alpha_composite(im, ((THUMB - im.width) // 2, (THUMB - im.height) // 2))
    return base.convert("RGB")


def cmd_sheets(p, args):
    """Needs a finished build: compares data/*/graphics with updated_graphics."""
    wanted = args.category or "*"
    groups = {}
    for f in p.pngs():
        c = p.cfg.classify(f)
        if c and c != "passthrough" and fnmatch.fnmatchcase(c, wanted):
            groups.setdefault(c, []).append(f)
    if not groups:
        raise SystemExit(f"No recolored categories match '{wanted}'.")
    out_dir = p.build_dir / "sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    for c, files in sorted(groups.items()):
        files = files[: args.limit]
        cols = 4                                    # 4 before/after pairs per row
        rows = (len(files) + cols - 1) // cols
        cell_w, cell_h = 2 * THUMB + 6, THUMB + 20
        sheet = Image.new("RGB", (cols * (cell_w + 12), rows * (cell_h + 8) + 30), (32, 30, 40))
        d = ImageDraw.Draw(sheet)
        d.text((8, 8), f"{c}: {len(files)} file(s), each shown before | after", fill=(255, 225, 150), font=_font(15))
        missing = 0
        for i, f in enumerate(files):
            x = (i % cols) * (cell_w + 12) + 6
            y = (i // cols) * (cell_h + 8) + 30
            out = p.out_path(f)
            if not out.exists():
                missing += 1
                continue
            sheet.paste(_thumb(pngio.open_png(p.src_path(f))), (x, y))
            sheet.paste(_thumb(pngio.open_png(out)), (x + THUMB + 6, y))
            name = f.rsplit("/", 1)[-1]
            d.text((x, y + THUMB + 3), name[:40], fill=(210, 210, 220), font=_font(11))
        path = out_dir / f"{c}.png"
        sheet.save(path)
        note = f" ({missing} not built yet)" if missing else ""
        print(f"{path.relative_to(p.root)}{note}")
