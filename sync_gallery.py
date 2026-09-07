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
import io
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

SITE = Path(__file__).resolve().parent
COVERPICS = SITE.parent / "1_Sedaha" / "Volume1" / "CoverPics"  # book working repo (sibling). Edit if moved.
# Masters for galleries that are not a book. The book's paintings live in the book
# repo because the book is their source of truth; a standalone series has no such
# home, so it gets one beside the repos rather than inside either. Nothing here is
# committed anywhere -- these are full-size originals, and the site only ever holds
# what this script derives from them.
ARCHIVE = SITE.parent / "Paintings"
PAINTINGS_OUT = SITE / "assets" / "img" / "paintings"
OUT = PAINTINGS_OUT / "sounds"          # the book gallery, named for _write_band below
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

# == the naming rule ==
# NN_place_year_WxH -- 01_italy_2024_40x30.jpg. Underscore separates the fields, so
# a place of more than one word joins with hyphens (new-zealand) and keeps the field
# count fixed at four. An insert takes a second number rather than renumbering what
# follows it: 03_2_greece_2025_30x30 goes after 03, and every link already shared
# still lands where it did. Sizes are centimetres.
#
# Matched by SHAPE, not by position: a bare four-digit run is the year and
# digits-x-digits is the size wherever they fall, so 01_italy_40x30_2024 reads the
# same. A convention that punishes one slip in fifty files is a bad convention.
STRICT = "place-year-size"
STRICT_NAME = re.compile(
    r"^(?P<n>\d{2})(?:_(?P<insert>\d+))?_(?P<rest>.+)$"
)
STRICT_YEAR = re.compile(r"(?:^|_)(?P<year>1[89]\d\d|20\d\d)(?=_|$)")
STRICT_SIZE = re.compile(r"(?:^|_)(?P<w>\d{1,3})x(?P<h>\d{1,3})(?=_|$)")
STRICT_PLACE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAMING_RULE = "NN_place_year_WxH  (e.g. 01_italy_2024_40x30.jpg)"


def _parse(stem: str) -> dict | None:
    """The four fields of a strict filename, or None if it does not obey the rule."""
    head = STRICT_NAME.match(stem)
    if not head:
        return None
    rest = head["rest"]
    year, size = STRICT_YEAR.search(rest), STRICT_SIZE.search(rest)
    if not year or not size:
        return None
    # whatever is left once the year and the size are lifted out is the place
    place = rest
    for found in (year.group(0), size.group(0)):
        place = place.replace(found, "", 1)
    place = place.strip("_")
    if not STRICT_PLACE.match(place):
        return None
    return {
        "n": int(head["n"]),
        "insert": int(head["insert"] or 0),
        "place": place,
        "year": year["year"],
        "w": size["w"],
        "h": size["h"],
    }


def _titled(place: str) -> str:
    return " ".join(word.capitalize() for word in place.split("-"))


# How far a photograph's shape may sit from the frame size its name declares. A
# painting is photographed by hand, so a few percent of keystone and a millimetre of
# mount are expected; 8% is past that and into a different rectangle.
SHAPE_TOLERANCE = 0.08


def _misshaped(gallery: dict) -> list[str]:
    """Paintings whose declared frame size disagrees with the photograph.

    The size in the filename is not private bookkeeping -- it is printed under the
    painting for everyone to read. A landscape picture captioned "30 x 40 cm" is
    wrong in a way any visitor can see, and the file cannot tell you so. The pixels
    can, which makes this the one fact in the name that is checkable, so it is
    checked. The usual cause is width and height the wrong way round, and the
    message says so rather than leaving you to work it out.
    """
    if gallery.get("naming") != STRICT:
        return []
    problems = []
    for master in _masters(gallery):
        fields = _parse(master.stem)
        declared = int(fields["w"]) / int(fields["h"])
        try:
            with Image.open(master) as im:
                px = ImageOps.exif_transpose(im).size
        except OSError:
            problems.append(f"{master.name}: cannot be opened as an image")
            continue
        actual = px[0] / px[1]
        if abs(actual - declared) / declared <= SHAPE_TOLERANCE:
            continue
        flipped = int(fields["h"]) / int(fields["w"])
        if abs(actual - flipped) / flipped <= SHAPE_TOLERANCE:
            problems.append(f"{master.name}: the photograph is {fields['h']}x"
                            f"{fields['w']}, not {fields['w']}x{fields['h']} "
                            f"-- width comes first")
        else:
            shape = ("square" if 0.92 < actual < 1.08
                     else "landscape" if actual > 1 else "portrait")
            problems.append(f"{master.name}: declares {fields['w']}x{fields['h']} "
                            f"but the photograph is {shape} ({px[0]}x{px[1]})")
    return problems


