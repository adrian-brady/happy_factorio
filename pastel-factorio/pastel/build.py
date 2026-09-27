"""inventory, build and validate."""
import csv
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from . import pngio
from .config import only_filter
from .project import Project, SKIP_NAMES

CODE_VERSION = "0.1"   # bump when transform code changes, to force a rebuild


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Validation of one source/output pair
# ---------------------------------------------------------------------------

def readable_png(path):
    """True if the file opens as an image. Some game files named .png are empty
    (0 bytes) placeholders; those are copied through unchanged."""
    try:
        if path.stat().st_size == 0:
            return False
        pngio.open_png(path)
        return True
    except Exception:
        return False


def _same_bytes(src, out):
    return src.stat().st_size == out.stat().st_size and sha1_file(src) == sha1_file(out)


def validate_pair(src, out, ctype):
    """List of problems with an output file (empty list = fine)."""
    if not out.exists():
        return ["output missing"]
    # Non-images, pass-through files and unreadable/empty .png files must be
    # byte-for-byte copies of the source.
    if (not str(src).lower().endswith(".png") or ctype == "passthrough"
            or not readable_png(src)):
        return [] if _same_bytes(src, out) else ["file differs from source (should be an exact copy)"]
    a, b = pngio.open_png(src), pngio.open_png(out)
    problems = []
    sa, sb = pngio.metadata_signature(a), pngio.metadata_signature(b)
    for k in sa:
        if sa[k] != sb[k]:
            problems.append(f"{k} changed: {sa[k]} -> {sb[k]}")
    if problems:
        return problems
    if a.mode in ("RGBA", "LA"):
        aa = np.asarray(a)[..., -1]
        ab = np.asarray(b)[..., -1]
        if ctype == "shadow":
            if not np.array_equal(aa > 0, ab > 0):
                problems.append("shadow shape changed")
        elif not np.array_equal(aa, ab):
            problems.append("alpha changed")
        if a.mode == "RGBA":
            clear = aa == 0
            if clear.any() and not np.array_equal(np.asarray(a)[clear][:, :3], np.asarray(b)[clear][:, :3]):
                problems.append("RGB of transparent pixels changed")
    elif a.mode == "P":
        if not np.array_equal(np.asarray(a), np.asarray(b)):
            problems.append("palette indices changed")
        _, pa = pngio.palette_arrays(a)
        _, pb = pngio.palette_arrays(b)
        if ctype == "shadow":
            if not np.array_equal(pa > 0, pb > 0):
                problems.append("shadow shape changed")
        elif not np.array_equal(pa, pb):
            problems.append("palette alpha changed")
    return problems


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

_P = None


def _init_worker(root, stats):
    global _P
    _P = Project(root)
    _P._stats = stats


def _process(job):
    rel, category, ctype = job
    p = _P
    src, out = p.src_path(rel), p.out_path(rel)
    out.parent.mkdir(parents=True, exist_ok=True)
    changed = False
    notes = []
    try:
        if rel.lower().endswith(".png") and ctype != "passthrough" and not readable_png(src):
            notes.append("not a readable image (empty or damaged); copied unchanged")
        elif rel.lower().endswith(".png") and ctype != "passthrough":
            new = p.recolor(rel, category)
            if new is not None:
                tmp = out.with_name(out.name + ".tmp")
                pngio.save_like(new, pngio.open_png(src), tmp)
                os.replace(tmp, out)
                changed = True
        if not changed:
            shutil.copy2(src, out)
        problems = validate_pair(src, out, ctype)
    except Exception as e:  # report and keep going
        problems = [f"error: {type(e).__name__}: {e}"]
    size = out.stat().st_size if out.exists() else 0
    return rel, changed, size, sha1_file(out) if out.exists() else None, problems, notes


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def classify_all(p, fail=True):
    result, unmatched = {}, []
    for f in p.all_files():
        if f.lower().endswith(".png"):
            c = p.cfg.classify(f)
            if c is None:
                unmatched.append(f)
            result[f] = c
        else:
            result[f] = "passthrough"
    if unmatched:
        p.build_dir.mkdir(exist_ok=True)
        (p.build_dir / "unmatched.txt").write_text("\n".join(unmatched) + "\n")
        print(f"{len(unmatched)} PNG(s) match no rule in config/rules.yaml "
              f"(full list in build/unmatched.txt):")
        for f in unmatched[:25]:
            print("   ", f)
        if fail:
            sys.exit(1)
    return result


