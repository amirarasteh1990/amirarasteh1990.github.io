#!/usr/bin/env python3
"""
make_painting_downloads.py -- the downloadable copy of every painting.

Each painting of every gallery sync_gallery.py knows, at 3000 px on its long edge
(a smaller master is never enlarged), JPEG quality 90, with the author's badge in
the bottom-right corner: a light rounded panel holding the painting-logo (the whole
top of assets/img/logo-lockup.png, never cropped), the Persian/Latin lettering
beside it, and "arasteh.art" centred under the lettering. The design is the one the
author approved from the painting_badge.py prototype; badge() keeps it exactly.

The files go OUTSIDE the repo, beside the masters:

    ../Paintings/_downloads/<gallery>/Arasteh_<gallery>_<painting>.jpg

named by sync_gallery.download_name() after the painting's address on the site.
publish_paintings.py uploads them to the `paintings` release; the lightbox links
there, so GitHub counts each download the way it counts the books.

    python make_painting_downloads.py            # build what is missing or stale
    python make_painting_downloads.py --check    # report only; exit 1 if stale
    python make_painting_downloads.py --list     # gallery, master, file, one per line

A file is rebuilt only when its master changed (size and time first, then the
bytes) or the badge itself changed: the source of badge() and _logo_parts(), the
DESIGN numbers, and the logo file. Editing anything else here rebuilds nothing.
The output carries no EXIF: the masters hold the camera's GPS position, and that
must not travel with a public download. Like the site's own copies it carries no
colour profile either, so it looks as the painting does on the site.

Never writes to the masters, the book repo, git or GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import sync_gallery as sg

SITE = sg.SITE
OUT_ROOT = sg.ARCHIVE / "_downloads"
STATE = OUT_ROOT / "_state.json"
LOGO = sg.LOGO
FONT = Path("C:/Windows/Fonts/georgia.ttf")

# The approved design, as numbers. Changing one rebuilds every download.
DESIGN = {
    "edge": 3000,               # long edge in px; a smaller master keeps its own
    "quality": 90,              # JPEG
    "logo": 0.041,              # logo height, as a share of the long edge
    "panel": (255, 255, 255, 215),
    "ink": (40, 40, 40, 255),   # the "arasteh.art" line
    "url": "arasteh.art",
    "colour": "sRGB",           # masters are Display P3; convert so every viewer shows true colour
}


def _logo_parts() -> tuple[Image.Image, Image.Image]:
    """The painting (every row above the first clear row) and the lettering below.

    Split where sync_gallery._write_logo_dark splits it: the painting is the block of
    rows opaque nearly all the way across, the lettering starts after the first fully
    clear row under it. For today's lockup that row is 498, as in the prototype."""
    lockup = Image.open(LOGO).convert("RGBA")
    w, h = lockup.size
    alpha = lockup.getchannel("A").load()
    solid = [y for y in range(h) if sum(1 for x in range(w) if alpha[x, y] > 40) > w * 0.9]
    gap = next((y for y in range(solid[-1] + 1, h)
                if all(alpha[x, y] <= 40 for x in range(w))), None) if solid else None
    if gap is None:
        raise SystemExit("logo-lockup.png: painting and lettering not separable")
    paint = lockup.crop((0, 0, w, gap))
    text = lockup.crop((0, gap, w, h))
    return paint, text.crop(text.getbbox())