def _misnamed(gallery: dict) -> list[str]:
    """Masters that break this gallery's naming rule. Empty for a lax gallery."""
    if gallery.get("naming") != STRICT:
        return []
    folder = gallery["masters"]
    if not folder.is_dir():
        return []
    return sorted(f.name for f in folder.iterdir()
                  if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")
                  and _parse(f.stem) is None)


# == the galleries ==
# One entry per collection. `masters` is the only source of truth: the paintings on
# the site are derived from it and nothing else, so a gallery with no masters folder
# is simply not built rather than half-built.
#
# `managed` says whether this script may rewrite the thumbnails block inside the
# gallery's own page. The Sounds page is False on purpose -- its captions ("Picture 12
# - End of Book One") were written by the author against the book's running order and
# cannot be recovered from a filename. A generator that overwrote them would be
# throwing away the only copy. New galleries start managed, where there is nothing
# hand-made to lose.
#
# `rename` maps a master's stem to the name it ships under; `tile` is the crop used
# on the collection index, and a source of None means "the first master".
GALLERIES = [
    {
        "slug": "sounds",
        "title": "Sedaha (Sounds) — Book One",
        "masters": COVERPICS,
        "rename": {"00_CoverPhoto": "cover"},
        "tile": {"source": "00_CoverPhoto", "centering": (0.5, 0.42)},
        "managed": False,
    },
    {
        "slug": "boteh-jegheh",
        "title": "The World Through Boteh-Jegheh",
        "masters": ARCHIVE / "boteh-jegheh",
        "rename": {},
        "tile": {"source": None, "centering": (0.5, 0.5)},
        "managed": True,
        # Every master must be named NN_place_year_WxH -- see STRICT_NAME. The
        # gallery is not built at all while one file breaks the rule, which is the
        # point: a series labelled from its filenames is only as good as the worst
        # filename in it, and the failure it prevents is one painting quietly
        # captioned "Picture 7" among forty that say where and when they are.
        "naming": STRICT,
        # place slug -> how the name is actually written, for the ones title-casing
        # cannot reach: accents, particles, capitalisation that is not initial caps.
        # Anything absent falls back to the slug with its hyphens opened out.
        "places": {
            # "cote-divoire": "Côte d'Ivoire",
            # "uk": "United Kingdom",
        },
    },
]


def _gallery(slug: str) -> dict:
    return next(g for g in GALLERIES if g["slug"] == slug)


def _derived_name(master: Path, rename: dict) -> str:
    return rename.get(master.stem, master.stem) + ".jpg"