def cmd_classify(p, args):
    cats = classify_all(p, fail=False)
    p.build_dir.mkdir(exist_ok=True)
    path = p.build_dir / "classification_report.csv"
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "category", "rule"])
        for f, c in cats.items():
            w.writerow([f, c, p.cfg.matching_rule(f)[0] if f.lower().endswith(".png") else "(non-PNG)"])
    counts = {}
    for c in cats.values():
        counts[c] = counts.get(c, 0) + 1
    for c, n in sorted(counts.items(), key=lambda x: (-x[1], str(x[0]))):
        print(f"{n:6d}  {c}")
    print(f"Written to {path.relative_to(p.root)}")


def cmd_inventory(p, args):
    cats = classify_all(p, fail=False)
    p.build_dir.mkdir(exist_ok=True)
    path = p.build_dir / "inventory.csv"
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "category", "bytes", "width", "height", "mode", "gamma", "sha1"])
        for f, c in cats.items():
            src = p.src_path(f)
            row = [f, c, src.stat().st_size, "", "", "", "", sha1_file(src)]
            if f.lower().endswith(".png"):
                try:
                    im = pngio.open_png(src)
                    row[3:7] = [im.width, im.height, im.mode, im.info.get("gamma", "")]
                except Exception as e:
                    row[5] = f"unreadable: {e}"
            w.writerow(row)
    print(f"{len(cats)} files. Written to {path.relative_to(p.root)}")


