#!/usr/bin/env python3
"""publish_paintings.py - upload the badged painting downloads to the `paintings` release.

The counterpart of publish_editions.py for the paintings. The files are the ones
make_painting_downloads.py builds in ../Paintings/_downloads/, and the gallery
lightboxes link to them on the release, so GitHub counts every download.

    python publish_paintings.py --dry-run             # show the plan, upload nothing
    python publish_paintings.py                       # every gallery
    python publish_paintings.py -g boteh-jegheh       # one gallery (or several)

ONLY NEW OR CHANGED FILES ARE SENT. Each local file is compared with the asset of
the same name by SHA-256 (the release reports one per asset). A file the release
already has, byte for byte, is never touched, because replacing an asset resets
its download count to zero. A changed file has to replace its asset (--clobber,
for that file only), and the plan shows the count that replacement would reset.
An asset on the release that no painting uses any more is listed, never deleted.

If the release does not exist yet it is created first, after the same
confirmation, and never marked "latest" (so nothing about `books` changes).

THE CONFIRMATION PHRASE IS DIFFERENT EVERY TIME, as in publish_editions.py: it is
built from what this run would do, so a phrase copied from an earlier run or from
the docs will not fire this one.

Refuses to run while any download is missing or stale: run
make_painting_downloads.py first. It touches the release only; it never commits,
stages or pushes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys

import make_painting_downloads as mpd
import sync_gallery as sg

SITE = sg.SITE
REPO = sg.DOWNLOAD_REPO
RELEASE_TAG = sg.DOWNLOAD_RELEASE
RELEASE_TITLE = "Paintings"
RELEASE_NOTES = ("Paintings by Amir Arasteh, 3000 px, as offered on https://arasteh.art/paintings/. "
                 "All artwork (c) Amir Arasteh. All Rights Reserved.")


def _console_safe(text: object) -> str:
    """The console here is cp1252; a gh error with a non-ASCII character must not
    turn a report into a traceback."""
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    return str(text).encode(enc, "replace").decode(enc, "replace")


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _release() -> dict | None:
    """The release as the API reports it, or None if it does not exist yet.
    A read-only GET through gh, so a private network error is reported, not guessed."""
    r = subprocess.run(["gh", "api", f"repos/{REPO}/releases/tags/{RELEASE_TAG}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 0:
        return json.loads(r.stdout)
    if "HTTP 404" in (r.stderr or "") or '"Not Found"' in (r.stdout or ""):
        return None
    raise SystemExit(_console_safe(f"gh api failed (exit {r.returncode}): "
                                   f"{(r.stderr or r.stdout).strip()}"))


def _phrase(scope: str, n_new: int, n_replaced: int, create: bool) -> str:
    """The confirmation phrase for THIS run and no other (see publish_editions._phrase).
    Replacements are named separately because each one resets a download count."""
    return (("CREATE AND " if create else "")
            + f"UPLOAD {scope.upper()} {n_new} NEW {n_replaced} REPLACED PAINTINGS")


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="publish_paintings.py",
        description=f"Upload new or changed painting downloads to the `{RELEASE_TAG}` release.")
    ap.add_argument("--gallery", "-g", nargs="+", metavar="SLUG",
                    help="Only these galleries: " + ", ".join(g["slug"] for g in sg.GALLERIES))
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be uploaded, then exit. Uploads nothing.")
    ap.add_argument("--yes", metavar="PHRASE",
                    help="Supply the confirmation phrase non-interactively. It must match "
                         "this run exactly; there is no blanket --force.")
    args = ap.parse_args()

    known = [g["slug"] for g in sg.GALLERIES]
    if args.gallery:
        bad = [g for g in args.gallery if g not in known]
        if bad:
            ap.error(f"unknown gallery: {', '.join(bad)} (choose from {', '.join(known)})")
        scope = "-".join(args.gallery)
    else:
        scope = "all"

    downloads, problems = mpd.expected()
    if args.gallery:
        downloads = [d for d in downloads if d.gallery in args.gallery]
    stale = mpd.stale(downloads)
    if problems or stale:
        for note in problems:
            print(_console_safe(f"[warn]  {note}"))
        for d, why in stale:
            print(f"[stale] _downloads/{d.gallery}/{d.name}  ({why})")
        print("\nNothing uploaded. Run  python make_painting_downloads.py  first.")
        return 2
    if not downloads:
        print("Nothing to upload (empty selection).", file=sys.stderr)
        return 2

    release = _release()
    assets = {a["name"]: a for a in (release or {}).get("assets", [])}
    new, replace, same = [], [], []
    for d in downloads:
        asset = assets.get(d.name)
        if asset is None:
            new.append(d)
            continue
        digest = (asset.get("digest") or "").removeprefix("sha256:")
        local = _sha256(d.path)
        unchanged = (digest == local) if digest else (asset.get("size") == d.path.stat().st_size)
        (same if unchanged else replace).append((d, asset))
    ours = {d.name for d in mpd.expected()[0]}
    unused = sorted(n for n in assets if n not in ours)

    total_mb = sum(d.path.stat().st_size for d in new) / 1e6 + \
        sum(d.path.stat().st_size for d, _a in replace) / 1e6
    print(f"Publish to release '{RELEASE_TAG}' ({REPO})")
    print(f"  release  : {'exists' if release else 'MISSING - it will be created'}")
    print(f"  scope    : {scope}")
    print(f"  paintings: {len(downloads)}  ({len(same)} already there, unchanged)")
    print(f"  new      : {len(new)}")
    print(f"  replaced : {len(replace)}")
    print(f"  upload   : {total_mb:.1f} MB")
    print(f"  source   : {mpd.OUT_ROOT}")
    for d in new:
        print(f"    + {d.name}  {d.path.stat().st_size / 1e6:.1f} MB")
    for d, asset in replace:
        print(f"    ~ {d.name}  {d.path.stat().st_size / 1e6:.1f} MB  "
              f"(replaces the asset; resets its {asset.get('download_count', 0)} downloads)")
    for name in unused:
        print(f"    ? {name}  on the release, used by no painting now (left alone)")
    if not (new or replace) and release:
        print("\nNothing to upload: the release already has every painting, byte for byte.")
        return 0

    if args.dry_run:
        print("\n[dry-run] nothing uploaded, no release created.")
        return 0

    want = _phrase(scope, len(new), len(replace), release is None)
    given = args.yes if args.yes is not None else input(f"\nType exactly:  {want}\n> ")
    if given.strip() != want:
        print("\nCancelled; nothing was uploaded.")
        print(f"  this run needs : {want}")
        print(f"  you gave       : {given.strip() or '(nothing)'}")
        return 1

    if release is None:
        print(f"\nCreating release '{RELEASE_TAG}'...")
        r = subprocess.run(["gh", "release", "create", RELEASE_TAG, "--repo", REPO,
                            "--title", RELEASE_TITLE, "--notes", RELEASE_NOTES,
                            "--latest=false"], cwd=SITE)
        if r.returncode != 0:
            print(f"gh release create failed with exit {r.returncode}; nothing was uploaded.")
            return r.returncode

    # New files without --clobber: if one turns out to exist after all, gh refuses
    # rather than resetting a count. Only the files known to differ are clobbered.
    batches = [("new", [d.path for d in new], []),
               ("replaced", [d.path for d, _a in replace], ["--clobber"])]
    for label, files, flags in batches:
        if not files:
            continue
        print(f"\nUploading {len(files)} {label} file(s)...")
        r = subprocess.run(["gh", "release", "upload", RELEASE_TAG, "--repo", REPO,
                            *[str(p) for p in files], *flags], cwd=SITE)
        if r.returncode != 0:
            print(_console_safe(f"gh failed with exit {r.returncode}; the release may be partially "
                                f"updated. Re-run the same command: it only sends what still "
                                f"differs."))
            return r.returncode
    print("\nUploaded. Check with:  python publish_paintings.py --dry-run   "
          "and  python download_counts.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