def _masters(gallery: dict) -> list[Path]:
    """The paintings of one gallery, in the order they will hang.

    A missing folder is not an error: it is a gallery whose paintings have not been
    delivered yet, and the caller skips it. A file that breaks a strict gallery's
    naming rule is left out here and reported by _misnamed, so nothing is ever built
    from a half-understood name.
    """
    folder = gallery["masters"]
    if not folder.is_dir():
        return []
    found = [f for f in folder.iterdir()
             if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")]
    if gallery.get("naming") != STRICT:
        return sorted(found)
    # Sorted on the parsed number, not on the filename. Plain text sort puts
    # 03_2_greece before 03_italy -- "2" is below "i" -- which lands an insert in
    # front of the painting it was meant to follow.
    ordered = [(_parse(f.stem), f) for f in found]
    ordered = [(parsed, f) for parsed, f in ordered if parsed is not None]
    ordered.sort(key=lambda pair: (pair[0]["n"], pair[0]["insert"], pair[1].name))
    return [f for _parsed, f in ordered]


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
# The author's own crop, placed here by hand. It is the master for this one image:
# nothing derives it from the painting, because the choice of what to show -- how
# much tangle, how much thread, how much bare canvas -- was made by eye and cannot
# be expressed as a rectangle in a config. Replace the file to change the mark.
MARK_SRC = SITE / "assets" / "img" / "loose-end.jpg"
MARK_OUT = SITE / "assets" / "img" / "opening-mark.jpg"
# The author picked the crop: the loose end alone, on bare canvas, with none of the
# tangle it runs into. As it is -- no turn, no flip.
# 9% of the canvas is 135px on the site's own copy, which would have to be blown up
# to reach a 2x display. The CoverPics master is ~5500px wide, so the same crop comes
# out around 490px and is downscaled instead. The site copy is the fallback for when
# the book repo is not beside the site; it prints a warning rather than going soft
# without saying so.
MARK_WIDTH = 256


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
        # Mirrored, and only mirrored. In the file the thread trails off to the left,
        # away from the sentence it belongs to; flipped, the loose end runs toward
        # the words -- which is the whole point of putting it there. Done here rather
        # than with a CSS transform: one asset, arriving the right way round, nothing
        # for the compositor to redo on every scroll.
        mark = ImageOps.mirror(im.convert("RGB"))
    # Only ever scaled DOWN. The author's file is what it is; enlarging it would be
    # inventing detail that is not in the picture they chose.
    if mark.width > MARK_WIDTH:
        mark = mark.resize((MARK_WIDTH, round(MARK_WIDTH * mark.height / mark.width)),
                           LANCZOS)
    mark.info.clear()          # drops the EXIF the file arrived with
    mark.save(MARK_OUT, "JPEG", quality=QUALITY, optimize=True)
    mark.save(MARK_OUT.with_suffix(".webp"), "WEBP",
              quality=WEBP_QUALITY, method=6)
    print(f"[write] {MARK_OUT.name}  ({mark.width}x{mark.height} from {src.name}, "
          f"the author's own file, mirrored so the loose end faces the text)")
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

# == tiles for series that have no gallery yet ==
# A tile saying "Coming soon" over nothing at all is an empty frame, and that is why
# these were prose for so long. With a photograph behind it the objection goes away:
# there is something to look at, and the tile is a promise rather than a broken link.
# It is still NOT a gallery -- no page, no <a>, and no entry in GALLERIES, so nothing
# derives lightbox images or thumbnails for it. One picture, one tile, and that is all
# until the series is real.
PLACEHOLDER_TILES = {
    "yarn-truck": {"masters": ARCHIVE / "yarn-truck", "source": "01",
                   "centering": (0.5, 0.5)},
}


def _write_one_tile(slug: str, src: Path, centering: tuple, check: bool) -> bool:
    """One 4:3 tile, cropped and written, or reported stale."""
    out = COLLECTION_DIR / f"{slug}.jpg"
    fresh = (out.is_file() and out.stat().st_mtime >= src.stat().st_mtime
             and _twin_is_current(out))
    if fresh:
        print(f"[ok]    paintings/index/{out.name}: current")
        return True
    if check:
        print(f"[stale] paintings/index/{out.name}")
        return False
    with Image.open(src) as im:
        tile = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"),
                            COLLECTION_SIZE, method=LANCZOS, centering=centering)
    tile.info.clear()             # no EXIF, no ICC: it is a 220px tile
    tile.save(out, "JPEG", quality=BAND_JPEG_QUALITY, optimize=True)
    tile.save(out.with_suffix(".webp"), "WEBP",
              quality=BAND_WEBP_QUALITY, method=6)
    print(f"[write] paintings/index/{out.name}  "
          f"({tile.width}x{tile.height} from {src.name}, "
          f"centred {centering[0]:.2f},{centering[1]:.2f})")
    return True


def _write_collection_thumbs(check: bool) -> bool:
    """A 4:3 tile per gallery, and per series that is only promised so far."""
    ok = True
    COLLECTION_DIR.mkdir(parents=True, exist_ok=True)
    for gallery in GALLERIES:
        slug, spec = gallery["slug"], gallery["tile"]
        masters = _masters(gallery)
        if not masters:
            continue          # no paintings yet; _derive_gallery has already said so
        wanted = spec["source"]
        src = masters[0] if wanted is None else next(
            (m for m in masters if m.stem == wanted), None)
        if src is None:
            print(f"[warn]  collection tile {slug}: master {wanted} not found")
            ok = False
            continue
        ok &= _write_one_tile(slug, src, spec["centering"], check)

    for slug, spec in PLACEHOLDER_TILES.items():
        folder = spec["masters"]
        src = folder / f"{spec['source']}.jpg" if folder.is_dir() else None
        if src is None or not src.is_file():
            print(f"[wait]  {slug}: no photograph in {folder}")
            continue          # a promise with nothing behind it stays prose
        ok &= _write_one_tile(slug, src, spec["centering"], check)
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


