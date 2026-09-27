"""The project on disk: finding source files, category statistics, and
recoloring a single file. Used by build, preview and validate."""
import hashlib
import json
from pathlib import Path

from . import lut as lutmod
from . import pngio
from .config import Config, glob_to_regex
from .transforms import color_stats, recolor_image

SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
STATS_VERSION = 1

# Files used to measure a 'transfer' category's median color, unless the
# category sets `stats_from`. Decals, particles and transition sheets are
# excluded so they don't skew the measurement; they are still recolored.
_DEFAULT_STATS_EXCLUDE = glob_to_regex("{**/decorative/**,**/particle/**,**/*-transition*/**}")


class Project:
    def __init__(self, root="."):
        self.root = Path(root).resolve()
        self.data = self.root / "data"
        self.build_dir = self.root / "build"
        self.cfg = Config(self.root)
        self._files = None
        self._stats = {}

    # -- files ------------------------------------------------------------
    def source_roots(self):
        """Every data/<folder>/graphics directory."""
        if not self.data.is_dir():
            raise SystemExit(f"No data folder found at {self.data}.\n"
                             "Copy the game's data/base/graphics and data/core/graphics into it first.")
        roots = sorted(p for p in self.data.glob("*/graphics") if p.is_dir())
        if not roots:
            raise SystemExit(f"No graphics folders found under {self.data} "
                             "(expected data/base/graphics and data/core/graphics).")
        return roots

    def all_files(self):
        """All source files as paths relative to data/, e.g. base/graphics/x.png."""
        if self._files is None:
            files = []
            for r in self.source_roots():
                for p in r.rglob("*"):
                    if p.is_file() and p.name not in SKIP_NAMES:
                        files.append(p.relative_to(self.data).as_posix())
            self._files = sorted(files)
        return self._files

    def pngs(self):
        return [f for f in self.all_files() if f.lower().endswith(".png")]

    def src_path(self, rel):
        return self.data / rel

    def out_path(self, rel):
        parts = rel.split("/")
        assert parts[1] == "graphics", rel
        parts[1] = "updated_graphics"
        return self.data.joinpath(*parts)

    # -- category statistics (for 'transfer' categories) -------------------
    def stats_for(self, category):
        cat = self.cfg.category(category)
        if cat["type"] != "transfer":
            return None
        if category in self._stats:
            return self._stats[category]
        members = [f for f in self.pngs() if self.cfg.classify(f) == category]
        chosen = [f for f in members if self.is_stats_source(category, f)] or members
        sig = hashlib.sha1(json.dumps(
            [STATS_VERSION] + [(f, self.src_path(f).stat().st_size, int(self.src_path(f).stat().st_mtime))
                               for f in chosen]).encode()).hexdigest()
        cache_file = self.build_dir / "stats.json"
        cache = {}
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text())
            except json.JSONDecodeError:
                cache = {}
        hit = cache.get(category)
        if hit and hit.get("sig") == sig:
            stats = hit["stats"]
        else:
            arrays = []
            for f in chosen:
                try:  # skip empty/damaged files; they're copied through unchanged
                    arrays.append(pngio.to_rgba_display(pngio.open_png(self.src_path(f))))
                except Exception:
                    pass
            stats = color_stats(arrays)
            stats["files"] = len(chosen)
            cache[category] = {"sig": sig, "stats": stats}
            self.build_dir.mkdir(exist_ok=True)
            cache_file.write_text(json.dumps(cache, indent=1, sort_keys=True))
        self._stats[category] = stats
        return stats

    def is_stats_source(self, category, rel):
        """Is this file one of the main tile sheets used to measure the category?
        (Decals, particles and transition sheets are not.)"""
        cat = self.cfg.category(category)
        if cat.get("stats_from"):
            return bool(glob_to_regex(cat["stats_from"]).match(rel))
        return not _DEFAULT_STATS_EXCLUDE.match(rel)

    def stats_for_file(self, category, rel, im):
        """Stats used to recolor one file.

        Normally the category-wide stats. With `per_file_match: m` (0..1), each
        main tile sheet is also measured on its own and its measured color moves
        m of the way from the category average toward its own average. The
        result: every sheet's own average lands close to the target color (at
        m = 1 exactly on it), so sheets that start out cooler or yellower than
        the others no longer end up standing out.
        """
        base = self.stats_for(category)
        cat = self.cfg.category(category)
        m = float(cat.get("per_file_match", 0) or 0)
        if base is None or m <= 0 or not self.is_stats_source(category, rel):
            return base
        own = color_stats([pngio.to_rgba_display(im)])
        if own.get("n", 0) == 0:
            return base
        dh = (own["h"] - base["h"] + 180.0) % 360.0 - 180.0
        return {"L": base["L"] + m * (own["L"] - base["L"]),
                "C": base["C"] + m * (own["C"] - base["C"]),
                "h": (base["h"] + m * dh) % 360.0}

    # -- recoloring one file ---------------------------------------------
    def recolor(self, rel, category=None, im=None):
        """Recolored PIL image for a source PNG, or None if it stays unchanged."""
        category = category or self.cfg.classify(rel)
        if category is None:
            raise KeyError(f"no rule in rules.yaml matches {rel}")
        cat = self.cfg.category(category)
        im = im or pngio.open_png(self.src_path(rel))
        if cat["type"] == "lut":
            return lutmod.transform_file(im, cat.get("files", {}).get(Path(rel).name))
        return recolor_image(im, cat, self.cfg.globals, self.stats_for_file(category, rel, im))