def badge(src: Image.Image) -> Image.Image:
    """The painting at DESIGN['edge'] with the badge composited bottom-right."""
    paint, text = _logo_parts()
    s = DESIGN["edge"] / max(src.size)
    if s < 1:                   # never upscale a smaller master
        src = src.resize((round(src.size[0] * s), round(src.size[1] * s)), Image.LANCZOS)
    W, H = src.size
    ph = int(max(W, H) * DESIGN["logo"])
    pw = round(paint.size[0] * ph / paint.size[1])
    pl = paint.resize((pw, ph), Image.LANCZOS)
    th = int(ph * 0.60)
    tw = round(text.size[0] * th / text.size[1])
    tl = text.resize((tw, th), Image.LANCZOS)
    f = ImageFont.truetype(str(FONT), int(ph * 0.205))
    t = DESIGN["url"]
    bx = ImageDraw.Draw(src).textbbox((0, 0), t, font=f)
    urlw = bx[2] - bx[0]
    pad = int(ph * 0.16)
    gap = int(ph * 0.14)
    colw = max(tw, urlw)
    boxw = pad + pw + gap + colw + pad
    boxh = pad + ph + pad
    m = int(max(W, H) * 0.012)
    x0, y0 = W - boxw - m, H - boxh - m
    panel = Image.new("RGBA", (boxw, boxh), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle((0, 0, boxw - 1, boxh - 1), radius=max(4, int(ph * 0.12)),
                         fill=DESIGN["panel"])
    panel.paste(pl, (pad, pad), pl)
    cx = pad + pw + gap
    ty = pad + int(ph * 0.05)
    panel.paste(tl, (cx + (colw - tw) // 2, ty), tl)
    uy = ty + th + int(ph * 0.08)
    pd.text((cx + (colw - urlw) // 2 - bx[0], uy - bx[1]), t, fill=DESIGN["ink"], font=f)
    out = src.convert("RGBA")
    out.alpha_composite(panel, (x0, y0))
    return out.convert("RGB")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def badge_fingerprint() -> str:
    """What the badge is made of. Any change here means every file is out of date."""
    h = hashlib.sha256()
    for part in (inspect.getsource(_logo_parts), inspect.getsource(badge),
                 json.dumps(DESIGN, sort_keys=True)):
        h.update(part.encode("utf-8"))
    h.update(_sha256(LOGO).encode("ascii"))
    return h.hexdigest()


@dataclass(frozen=True)
class Download:
    gallery: str        # gallery slug
    master: Path
    painting: str       # its address on the site
    name: str           # the release asset name
    url: str            # where the lightbox links
    path: Path          # the local file under OUT_ROOT


def expected() -> tuple[list[Download], list[str]]:
    """Every download the site should offer, in hanging order, and the problems
    that keep a painting from having one (a master its unmanaged page does not show)."""
    out, problems = [], []
    for gallery in sg.GALLERIES:
        for master, painting in sg.painting_addresses(gallery):
            if painting is None:
                problems.append(f"{gallery['slug']}: {master.name} is not shown on its page, "
                                f"so it has no address and no download")
                continue
            name = sg.download_name(gallery, painting)
            out.append(Download(gallery["slug"], master, painting, name,
                                sg.download_url(gallery, painting),
                                OUT_ROOT / gallery["slug"] / name))
    names = [d.name for d in out]
    for dup in sorted({n for n in names if names.count(n) > 1}):
        problems.append(f"two paintings would both download as {dup}")
    return out, problems


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _why_stale(d: Download, record: dict | None, fingerprint: str) -> str | None:
    """None when the file on disk is the one this master and badge make."""
    if not d.path.is_file():
        return "missing"
    if not record or record.get("badge") != fingerprint:
        return "badge changed" if record else "not built by this script"
    out = d.path.stat()
    if (record.get("out_size"), record.get("out_mtime_ns")) != (out.st_size, out.st_mtime_ns):
        return "the file was changed after it was built"
    st = d.master.stat()
    if (record.get("master_size"), record.get("master_mtime_ns")) == (st.st_size, st.st_mtime_ns):
        return None
    # touched but perhaps not changed: only the bytes decide
    return None if record.get("master_sha256") == _sha256(d.master) else "master changed"


def stale(downloads: list[Download] | None = None) -> list[tuple[Download, str]]:
    """The downloads that need building, with the reason. Writes nothing."""
    if downloads is None:
        downloads, _problems = expected()
    state, fingerprint = _load_state().get("files", {}), badge_fingerprint()
    found = []
    for d in downloads:
        why = _why_stale(d, state.get(f"{d.gallery}/{d.name}"), fingerprint)
        if why:
            found.append((d, why))
    return found


def _build(d: Download) -> tuple[int, int]:
    with Image.open(d.master) as im:
        icc = im.info.get("icc_profile")
        im = ImageOps.exif_transpose(im)
        if icc:                     # Display P3 (or any embedded profile) -> sRGB
            from io import BytesIO
            from PIL import ImageCms
            im = ImageCms.profileToProfile(im.convert("RGB"), ImageCms.ImageCmsProfile(BytesIO(icc)),
                                           ImageCms.createProfile("sRGB"), outputMode="RGB")
        if im.mode != "RGB":        # PNG masters (RGBA): flattened as sync_gallery does
            im = im.convert("RGB")
        out = badge(im)
    out.info.clear()                # no EXIF (the masters carry GPS), no profile
    d.path.parent.mkdir(parents=True, exist_ok=True)
    tmp = d.path.with_name(d.path.name + ".tmp")
    out.save(tmp, "JPEG", quality=DESIGN["quality"], optimize=True)
    os.replace(tmp, d.path)
    return out.size


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the badged 3000 px painting downloads.")
    ap.add_argument("--check", action="store_true",
                    help="report missing or stale downloads; change nothing; exit 1 if any")
    ap.add_argument("--list", action="store_true", help="print gallery, master and file name")
    args = ap.parse_args()

    downloads, problems = expected()
    for note in problems:
        print(f"[warn]  {note}")
    if args.list:
        for d in downloads:
            print(f"{d.gallery}\t{d.master.name}\t{d.name}")
        return 1 if problems else 0
    if not FONT.is_file():
        print(f"[warn]  font not found: {FONT}")
        return 1

    todo = stale(downloads)
    wanted = {d.path for d in downloads}
    for folder in sorted(p for p in OUT_ROOT.iterdir() if p.is_dir()) if OUT_ROOT.is_dir() else []:
        for f in sorted(folder.glob("*.jpg")):
            if f not in wanted:
                print(f"[orphan] _downloads/{folder.name}/{f.name}  (no painting uses this "
                      f"name now; it is never uploaded)")

    if args.check:
        for d, why in todo:
            print(f"[stale] _downloads/{d.gallery}/{d.name}  ({why})")
        if not todo and not problems:
            print(f"[ok]    {len(downloads)} painting downloads current in {OUT_ROOT}")
        return 1 if (todo or problems) else 0

    state = _load_state()
    files = state.get("files", {})
    fingerprint = badge_fingerprint()
    for d, why in todo:
        size = _build(d)
        st, out = d.master.stat(), d.path.stat()
        files[f"{d.gallery}/{d.name}"] = {
            "master": str(d.master), "master_size": st.st_size,
            "master_mtime_ns": st.st_mtime_ns, "master_sha256": _sha256(d.master),
            "badge": fingerprint, "out_size": out.st_size, "out_mtime_ns": out.st_mtime_ns,
            "out_sha256": _sha256(d.path),
        }
        print(f"[write] _downloads/{d.gallery}/{d.name}  ({size[0]}x{size[1]}, "
              f"{out.st_size / 1e6:.1f} MB; {why})")
        # saved after every file, so an interrupted run keeps what it finished
        OUT_ROOT.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"files": files}, indent=1, sort_keys=True),
                         encoding="utf-8")
    print(f"{len(downloads)} painting downloads, {len(todo)} built, in {OUT_ROOT}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