def _derive_gallery(gallery: dict, check: bool, force: bool) -> int:
    """The full-size and thumbnail pair for every painting in one gallery.

    Returns the number of derived files found stale. A gallery whose masters folder
    is missing or empty is announced and skipped: an unbuilt gallery is a gallery
    waiting for paintings, not a failure.
    """
    masters = _masters(gallery)
    if not masters:
        print(f"[wait]  {gallery['slug']}: no paintings in {gallery['masters']}")
        return 0

    out = PAINTINGS_OUT / gallery["slug"]
    out_th = out / "th"
    out_th.mkdir(parents=True, exist_ok=True)

    stale = 0
    for master in masters:
        name = _derived_name(master, gallery["rename"])
        full, thumb = out / name, out_th / name
        current = (
            not force
            and full.is_file() and thumb.is_file()
            and full.stat().st_mtime >= master.stat().st_mtime
            and thumb.stat().st_mtime >= master.stat().st_mtime
            and _twin_is_current(full) and _twin_is_current(thumb)
        )
        if current:
            continue
        stale += 1
        if check:
            print(f"STALE  {gallery['slug']}/{name}  (master {master.name} is newer)")
            continue
        with Image.open(master) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode != "RGB":  # PNG masters (RGBA) — flatten
                im = im.convert("RGB")
            _save_resized(im, full, FULL_EDGE)
            _save_resized(im, thumb, THUMB_EDGE)
        print(f"wrote  {full.relative_to(SITE)}  +  {thumb.relative_to(SITE)}")
    return stale


# == the thumbnails on a gallery's own page ==
# Managed the way sync_appnav and sync_footers manage theirs: a marked block the
# script owns, inside a page nobody generates. What goes in it cannot be hand-kept in
# step -- every <img> carries the derived thumbnail's real width and height, so the
# grid reserves the right box before the picture arrives and nothing jumps as the
# page loads. Those numbers come from the files themselves, which is exactly the kind
# of bookkeeping a person should not be doing by eye.
GALLERY_START = ("<!-- GALLERY:START (managed by sync_gallery.py — the paintings on "
                 "disk decide this block; edit the script, not the page) -->")
GALLERY_END = "<!-- GALLERY:END -->"
GALLERY_RE = re.compile(re.escape(GALLERY_START) + r".*?" + re.escape(GALLERY_END), re.S)


ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _roman(n: int) -> str:
    out = ""
    for value, sign in ROMAN:
        while n >= value:
            out, n = out + sign, n - value
    return out


def _labels(gallery: dict, masters: list[Path]) -> list[dict]:
    """What each painting is called, in four places that want different things.

    label   -- under the thumbnail. Short: it sits over a 220px tile.
    caption -- in the lightbox, where there is room for the whole museum line.
    alt     -- read aloud. Dimensions are noise in a spoken description of a
               picture, so they are the one field the caption has and this does not.
    slug    -- the painting's own address, /paintings/boteh-jegheh/#iran-ii.

    Where a place is painted more than once, every one of them is numbered --
    Iran I through Iran IV -- the way a gallery numbers variants of one subject.
    Numbering only the second would leave the first looking like the whole of it.

    This is not decoration. The address is built from the label, so two paintings
    called "Iran" would share one, #iran would always open whichever came first,
    and the other three could not be linked to at all. Disambiguating by year, as
    an earlier version did, fixes nothing here: all ten were painted in 2026.
    """
    parsed = [_parse(m.stem) if gallery.get("naming") == STRICT else None
              for m in masters]
    names = [gallery.get("places", {}).get(p["place"]) or _titled(p["place"])
             if p else None for p in parsed]

    out, number, seen = [], 0, {}
    for fields, name in zip(parsed, names):
        if not fields:
            number += 1
            worded = f"Picture {number}"
            out.append({"label": worded, "caption": worded, "slug": "",
                        "alt": f"{worded}, from {gallery['title']}"})
            continue
        if names.count(name) > 1:
            seen[name] = seen.get(name, 0) + 1
            numeral = _roman(seen[name])
            label, slug = f"{name} {numeral}", f"{fields['place']}-{numeral.lower()}"
        else:
            label, slug = name, fields["place"]
        out.append({
            "label": label,
            # built from the place SLUG, not the shown name, so a place written with
            # accents or an apostrophe still has an ASCII address
            "slug": slug,
            "caption": f"{label} &middot; {fields['year']} &middot; "
                       f"{fields['w']} &times; {fields['h']} cm",
            "alt": f"{label}, {fields['year']}, from {gallery['title']}",
        })
    return out


