#!/usr/bin/env python3
"""publish_editions.py - upload built editions to the public `books` release.

The mirror image of the book repo's `build.py online`: the same selectors, so what
you built is what you publish, named the same way.

    python publish_editions.py                       # Tier A (default, same as build.py)
    python publish_editions.py --full                # every publishable edition that renders
    python publish_editions.py --all                 # every publishable edition
    python publish_editions.py --tier AB             # A + all complete drafts
    python publish_editions.py -l Chinese Urdu       # by name or 2-letter code
    python publish_editions.py --full --format epub  # one format only
    python publish_editions.py --full --dry-run      # list and exit, upload nothing

Selection mirrors `build.py online` exactly, reading TIER_A and HARD_EXCLUDE straight
out of the book repo so the two can never disagree. The hard-excluded editions are
refused even when named explicitly: `build.py` lets you build one to proof it, but
publishing is where "these never ship" has to actually bite.

Hebrew is uploaded like any other edition. `HIDDEN_SLUGS` in build_read_pages.py keeps
it off arasteh.art; the release still carries it (author's call, 2026-07-26).

THE CONFIRMATION PHRASE IS DIFFERENT EVERY TIME. It is built from what this specific
run would do -- scope, edition count, file count -- so a phrase copied from an earlier
command, or from the docs, will not fire this one. Typing UPLOAD out of muscle memory
cannot push 214 files when you meant three.

After uploading, run `build_read_pages.py`: it reads the release, so the cards, counts
and copy all follow from what is actually published.

Git is author-only, here as everywhere in this project: this script touches the release
only. It never commits, stages or pushes.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
BOOK_VOL = SITE.parent / "1_Sedaha" / "Volume1"
ONLINE = BOOK_VOL / "online"
RELEASE_TAG = "books"
FORMATS = ("epub", "pdf")


def _console_safe(text: object) -> str:
    """The console here is cp1252; an edition name or gh error with a non-ASCII
    character must not turn a report into a traceback."""
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    return str(text).encode(enc, "replace").decode(enc, "replace")


def _book_lists() -> tuple[list[str], set[str]]:
    """TIER_A and HARD_EXCLUDE, read straight out of the book repo's build.py, the
    same way build_read_pages.py does. One source of truth, not a second copy."""
    src = (BOOK_VOL / "build.py").read_text(encoding="utf-8")
    out = {}
    for name in ("TIER_A", "HARD_EXCLUDE"):
        m = re.search(rf"^{name}\s*=\s*([\[{{].*?[\]}}])\s*$", src, re.M | re.S)
        if not m:
            raise SystemExit(f"build.py: {name} not found - refusing to guess the publish set")
        out[name] = ast.literal_eval(m.group(1))
    return list(out["TIER_A"]), set(out["HARD_EXCLUDE"])


def _editions() -> dict[str, str]:
    """config key -> block_tag, from the book's LANGUAGE_CONFIGS, without importing it
    (that module is heavy and pulls in the whole export stack)."""
    src = (BOOK_VOL / "export_translation.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        targets = getattr(node, "targets", [])
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "LANGUAGE_CONFIGS" for t in targets):
            out = {}
            for k, v in zip(node.value.keys, node.value.values):
                tag = next((vv.value for kk, vv in zip(v.keys, v.values)
                            if kk is not None and getattr(kk, "value", "") == "block_tag"), None)
                out[k.value] = tag
            return out
    raise SystemExit("export_translation.py: LANGUAGE_CONFIGS not found")


def _resolve(names: list[str], known: dict[str, str]) -> list[str]:
    """Accept a config name or a block tag, case-insensitively, like build.py does."""
    by_lower = {n.lower(): n for n in known}
    by_tag = {(t or "").lower(): n for n, t in known.items()}
    out, bad = [], []
    for raw in names:
        key = raw.strip().lower()
        hit = by_lower.get(key) or by_tag.get(key)
        (out.append(hit) if hit else bad.append(raw))
    if bad:
        raise SystemExit("unknown edition(s): %s\nRun `python build_read_pages.py --check` "
                         "or `python ..\\1_Sedaha\\Volume1\\build.py languages` for the list."
                         % ", ".join(bad))
    return out


def _phrase(scope: str, n_ed: int, n_files: int) -> str:
    """The confirmation phrase for THIS run and no other.

    Deliberately not a bare UPLOAD. The point of a confirmation is that you cannot
    give it without reading what you are confirming, and a fixed word fails that the
    third time you type it. Scope and both counts are in the phrase, so publishing
    three editions and publishing all of them do not look alike at the prompt.
    """
    return f"UPLOAD {scope.upper()} {n_ed} EDITIONS {n_files} FILES"


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="publish_editions.py",
        description="Upload built editions to the public `books` release. "
                    "Selectors mirror `build.py online`.")
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--language", "-l", nargs="+", metavar="LANG",
                     help="Specific edition(s) by name or 2-letter code.")
    sel.add_argument("--all", action="store_true",
                     help="Every publishable edition (all minus the hard-excluded).")
    sel.add_argument("--full", action="store_true",
                     help="Every publishable edition that has a built pair on disk.")
    sel.add_argument("--tier", choices=["A", "AB"],
                     help="A = QA'd lead set (default); AB = A + all complete drafts.")
    ap.add_argument("--format", "-f", default=",".join(FORMATS),
                    help=f"Comma list of formats. Default: {','.join(FORMATS)}.")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be uploaded, then exit. Uploads nothing.")
    ap.add_argument("--yes", metavar="PHRASE",
                    help="Supply the confirmation phrase non-interactively. It must "
                         "match this run exactly; there is no blanket --force.")
    args = ap.parse_args()

    formats = [f.strip().lower() for f in args.format.split(",") if f.strip()]
    if any(f not in FORMATS for f in formats):
        ap.error(f"unknown format(s); choose from {', '.join(FORMATS)}")

    known = _editions()
    tier_a, excluded = _book_lists()
    publishable = [n for n in known if n not in excluded]

    if args.language:
        langs = _resolve(args.language, known)
        blocked = [n for n in langs if n in excluded]
        if blocked:
            # build.py builds a named defective edition so you can proof it. Publishing
            # is the other side of that: the exclude list is absolute here.
            raise SystemExit("refusing to publish hard-excluded edition(s): %s\n"
                             "These are recorded in build.py with their evidence and never ship."
                             % ", ".join(sorted(blocked)))
        scope = "named"
    elif args.all:
        langs, scope = list(publishable), "all"
    elif args.full:
        langs, scope = list(publishable), "full"
    elif args.tier == "AB":
        langs, scope = tier_a + [n for n in publishable if n not in tier_a], "tierab"
    else:
        langs, scope = list(tier_a), "tiera"

    # What is actually on disk. --full quietly drops editions with no build; every
    # other selector reports them, because asking for something that is not there
    # should not be silent.
    plan, missing = [], []
    for name in langs:
        found = [ONLINE / f"Sedaha_{name}.{f}" for f in formats]
        have = [p for p in found if p.exists()]
        if len(have) != len(found):
            missing.append((name, [p.name for p in found if not p.exists()]))
        plan.extend(have)
    if missing and not args.full:
        print("Not built (run build.py online first):")
        for name, files in missing:
            print(f"  {name}: {', '.join(files)}")
        if not plan:
            return 2
    if args.full:
        langs = [n for n in langs if any((ONLINE / f"Sedaha_{n}.{f}").exists() for f in formats)]

    if not plan:
        print("Nothing to upload (empty selection).", file=sys.stderr)
        return 2

    n_ed = len({p.stem for p in plan})
    total_mb = sum(p.stat().st_size for p in plan) / 1e6
    print(f"Publish to release '{RELEASE_TAG}'")
    print(f"  scope    : {scope}")
    print(f"  editions : {n_ed}")
    print(f"  formats  : {', '.join(formats)}")
    print(f"  files    : {len(plan)}  ({total_mb:.0f} MB)")
    print(f"  source   : {ONLINE}")
    for p in sorted(plan, key=lambda q: q.name):
        print(f"    {p.name}  {p.stat().st_size / 1e6:.1f} MB")
    print("\n  NOTE: --clobber replaces same-name assets and RESETS their download counts.")

    if args.dry_run:
        print("\n[dry-run] nothing uploaded.")
        return 0

    want = _phrase(scope, n_ed, len(plan))
    given = args.yes if args.yes is not None else input(f'\nType exactly:  {want}\n> ')
    if given.strip() != want:
        print(f"\nCancelled; nothing was uploaded.")
        print(f"  this run needs : {want}")
        print(f"  you gave       : {given.strip() or '(nothing)'}")
        return 1

    cmd = ["gh", "release", "upload", RELEASE_TAG, *[str(p) for p in plan], "--clobber"]
    print(f"\nUploading {len(plan)} file(s)...")
    r = subprocess.run(cmd, cwd=SITE)
    if r.returncode != 0:
        print(_console_safe(f"gh failed with exit {r.returncode}; the release may be partially updated. "
                            "Re-run the same command - --clobber makes it safe to repeat."))
        return r.returncode
    print("\nUploaded. Now run:  python build_read_pages.py   (then check.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
