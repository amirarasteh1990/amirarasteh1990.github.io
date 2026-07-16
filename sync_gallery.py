#!/usr/bin/env python3
"""
sync_gallery.py — Re-derive the site's gallery images from the BOOK repo's painting
masters (Volume1/CoverPics), so a repainted master never goes stale on the site.
Single source of truth = the book repo.

For every master it writes two JPEGs under assets/img/paintings/sounds/:
  * full  — longest edge 1500 px   (lightbox image)
  * th/   — longest edge  560 px   (gallery thumbnail)

A derived pair is only rewritten when the master is newer than the derived file
(or with --force), so unchanged paintings keep identical bytes and a clean git diff.

Run whenever a painting in CoverPics changes:
    python sync_gallery.py            # regenerate stale derived images
    python sync_gallery.py --check    # report drift only; change nothing; exit 1 if stale
    python sync_gallery.py --force    # regenerate everything
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

SITE = Path(__file__).resolve().parent
COVERPICS = SITE.parent / "1_Sedaha" / "Volume1" / "CoverPics"  # book working repo (sibling). Edit if moved.
OUT = SITE / "assets" / "img" / "paintings" / "sounds"
OUT_TH = OUT / "th"

FULL_EDGE = 1500
THUMB_EDGE = 560
QUALITY = 85

# master filename -> derived stem (everything ships as .jpg on the site)
RENAME = {"00_CoverPhoto": "cover"}


def _derived_name(master: Path) -> str:
    return RENAME.get(master.stem, master.stem) + ".jpg"


def _masters() -> list[Path]:
    return sorted(
        f for f in COVERPICS.iterdir()
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")
    )


def _save_resized(im: Image.Image, dest: Path, edge: int) -> None:
    scale = edge / max(im.size)
    resized = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    resized.save(dest, "JPEG", quality=QUALITY, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--check", action="store_true", help="report drift only; change nothing; exit 1 if stale")
    ap.add_argument("--force", action="store_true", help="regenerate every derived image")
    args = ap.parse_args()

    if not COVERPICS.is_dir():
        sys.exit(f"CoverPics not found: {COVERPICS}")
    OUT_TH.mkdir(parents=True, exist_ok=True)

    stale = 0
    for master in _masters():
        name = _derived_name(master)
        full, thumb = OUT / name, OUT_TH / name
        current = (
            not args.force
            and full.is_file() and thumb.is_file()
            and full.stat().st_mtime >= master.stat().st_mtime
            and thumb.stat().st_mtime >= master.stat().st_mtime
        )
        if current:
            continue
        stale += 1
        if args.check:
            print(f"STALE  {name}  (master {master.name} is newer)")
            continue
        with Image.open(master) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode != "RGB":  # PNG masters (RGBA) — flatten
                im = im.convert("RGB")
            _save_resized(im, full, FULL_EDGE)
            _save_resized(im, thumb, THUMB_EDGE)
        print(f"wrote  {full.relative_to(SITE)}  +  {thumb.relative_to(SITE)}")

    if stale == 0:
        print(f"gallery in sync with {COVERPICS} ({len(_masters())} paintings)")
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
