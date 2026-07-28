#!/usr/bin/env python3
"""
sync_gallery.py — Re-derive the site's gallery images and English book-cover preview
from the BOOK repo, so neither the paintings nor the displayed cover can go stale.
Single source of truth = the book repo.

For every master it writes two JPEGs under assets/img/paintings/sounds/:
  * full  — longest edge 1500 px   (lightbox image)
  * th/   — longest edge  560 px   (gallery thumbnail)

Each JPEG gets a WebP twin of the same pixels, roughly half the bytes. The pages
serve it through <picture>/image-set and fall back to the JPEG where WebP is not
supported, so the twins are an optimisation, never a requirement.

It also writes assets/img/book-cover.jpg from CoverPics/_generated/cover_EN.jpg
at a web-sized 1200 px longest edge, and a WebP twin for the two standing page
images (cover.jpg, book-cover.jpg) that are used as CSS backgrounds.

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
BOOK_COVER_MASTER = COVERPICS / "_generated" / "cover_EN.jpg"
BOOK_COVER_OUT = SITE / "assets" / "img" / "book-cover.jpg"

FULL_EDGE = 1500
THUMB_EDGE = 560
BOOK_COVER_EDGE = 1200
QUALITY = 85
WEBP_QUALITY = 80          # visually matched to JPEG 85 on these paintings
LANCZOS = getattr(Image, "Resampling", Image).LANCZOS
# page images that are not derived from CoverPics but still want a WebP twin
STANDING = [SITE / "assets" / "img" / "cover.jpg", BOOK_COVER_OUT]

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
    resized = im.resize((round(im.width * scale), round(im.height * scale)), LANCZOS)
    resized.save(dest, "JPEG", quality=QUALITY, optimize=True)
    resized.save(dest.with_suffix(".webp"), "WEBP", quality=WEBP_QUALITY, method=6)


BAND_SRC = OUT / "cover.jpg"     # the painting itself, before covers.py letters it
BAND_OUT = SITE / "assets" / "img" / "book-painting-band.jpg"
# The largest box this sits behind is about 150 CSS px wide. background-size:cover on
# a portrait painting matches the width and crops the height, so 512 is a 3x display
# at 170 px, with room over. Bigger is pixels no one can see.
BAND_EDGE = 512
BAND_TURN = 270          # the painting stands upright; this lays it down
# Lower than the galleries, because nobody looks at this the way they look at those.
# Measured at what a box actually renders (112x60 at 2x, cover-cropped): dropping the
# WebP from 80 to 68 costs 0.7/255 of mean error, well under noticing, and a quarter
# of the file. The scrim over it narrows the visible range further still.
BAND_WEBP_QUALITY = 68
BAND_JPEG_QUALITY = 78


def _write_band(check: bool) -> bool:
    """A quiet band of the painting, behind the language boxes.

    Two things it is deliberately NOT. It is not the cover: the cover carries the
    title and the author's name, and a hundred chips each wearing a tiny book jacket
    read as clutter, not as texture. This comes from 00_CoverPhoto, the painting on
    its own, so nothing legible survives the crop.

    And it is not rotated in CSS. A background image cannot be turned, and turning a
    pseudo-element per box repaints on every scroll, at a hundred boxes once the
    catalogue is open. The turn is baked into the file instead: one asset, no
    transform, nothing for the compositor to redo.

    No ICC profile or EXIF is carried over. It is a texture under a dark scrim; the
    metadata would be a third of the file."""
    if not BAND_SRC.is_file():
        return True
    fresh = (BAND_OUT.is_file()
             and BAND_OUT.stat().st_mtime >= BAND_SRC.stat().st_mtime
             and _twin_is_current(BAND_OUT))
    if fresh:
        print(f"[ok]    {BAND_OUT.name}: current")
        return True
    if check:
        print(f"[stale] {BAND_OUT.name}")
        return False
    with Image.open(BAND_SRC) as im:
        turned = im.convert("RGB").rotate(BAND_TURN, expand=True)
    scale = BAND_EDGE / max(turned.size)
    turned = turned.resize((round(turned.width * scale), round(turned.height * scale)),
                           LANCZOS)
    # resize carries .info forward, and Pillow writes any icc_profile or exif it
    # finds there; emptying it is what keeps the file to pixels alone
    turned.info.clear()
    turned.save(BAND_OUT, "JPEG", quality=BAND_JPEG_QUALITY, optimize=True)
    turned.save(BAND_OUT.with_suffix(".webp"), "WEBP",
                quality=BAND_WEBP_QUALITY, method=6)
    print(f"[write] {BAND_OUT.name}  ({turned.width}x{turned.height}, "
          f"the painting laid down, no lettering)")
    return True


# == the painting beside the excerpt on /sedaha/ ==
# The line it sits next to is "... the loose end of a thread of words that were once
# sounds...", and the opening painting is that sentence. Whole, uncropped: at three
# lines tall it has the room a crop was invented to save, and the trailing thread,
# the tangle and the bare canvas all read at that size.
#
# The source is the site's own derived copy, not the CoverPics master, so the mark
# still builds when the book repo is not beside the site. _write_band takes its
# source the same way.
MARK_SRC = OUT / "01.jpg"         # the opening painting
MARK_OUT = SITE / "assets" / "img" / "opening-mark.jpg"
# The element is about 125 CSS px wide (three lines tall, proportions kept), so 256
# covers a 2x display with a little over. Nothing is cropped, so no region here.
MARK_WIDTH = 256
# Turned in the file, not by CSS. A transform on the element would be re-composited
# on every scroll and would rotate the box as well as the paint; this is one asset
# that arrives the right way up. Same reasoning as the band behind the language
# boxes. Upside down, the weight of the tangle sits at the top and the bare canvas
# falls to the bottom, where the text now sits.
MARK_TURN = 180


def _write_excerpt_mark(check: bool) -> bool:
    src = MARK_SRC
    if not src.is_file():
        print(f"[warn]  excerpt mark: {src.name} not found; run the gallery sync first")
        return False
    fresh = (MARK_OUT.is_file() and MARK_OUT.stat().st_mtime >= src.stat().st_mtime
             and _twin_is_current(MARK_OUT))
    if fresh:
        print(f"[ok]    {MARK_OUT.name}: current")
        return True
    if check:
        print(f"[stale] {MARK_OUT.name}")
        return False
    with Image.open(src) as im:
        mark = im.convert("RGB").rotate(MARK_TURN, expand=True)
        ratio = mark.height / mark.width
        # scaled, never fitted or cropped: the whole canvas, in its own proportions
        mark = mark.resize((MARK_WIDTH, round(MARK_WIDTH * ratio)), LANCZOS)
    mark.info.clear()
    mark.save(MARK_OUT, "JPEG", quality=QUALITY, optimize=True)
    mark.save(MARK_OUT.with_suffix(".webp"), "WEBP",
              quality=WEBP_QUALITY, method=6)
    print(f"[write] {MARK_OUT.name}  ({mark.width}x{mark.height} from {src.name}, "
          f"the whole painting, uncropped, turned {MARK_TURN})")
    return True


# == collection tiles for /paintings/ ==
# One entry per gallery. The crop is decided here and baked into the file, rather
# than loaded full-size and cropped by CSS: these are 220 CSS px at their widest, so
# shipping a gallery-sized painting to be squeezed by object-fit would be sending
# twenty times the pixels anyone sees. `centering` is where in the source the 4:3
# window sits -- 0.5, 0.42 keeps the poured centre of the Sounds painting and drops
# more of the foot than the head.
COLLECTION_DIR = SITE / "assets" / "img" / "paintings" / "index"
COLLECTION_SIZE = (480, 360)          # 2x a 220px tile, with room over
COLLECTION_THUMBS = {
    "sounds": {"source": "00_CoverPhoto", "centering": (0.5, 0.42)},
}


def _write_collection_thumbs(check: bool) -> bool:
    """A 4:3 tile per gallery, for the collection index."""
    ok = True
    COLLECTION_DIR.mkdir(parents=True, exist_ok=True)
    for slug, spec in COLLECTION_THUMBS.items():
        src = next((m for m in _masters() if m.stem == spec["source"]), None)
        if src is None:
            print(f"[warn]  collection tile {slug}: master {spec['source']} not found")
            ok = False
            continue
        out = COLLECTION_DIR / f"{slug}.jpg"
        fresh = (out.is_file() and out.stat().st_mtime >= src.stat().st_mtime
                 and _twin_is_current(out))
        if fresh:
            print(f"[ok]    paintings/index/{out.name}: current")
            continue
        if check:
            print(f"[stale] paintings/index/{out.name}")
            ok = False
            continue
        with Image.open(src) as im:
            tile = ImageOps.fit(im.convert("RGB"), COLLECTION_SIZE,
                                method=LANCZOS, centering=spec["centering"])
        tile.info.clear()             # no EXIF, no ICC: it is a 220px tile
        tile.save(out, "JPEG", quality=BAND_JPEG_QUALITY, optimize=True)
        tile.save(out.with_suffix(".webp"), "WEBP",
                  quality=BAND_WEBP_QUALITY, method=6)
        print(f"[write] paintings/index/{out.name}  "
              f"({tile.width}x{tile.height} from {src.name}, "
              f"centred {spec['centering'][0]:.2f},{spec['centering'][1]:.2f})")
    return ok


LOGO = SITE / "assets" / "img" / "logo-lockup.png"
LOGO_DARK = SITE / "assets" / "img" / "logo-lockup-dark.png"
LOGO_INK = (0xEC, 0xE3, 0xD4)     # the dark palette's warm cream


def _write_logo_dark(check: bool) -> bool:
    """The same logo with its lettering in warm cream, for dark pages.

    The lettering is dark ink and vanishes on a dark ground; a light plaque behind
    it fixed the contrast and put a box in the middle of a minimal page. So the
    lettering is recoloured and the background stays transparent.

    THE PAINTING IS NOT TOUCHED. It occupies a solid block of rows at the top; the
    lettering sits below a clear empty gap. Only pixels below that gap are altered,
    and only their colour: every alpha value is copied through, so the glyph edges
    keep their exact shape. Above the gap the file is copied pixel for pixel."""
    if not LOGO.is_file():
        return True
    fresh = (LOGO_DARK.is_file()
             and LOGO_DARK.stat().st_mtime >= LOGO.stat().st_mtime
             and _twin_is_current(LOGO_DARK))
    if fresh:
        print(f"[ok]    {LOGO_DARK.name}: current")
        return True
    if check:
        print(f"[stale] {LOGO_DARK.name}")
        return False

    with Image.open(LOGO) as src:
        out = src.convert("RGBA")
    w, h = out.size
    px = out.load()

    # the painting is the block of rows opaque nearly all the way across; the
    # lettering sits below the first fully clear row after it
    solid = [y for y in range(h)
             if sum(1 for x in range(w) if px[x, y][3] > 40) > w * 0.9]
    gap = next((y for y in range(solid[-1] + 1, h)
                if all(px[x, y][3] <= 40 for x in range(w))), None) if solid else None
    if gap is None:
        print("[warn]  logo: painting and lettering not separable; not written")
        return False

    # Scoped by POSITION, not by colour. Recolouring the ink colours would have been
    # neater and is wrong: ten of them are used by the painting as well, so remapping
    # them repaints it. Only pixels below the clear gap are rewritten, and only their
    # RGB: every alpha value is copied through, so the glyph edges keep their shape
    # and everything above the gap is byte-for-byte the original.
    changed = 0
    for y in range(gap, h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if max(r, g, b) < 150 and max(r, g, b) - min(r, g, b) < 60:
                px[x, y] = LOGO_INK + (a,)
                changed += 1

    # The PNG is ~3x the palette original, because a recoloured RGBA cannot go back
    # to a full palette without requantising the painting. It is a fallback only: a
    # browser old enough to lack WebP also lacks prefers-color-scheme, so it never
    # asks for this file at all. The WebP everyone else gets is smaller than the
    # light PNG.
    out.save(LOGO_DARK, "PNG", optimize=True)
    out.save(LOGO_DARK.with_suffix(".webp"), "WEBP", quality=WEBP_QUALITY, method=6)
    print(f"[write] {LOGO_DARK.name}  (lettering below row {gap}: {changed} pixels "
          f"recoloured; the painting is byte-for-byte the original)")
    return True


def _twin_is_current(jpg: Path) -> bool:
    webp = jpg.with_suffix(".webp")
    return webp.is_file() and webp.stat().st_mtime >= jpg.stat().st_mtime


def _write_twin(jpg: Path) -> None:
    """WebP beside a JPEG this script does not itself derive (page backgrounds)."""
    with Image.open(jpg) as im:
        im.convert("RGB").save(jpg.with_suffix(".webp"), "WEBP", quality=WEBP_QUALITY, method=6)


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
            and _twin_is_current(full) and _twin_is_current(thumb)
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

    cover_current = (
        not args.force
        and BOOK_COVER_OUT.is_file()
        and BOOK_COVER_OUT.stat().st_mtime >= BOOK_COVER_MASTER.stat().st_mtime
        and _twin_is_current(BOOK_COVER_OUT)
    )
    if not cover_current:
        stale += 1
        if args.check:
            print("STALE  assets/img/book-cover.jpg  (canonical English cover is newer)")
        else:
            with Image.open(BOOK_COVER_MASTER) as im:
                im = ImageOps.exif_transpose(im)
                if im.mode != "RGB":
                    im = im.convert("RGB")
                _save_resized(im, BOOK_COVER_OUT, BOOK_COVER_EDGE)
            print(f"wrote  {BOOK_COVER_OUT.relative_to(SITE)}")

    for jpg in STANDING:
        if not jpg.is_file() or (not args.force and _twin_is_current(jpg)):
            continue
        stale += 1
        if args.check:
            print(f"STALE  {jpg.with_suffix('.webp').relative_to(SITE)}  (WebP twin missing or older)")
        else:
            _write_twin(jpg)
            print(f"wrote  {jpg.with_suffix('.webp').relative_to(SITE)}")

    if not _write_band(args.check):
        stale += 1
    if not _write_logo_dark(args.check):
        stale += 1
    if not _write_collection_thumbs(args.check):
        stale += 1
    if not _write_excerpt_mark(args.check):
        stale += 1
    if stale == 0:
        print(f"gallery and book cover in sync with {COVERPICS} ({len(_masters())} paintings)")
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
