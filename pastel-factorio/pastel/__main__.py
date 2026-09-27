"""Command line entry point:  python3 -m pastel <command>  (run from the project folder)."""
import argparse
import sys

from .project import Project

USAGE = """\
python3 -m pastel --preview <filename> [options]   recolor one file, show before/after
python3 -m pastel build [--only CATS] [--clean]    write data/*/updated_graphics
python3 -m pastel validate                         re-check the output against the source
python3 -m pastel classify                         show which category every PNG is in
python3 -m pastel inventory                        list every source file (build/inventory.csv)
python3 -m pastel sheets [--category CAT]          before/after contact sheets after a build
"""


def preview_parser():
    ap = argparse.ArgumentParser(prog="python3 -m pastel --preview",
                                 description="Recolor one PNG in memory and show before and after.")
    ap.add_argument("--preview", required=True, metavar="NAME",
                    help="filename or part of a path, e.g. grass-1.png, iron-ore, entity/lab/lab.png")
    ap.add_argument("--pick", type=int, help="choose match N without prompting")
    ap.add_argument("--zoom", type=float, help="scale factor (default: fit about 1600px wide)")
    ap.add_argument("--crop", help="x,y,w,h region of the source image, e.g. 0,320,256,256")
    ap.add_argument("--bg", choices=["checker", "grass", "light", "dark"],
                    help="background behind transparent pixels (default checker; grass for shadows)")
    ap.add_argument("--tile", type=int, help="repeat the (cropped) image N x N, for terrain")
    ap.add_argument("--watch", action="store_true", help="re-render whenever config files change")
    ap.add_argument("--no-open", action="store_true", help="save only, don't open a viewer")
    ap.add_argument("--root", default=".", help=argparse.SUPPRESS)
    return ap


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if any(a == "--preview" or a.startswith("--preview=") for a in argv):
        args = preview_parser().parse_args(argv)
        from .preview import run
        run(Project(args.root), args)
        return

    ap = argparse.ArgumentParser(prog="python3 -m pastel", usage=USAGE)
    ap.add_argument("--root", default=".", help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="recolor everything into data/*/updated_graphics")
    b.add_argument("--only", help="only recolor these categories (comma-separated, wildcards ok, "
                                  "e.g. 'terrain.*,ore.*,shadow,lut'); everything else is copied unchanged")
    b.add_argument("--clean", action="store_true", help="delete existing output and rebuild from scratch")
    b.add_argument("--force", action="store_true", help="skip the already-recolored-input check")
    b.add_argument("--jobs", type=int, help="parallel worker processes (default: CPU count - 1)")
    v = sub.add_parser("validate", help="check the output against the source")
    v.add_argument("--jobs", type=int)
    sub.add_parser("classify", help="write build/classification_report.csv")
    sub.add_parser("inventory", help="write build/inventory.csv")
    s = sub.add_parser("sheets", help="before/after contact sheets per category (after a build)")
    s.add_argument("--category", help="category name or wildcard, e.g. 'terrain.*'")
    s.add_argument("--limit", type=int, default=48, help="max files per sheet")
    args = ap.parse_args(argv)
    if not args.cmd:
        print(USAGE)
        return

    p = Project(args.root)
    from . import build, sheets
    {"build": build.cmd_build, "validate": build.cmd_validate, "classify": build.cmd_classify,
     "inventory": build.cmd_inventory, "sheets": sheets.cmd_sheets}[args.cmd](p, args)


if __name__ == "__main__":
    main()