def cmd_build(p, args):
    t0 = time.time()
    cats = classify_all(p)
    only = only_filter(args.only)
    manifest_path = p.build_dir / "manifest.json"
    prev = {}
    if manifest_path.exists():
        prev = json.loads(manifest_path.read_text()).get("files", {})

    if args.clean:
        for root in p.source_roots():
            out_root = root.parent / "updated_graphics"
            if out_root.exists():
                print(f"Removing {out_root.relative_to(p.root)}")
                shutil.rmtree(out_root)
        prev = {}

    # Effective category for this run: with --only, everything else is copied as vanilla.
    eff = {}
    for f, c in cats.items():
        eff[f] = c if (not f.lower().endswith(".png") or only(c)) else "passthrough"

    print(f"Hashing {len(cats)} source files...")
    src_hash = {f: sha1_file(p.src_path(f)) for f in cats}

    # Guard: a source file that is byte-identical to something we produced earlier
    # means recolored files were copied back in as "vanilla".
    produced = {m["out"] for m in prev.values() if m.get("out") and m.get("out") != m.get("src")}
    recolored_inputs = [f for f, h in src_hash.items() if h in produced]
    if recolored_inputs and not args.force:
        print(f"\nSTOP: {len(recolored_inputs)} source file(s) in data/*/graphics look already recolored "
              "(they match files this pipeline produced). Examples:")
        for f in recolored_inputs[:10]:
            print("   ", f)
        print("\nCopy fresh vanilla graphics folders into data/ (Steam: Verify integrity of game files first).\n"
              "If you are sure these are vanilla, rerun with --force.")
        sys.exit(1)

    # Stats for 'transfer' categories are computed once, up front.
    stats = {}
    for c in sorted({c for c in eff.values() if c != "passthrough"}):
        if p.cfg.category(c)["type"] == "transfer":
            stats[c] = p.stats_for(c)
            s = stats[c]
            print(f"  {c}: measured median L={s['L']:.2f} C={s['C']:.3f} h={s['h']:.0f} over {s['files']} file(s)")

    jobs, records, skipped = [], {}, 0
    for f, c in eff.items():
        ctype = p.cfg.category(c)["type"] if c else "passthrough"
        cfg_hash = CODE_VERSION + ":" + (p.cfg.category_hash(c, stats.get(c)) if ctype != "passthrough" else "copy")
        old = prev.get(f)
        out = p.out_path(f)
        if (old and old.get("src") == src_hash[f] and old.get("cfg") == cfg_hash and not old.get("problems")
                and out.exists() and out.stat().st_size == old.get("size")):
            records[f] = old
            skipped += 1
            continue
        records[f] = {"src": src_hash[f], "cfg": cfg_hash, "category": c}
        jobs.append((f, c, ctype))

    print(f"{len(jobs)} file(s) to process, {skipped} unchanged since last build.")
    problems_total = []
    notes_total = []
    changed_n = 0
    if jobs:
        workers = args.jobs or max(1, (os.cpu_count() or 2) - 1)
        done = 0
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                                 initargs=(str(p.root), stats)) as ex:
            for rel, changed, size, out_hash, problems, notes in ex.map(_process, jobs, chunksize=4):
                records[rel].update({"out": out_hash, "size": size, "problems": problems})
                if notes:
                    notes_total.append((rel, notes))
                changed_n += changed
                if problems:
                    problems_total.append((rel, problems))
                done += 1
                if done % 100 == 0 or done == len(jobs):
                    print(f"\r  {done}/{len(jobs)}", end="", flush=True)
        print()

    # Remove outputs whose source no longer exists, so the folder mirrors the source.
    stale = 0
    for root in p.source_roots():
        out_root = root.parent / "updated_graphics"
        if not out_root.exists():
            continue
        for q in out_root.rglob("*"):
            if q.is_file() and q.name not in SKIP_NAMES:
                rel = (root.relative_to(p.data).parent / "graphics" / q.relative_to(out_root)).as_posix()
                if rel not in cats:
                    q.unlink()
                    stale += 1

    p.build_dir.mkdir(exist_ok=True)
    manifest_path.write_text(json.dumps({"version": CODE_VERSION, "files": records}, indent=0, sort_keys=True))
    with open(p.build_dir / "build_report.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "category", "problems"])
        for f in sorted(records):
            w.writerow([f, records[f].get("category"), "; ".join(records[f].get("problems") or [])])

    print(f"\nDone in {time.time() - t0:.0f}s: {changed_n} recolored, "
          f"{len(jobs) - changed_n} copied unchanged, {skipped} skipped (up to date), {stale} stale removed.")
    outs = ", ".join(str((r.parent / "updated_graphics").relative_to(p.root)) for r in p.source_roots())
    print(f"Output: {outs}")
    if problems_total:
        print(f"\n{len(problems_total)} file(s) FAILED validation:")
        for rel, pr in problems_total[:30]:
            print(f"   {rel}: {'; '.join(pr)}")
        print("Full list in build/build_report.csv. Don't install until these are fixed.")
        sys.exit(1)
    print("All files passed validation.")


def _validate_job(job):
    rel, ctype = job
    return rel, validate_pair(_P.src_path(rel), _P.out_path(rel), ctype)


def cmd_validate(p, args):
    cats = classify_all(p)
    jobs = [(f, p.cfg.category(c)["type"]) for f, c in cats.items()]
    bad = []
    with ProcessPoolExecutor(max_workers=args.jobs or max(1, (os.cpu_count() or 2) - 1),
                             initializer=_init_worker, initargs=(str(p.root), {})) as ex:
        for rel, problems in ex.map(_validate_job, jobs, chunksize=8):
            if problems:
                bad.append((rel, problems))
    extra = []
    for root in p.source_roots():
        out_root = root.parent / "updated_graphics"
        for q in (out_root.rglob("*") if out_root.exists() else []):
            if q.is_file() and q.name not in SKIP_NAMES:
                rel = (root.relative_to(p.data).parent / "graphics" / q.relative_to(out_root)).as_posix()
                if rel not in cats:
                    extra.append(rel)
    for rel, pr in bad[:50]:
        print(f"   {rel}: {'; '.join(pr)}")
    for rel in extra[:20]:
        print(f"   extra file in output: {rel}")
    if bad or extra:
        print(f"{len(bad)} problem file(s), {len(extra)} extra file(s).")
        sys.exit(1)
    print(f"All {len(jobs)} files OK: same names, sizes, modes, metadata and alpha as the source.")
