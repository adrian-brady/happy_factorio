"""Loading rules.yaml and palette.yaml, and classifying files into categories."""
import copy
import fnmatch
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

SPECIAL_TYPES = {"passthrough", "remap", "transfer", "shadow", "lut"}


def glob_to_regex(pattern):
    """Glob with ** (any depth), * (within a folder), ? and {a,b} alternatives."""
    return re.compile("^" + _glob_body(pattern) + "$", re.IGNORECASE)


def _glob_body(pattern):
    i, out = 0, []
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "{":
            j = pattern.index("}", i)
            alts = pattern[i + 1:j].split(",")
            out.append("(?:" + "|".join(_glob_body(a) for a in alts) + ")")
            i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


class Config:
    def __init__(self, root):
        self.root = Path(root)
        self.rules_path = self.root / "config" / "rules.yaml"
        self.palette_path = self.root / "config" / "palette.yaml"
        self.reload()

    def reload(self):
        rules = yaml.safe_load(self.rules_path.read_text()) or []
        self.rules = [(r["match"], glob_to_regex(r["match"]), r["category"]) for r in rules]
        pal = yaml.safe_load(self.palette_path.read_text()) or {}
        self.globals = pal.get("global", {})
        self.colors = pal.get("colors", {})
        self.raw_categories = pal.get("categories", {})
        self._resolved = {}
        self.check()

    def mtimes(self):
        return (self.rules_path.stat().st_mtime, self.palette_path.stat().st_mtime)

    # -- categories -----------------------------------------------------
    def category(self, name):
        """Category settings with `inherit:` resolved and named colors expanded."""
        if name in self._resolved:
            return self._resolved[name]
        if name not in self.raw_categories:
            raise KeyError(f"category '{name}' is used in rules.yaml but not defined in palette.yaml")
        raw = copy.deepcopy(self.raw_categories[name])
        parent = raw.pop("inherit", None)
        cat = _deep_merge(copy.deepcopy(self.category(parent)), raw) if parent else raw
        cat = self._expand_colors(cat)
        if cat.get("type") not in SPECIAL_TYPES:
            raise ValueError(f"category '{name}' has unknown type {cat.get('type')!r}")
        self._resolved[name] = cat
        return cat

    def _expand_colors(self, v):
        if isinstance(v, dict):
            return {k: self._expand_colors(x) for k, x in v.items()}
        if isinstance(v, list):
            return [self._expand_colors(x) for x in v]
        if isinstance(v, str) and v.startswith("$"):
            key = v[1:]
            if key not in self.colors:
                raise KeyError(f"unknown named color {v}")
            return self.colors[key]
        return v

    def check(self):
        for _, _, cat in self.rules:
            self.category(cat)

    def category_hash(self, name, stats=None):
        blob = json.dumps({"cat": self.category(name), "global": self.globals, "stats": stats},
                          sort_keys=True).encode()
        return hashlib.sha1(blob).hexdigest()[:16]

    # -- classification -------------------------------------------------
    def classify(self, rel):
        """Category for a path relative to data/, e.g. 'base/graphics/terrain/grass-1.png'."""
        return _classify(tuple((rx, cat) for _, rx, cat in self.rules), rel)

    def matching_rule(self, rel):
        for pat, rx, cat in self.rules:
            if rx.match(rel):
                return pat, cat
        return None, None


@lru_cache(maxsize=None)
def _classify(rules, rel):
    for rx, cat in rules:
        if rx.match(rel):
            return cat
    return None


def _deep_merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            a[k] = _deep_merge(a[k], v)
        else:
            a[k] = v
    return a


def only_filter(patterns):
    """Predicate for --only: category names matched by comma-separated globs."""
    if not patterns:
        return lambda name: True
    pats = [p.strip() for p in patterns.split(",") if p.strip()]
    return lambda name: any(fnmatch.fnmatchcase(name, p) for p in pats)