def _write_gallery_markup(gallery: dict, check: bool) -> bool:
    """Rewrite the marked thumbnails block on one managed gallery's page."""
    if not gallery.get("managed"):
        return True                     # the author's own captions live there
    page = SITE / "paintings" / gallery["slug"] / "index.html"
    masters = _masters(gallery)
    if not page.is_file() or not masters:
        return True

    base = f"/assets/img/paintings/{gallery['slug']}"
    shots = []
    for position, (master, words) in enumerate(zip(masters,
                                                   _labels(gallery, masters))):
        name = _derived_name(master, gallery["rename"])
        stem = Path(name).stem
        thumb = PAINTINGS_OUT / gallery["slug"] / "th" / name
        if not thumb.is_file():
            print(f"[warn]  {gallery['slug']}: {name} has no thumbnail yet")
            return False
        with Image.open(thumb) as im:
            width, height = im.size
        # The first painting is the one a reader is waiting for, so it is fetched
        # early; the next two are usually still above the fold on a laptop; from the
        # fourth on, nobody is looking yet and the browser can take its time.
        priority = (' fetchpriority="high"' if position == 0
                    else ' loading="lazy"' if position >= 3 else "")
        shots.append(
            f'      <a class="shot" href="{base}/{name}"'
            f' data-caption="{words["caption"]}"'
            + (f' data-slug="{words["slug"]}"' if words["slug"] else "") +
            f' aria-haspopup="dialog"><picture>'
            f'<source srcset="{base}/th/{stem}.webp" type="image/webp">'
            f'<img{priority} src="{base}/th/{name}" width="{width}" height="{height}"'
            f' alt="{words["alt"]}"></picture>'
            f'<span class="shot-label">{words["label"]}</span></a>'
        )

    # The block owns the whole grid, not just its contents, so a gallery with no
    # paintings yet is a sentence saying so rather than an empty frame -- the same
    # reason the collection index names its unpainted series instead of tiling them.
    block = (GALLERY_START + "\n"
             '    <div class="gallery">\n'
             + "\n".join(shots) + "\n"
             '    </div>\n'
             '    ' + GALLERY_END)
    html = io.open(page, encoding="utf-8").read()
    if not GALLERY_RE.search(html):
        print(f"[warn]  {gallery['slug']}: no GALLERY markers on its page")
        return False
    # a lambda, not the replacement string: a caption containing a backslash or a
    # \g would otherwise be read as a group reference and mangled
    updated = GALLERY_RE.sub(lambda _m: block, html)
    if updated == html:
        print(f"[ok]    paintings/{gallery['slug']}/index.html: current")
        return True
    if check:
        print(f"[stale] paintings/{gallery['slug']}/index.html")
        return False
    io.open(page, "w", encoding="utf-8", newline="").write(updated)
    print(f"[write] paintings/{gallery['slug']}/index.html  ({len(shots)} paintings)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--check", action="store_true", help="report drift only; change nothing; exit 1 if stale")
    ap.add_argument("--force", action="store_true", help="regenerate every derived image")
    args = ap.parse_args()

    if not COVERPICS.is_dir():
        sys.exit(f"CoverPics not found: {COVERPICS}")
    OUT_TH.mkdir(parents=True, exist_ok=True)

    # Nothing is built while a name is wrong, in any gallery -- not even the ones
    # that are fine. A misnamed file is not a small defect to be worked around: it
    # is a painting whose place, year and size are unknown to the site, and the
    # sync would otherwise sail past it and publish the other thirty-nine. Every
    # offender is listed, so one run tells you the whole of what to rename.
    broken = [(g["slug"], name) for g in GALLERIES for name in _misnamed(g)]
    if broken:
        for slug, name in broken:
            print(f"[name]  {slug}: {name}")
        print(f"\n{len(broken)} file(s) do not match {NAMING_RULE}")
        print("        NN     two digits, and the order they hang in; an insert")
        print("               takes a second number (03_2) rather than renumbering")
        print("        place  lower case ASCII, hyphens between words (new-zealand)")
        print("        year   four digits, the year painted")
        print("        WxH    centimetres, width first (40x30)")
        print("nothing was built. Rename these and run again.")
        return 1

    wrong = [(g["slug"], note) for g in GALLERIES for note in _misshaped(g)]
    if wrong:
        for slug, note in wrong:
            print(f"[size]  {slug}: {note}")
        print(f"\n{len(wrong)} painting(s) declare a frame size the photograph "
              f"contradicts.")
        print("        That size is printed under the painting for visitors to read,")
        print("        so nothing is built until the two agree. Rename to the true")
        print("        size and run again.")
        return 1

    stale = 0
    for gallery in GALLERIES:
        stale += _derive_gallery(gallery, args.check, args.force)

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
    for gallery in GALLERIES:
        if not _write_gallery_markup(gallery, args.check):
            stale += 1
    if stale == 0:
        counts = ", ".join(f"{g['slug']} {len(_masters(g))}" for g in GALLERIES)
        print(f"galleries and book cover in sync with their masters ({counts})")
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
