#!/usr/bin/env python3
"""
check.py — one command that answers "is the site consistent?"

The site is stamped together by eight scripts: the nav shell, the footer, the head
block, the book text, the gallery derivatives, the 111 Opening pages, the name
subsets. Each can already answer --check on its own, but nobody remembers to run
eight of them, and the interesting failures are the ones no single script owns: a
link pointing at a file that was renamed, a service worker caching a path that no
longer exists, a hand-written page drifting away from the generator that owns the
same markup everywhere else.

So this runs all of them, then the checks between them:

  * every sync/build script's own --check
  * node --check on each script in assets/js and on sw.js  (skipped if no node)
  * every local href/src/srcset in all 124 pages resolves to a file on disk
  * every url(...) in the stylesheet resolves, and every path in sw.js's SHELL
  * sitemap.xml, feed.xml and the manifest parse, and every JSON-LD block is JSON
  * the three hand-written Opening pages still carry the generator's own hreflang
    cluster and reading toolbar, byte for byte

Nothing here writes: it is safe to run at any time, and it is the last thing to
run before a push.

    python check.py            everything
    python check.py --quick    skip the script --checks (the slow part)
"""
from __future__ import annotations

import argparse
import datetime
import html as htmllib
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import xml.dom.minidom
from pathlib import Path

SITE = Path(__file__).resolve().parent

SCRIPTS = ["sync_appnav.py", "sync_footers.py", "sync_head.py", "sync_book_text.py",
           "sync_gallery.py", "build_read_pages.py", "build_name_fonts.py"]

SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "javascript:", "data:")

failures: list[str] = []


def report(label: str, ok: bool, detail: str = "") -> bool:
    print(("[ok]    " if ok else "[FAIL]  ") + label + (("  " + detail) if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def pages() -> list[Path]:
    return sorted(p for p in SITE.rglob("*.html") if ".git" not in p.parts)


# --------------------------------------------------------------- the scripts
def run_scripts() -> None:
    for name in SCRIPTS:
        proc = subprocess.run([sys.executable, name, "--check"], cwd=SITE,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        bad = [ln for ln in (proc.stdout or "").splitlines()
               if ln.startswith(("[drift]", "[stale]", "[warn]"))]
        detail = bad[0] if bad else ""
        report(f"{name} --check", proc.returncode == 0, detail)


def run_node() -> None:
    node = shutil.which("node")
    if not node:
        print("[skip]  node --check (node not installed)")
        return
    files = sorted((SITE / "assets" / "js").glob("*.js")) + [SITE / "sw.js"]
    bad = []
    for f in files:
        proc = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        if proc.returncode != 0:
            bad.append(f"{f.name}: {proc.stderr.strip().splitlines()[0]}")
    report(f"node --check on {len(files)} scripts", not bad, bad[0] if bad else "")


# ------------------------------------------------------------ the link graph
def resolve(page: Path, url: str) -> Path | None:
    """Where a link points on disk, or None if it is not ours to check."""
    url = url.strip()
    if not url or url.startswith("#") or url.lower().startswith(SKIP_SCHEMES):
        return None
    url = urllib.parse.urldefrag(url)[0].split("?")[0]
    if not url:
        return None
    url = urllib.parse.unquote(url)
    target = (SITE / url.lstrip("/")) if url.startswith("/") else (page.parent / url)
    if url.endswith("/"):
        target = target / "index.html"
    return target


def links_in(body: str) -> list[str]:
    out = re.findall(r'(?:href|src)="([^"]+)"', body)
    for sets in re.findall(r'srcset="([^"]+)"', body):
        out += [part.strip().split(" ")[0] for part in sets.split(",") if part.strip()]
    return out


def crawl() -> None:
    missing = []
    for page in pages():
        body = page.read_text(encoding="utf-8")
        for url in links_in(body):
            target = resolve(page, htmllib.unescape(url))
            if target is not None and not target.exists():
                missing.append(f"{page.relative_to(SITE).as_posix()} -> {url}")
    report(f"{len(pages())} pages: every local link resolves", not missing,
           f"{len(missing)} broken, first: {missing[0]}" if missing else "")

    css = SITE / "assets" / "css" / "style.css"
    body = css.read_text(encoding="utf-8")
    bad = [u for u in re.findall(r'url\(([^)]+)\)', body)
           if not u.strip('"\'').startswith("data:")
           and not (SITE / u.strip('"\'').lstrip("/")).exists()]
    report("style.css: every url() resolves", not bad, bad[0] if bad else "")
    report("style.css: braces balanced", body.count("{") == body.count("}"),
           f"{body.count('{')} open, {body.count('}')} close")

    sw = (SITE / "sw.js").read_text(encoding="utf-8")
    shell = re.search(r"var SHELL = \[(.*?)\];", sw, re.S)
    paths = re.findall(r"'([^']+)'", shell.group(1)) if shell else []
    gone = [p for p in paths if not (SITE / (p.lstrip("/") or "index.html")).exists()
            and not (SITE / p.lstrip("/") / "index.html").exists()]
    report(f"sw.js: {len(paths)} shell paths exist", bool(paths) and not gone,
           gone[0] if gone else ("SHELL not found" if not paths else ""))


# ---------------------------------------------------------- machine-readable
def structured() -> None:
    for name in ("sitemap.xml", "feed.xml"):
        try:
            xml.dom.minidom.parse(str(SITE / name))
            report(f"{name} parses", True)
        except Exception as exc:  # noqa: BLE001 - the message is the finding
            report(f"{name} parses", False, str(exc))
    try:
        json.loads((SITE / "manifest.webmanifest").read_text(encoding="utf-8"))
        report("manifest.webmanifest parses", True)
    except Exception as exc:  # noqa: BLE001
        report("manifest.webmanifest parses", False, str(exc))

    bad, found = [], 0
    for page in pages():
        for block in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>',
                page.read_text(encoding="utf-8"), re.S):
            found += 1
            try:
                json.loads(block)
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{page.relative_to(SITE).as_posix()}: {exc}")
    report(f"{found} JSON-LD blocks parse", not bad, bad[0] if bad else "")


# ------------------------------------------------- hand-written vs generated
def hand_written() -> None:
    """The three hand-maintained Opening pages carry markup the generator owns for
    the other 111. Nothing stamps it there, so compare it here."""
    sys.path.insert(0, str(SITE))
    import build_read_pages as gen

    hand = ["sedaha/read/index.html", "sedaha/read/fa/index.html", "sedaha/read/da/index.html"]
    for what, want in (("hreflang cluster", gen.alternates()),
                       ("reading toolbar", gen.reader_tools_html())):
        off = [rel for rel in hand
               if want not in (SITE / rel).read_text(encoding="utf-8")]
        report(f"EN/FA/DA Opening pages: {what} matches the generator", not off,
               ", ".join(off))

    # the language strip differs per page (each marks a different language current),
    # so ask the generator for the one that page should be carrying
    off = [rel for rel, slug in zip(hand, ("", "fa/", "da/"))
           if gen.op_langs_html(slug) not in (SITE / rel).read_text(encoding="utf-8")]
    report("EN/FA/DA Opening pages: language strip matches the generator", not off,
           ", ".join(off))

    stale = [rel for rel in hand
             if "read-kicker" in (SITE / rel).read_text(encoding="utf-8")]
    report("EN/FA/DA Opening pages: no leftover English kicker", not stale, ", ".join(stale))

    missing = [rel for rel in hand
               if "/assets/js/reader.js" not in (SITE / rel).read_text(encoding="utf-8")]
    report("EN/FA/DA Opening pages: reader.js loaded", not missing, ", ".join(missing))


def availability() -> None:
    """One availability story, told the same everywhere.

    The generator can be perfectly happy while the page is wrong, and the reason
    this exists is that Italian was complete and downloadable for weeks while
    three pages said three. /sedaha/ is a doorway now and names no language at
    all, so the guard moved with the data: what must hold is that editions.js
    carries every edition the site shows, with the files each one really has."""
    sys.path.insert(0, str(SITE))
    import build_read_pages as gen

    rows = gen.status_rows()
    site_rows = gen.shown(rows)
    done = [r["en"] for r in gen.complete_rows(site_rows)]
    book = (SITE / "sedaha" / "index.html").read_text(encoding="utf-8")
    data = (SITE / "assets" / "js" / "editions.js").read_text(encoding="utf-8")

    listed = re.findall(r'"slug":"([^"]+)"', data)
    report(f"editions.js carries all {len(site_rows)} languages the site shows",
           len(listed) == len(site_rows),
           f"{len(listed)} in the data, {len(site_rows)} in the record")

    ready = [ln for ln in data.splitlines() if '"state":"ready"' in ln]
    report(f"editions.js marks all {len(done)} complete editions as such",
           len(ready) == len(done), f"{len(ready)} ready in the data, {len(done)} complete")

    fileless = [ln for ln in ready if '"files"' not in ln]
    report("every complete edition in the data has files to offer", not fileless,
           re.search(r'"en":"([^"]+)"', fileless[0]).group(1) if fileless else "")

    stray = len(re.findall(r'<div class="ed-featured"|<li class="dl-row"|class="continent"',
                           book))
    report("/sedaha/ still holds no catalogue of its own", stray == 0,
           f"{stray} catalogue elements found")

    home = (SITE / "index.html").read_text(encoding="utf-8")
    sentence = gen.availability(rows)["long"]
    tellers = {"index.html": home, "sedaha/index.html": book}
    off = [name for name, body in tellers.items() if sentence not in body]
    report("the availability sentence is the same on every page that tells it",
           not off, ", ".join(off))

    stale = [name for name, body in tellers.items()
             if re.search(r"free to read in .*hundred", body)
             and "og:image:alt" not in body.split("hundred")[0][-200:]]
    report("no page still claims the whole book in a hundred languages", not stale,
           ", ".join(stale))

    # An edition the author has asked the site not to carry must be absent from all
    # of it, not merely unlinked: the page, the lists, the hreflang cluster, the
    # sitemap, the feed, the search aliases. The book keeps it; the site is quiet.
    for slug in sorted(gen.HIDDEN_SLUGS):
        row = next((r for r in rows if r["slug"] == slug), None)
        needles = [f"/sedaha/read/{slug}/", f'hreflang="{row["lang"]}"' if row else "",
                   row["native"] if row else "", row["en"] if row else ""]
        needles = [n for n in needles if n]
        seen = []
        for path in list(pages()) + [SITE / "sitemap.xml", SITE / "feed.xml",
                                     SITE / "assets" / "js" / "lang-alias.js"]:
            body = path.read_text(encoding="utf-8")
            hit = [n for n in needles if n in body]
            if hit:
                seen.append(f"{path.relative_to(SITE).as_posix()} ({hit[0]})")
        name = row["en"] if row else slug
        report(f"{name} is hidden from the site, as asked", not seen,
               f"{len(seen)} page(s), first: {seen[0]}" if seen else "")


def logo() -> None:
    """The dark logo must be the same painting, and must arrive by CSS.

    Two failures are being guarded against, both of which happened. The first: the
    dark variant was made by recolouring palette entries, which the painting shares,
    so the artwork itself was repainted. Nothing in the page would have shown that.
    So the painting's pixels are compared against the light file directly.

    The second: a <picture media="(prefers-color-scheme:dark)"> looks right and
    ignores the reader's own theme choice, because that choice works by re-pointing
    the stylesheet's media rule and has no effect on markup. So the logo must not be
    an <img> at all, and the cream plaque it used to sit on must be gone."""
    light = SITE / "assets" / "img" / "logo-lockup.png"
    dark = SITE / "assets" / "img" / "logo-lockup-dark.png"
    if not report("the dark logo exists", dark.exists(),
                  "" if dark.exists() else "run python sync_gallery.py"):
        return

    try:
        from PIL import Image
    except ImportError:
        report("the dark logo keeps the painting", True, "skipped: Pillow not installed")
    else:
        a, b = (Image.open(p).convert("RGBA") for p in (light, dark))
        if a.size != b.size:
            report("the dark logo keeps the painting", False,
                   f"{a.size} against {b.size}")
        else:
            w, h = a.size
            pa, pb = a.load(), b.load()
            # the painting is every row above the first fully clear one
            solid = [y for y in range(h)
                     if sum(1 for x in range(w) if pa[x, y][3] > 40) > w * 0.9]
            gap = next((y for y in range(solid[-1] + 1, h)
                        if all(pa[x, y][3] <= 40 for x in range(w))), h)
            bad = next(((x, y) for y in range(gap) for x in range(w)
                        if pa[x, y] != pb[x, y]), None)
            report("the dark logo keeps the painting, pixel for pixel", bad is None,
                   f"rows 0-{gap - 1} match" if bad is None
                   else f"differs at {bad}; the artwork has been altered")
            lit = sum(1 for y in range(gap, h) for x in range(w)
                      if pb[x, y][3] > 0 and pb[x, y][:3] != pa[x, y][:3])
            report("the dark logo relettered the name", lit > 0, f"{lit} pixels")

    css = (SITE / "assets" / "css" / "style.css").read_text(encoding="utf-8")
    imgs = [p.relative_to(SITE).as_posix() for p in pages()
            if re.search(r"<img[^>]*logo-lockup", p.read_text(encoding="utf-8"))]
    report("no page pins the logo to one theme with an <img>", not imgs,
           f"{len(imgs)} page(s), first: {imgs[0]}" if imgs else "")

    # a page's own <style> is later in the document than the sheet holding the dark
    # rule, so declaring the image there silently defeats the swap on that page
    own = [p.relative_to(SITE).as_posix() for p in pages()
           if any("logo-lockup" in s for s in
                  re.findall(r"<style[^>]*>(.*?)</style>",
                             p.read_text(encoding="utf-8"), re.S))]
    report("no page declares the logo image in its own <style>", not own,
           f"{len(own)} page(s), first: {own[0]}" if own else "")

    m = re.search(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{(.*)", css, re.S)
    block = m.group(1) if m else ""
    report("the dark theme swaps the logo file",
           "logo-lockup-dark" in block, "" if "logo-lockup-dark" in block
           else "the dark block never names the dark asset")
    plaque = [line.strip() for line in block.splitlines()
              if re.search(r"(logo|nf-logo)\b", line)
              and re.search(r"background:\s*rgba\(2[34]", line)]
    report("the logo sits on no cream plaque in the dark",
           not plaque, plaque[0] if plaque else "")


LIVE = "https://arasteh.art"


def live() -> None:
    """Is the public site the site in this folder?

    Asked because a reviewer read arasteh.art, saw four complete editions and
    region-first browsing, and could not tell whether that was a stale crawler, a
    stale CDN, or simply a deploy that had never happened. It was the third. Rather
    than argue about caches, fetch the pages and compare them with what is here.

    Each request carries a cache-busting query and a no-store header, so what comes
    back is what GitHub Pages is serving now."""
    import urllib.error
    import urllib.request

    pages_to_check = {
        "/": SITE / "index.html",
        "/sedaha/": SITE / "sedaha" / "index.html",
        "/sedaha/languages/": SITE / "sedaha" / "languages" / "index.html",
        "/assets/css/style.css": SITE / "assets" / "css" / "style.css",
    }
    stamp = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp()))
    for path, local in pages_to_check.items():
        url = f"{LIVE}{path}?nocache={stamp}"
        try:
            req = urllib.request.Request(url, headers={
                "Cache-Control": "no-store", "Pragma": "no-cache",
                "User-Agent": "arasteh-check"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001 - the message is the finding
            report(f"live {path}", False, f"{type(exc).__name__}: {exc}")
            continue
        # byte comparison, not a keyword search: Pages serves these files verbatim,
        # so anything short of equality means the public copy is a different file.
        # Looking for a phrase instead would have passed happily on a version that
        # merely shared that phrase, which is the ambiguity this exists to remove.
        here = local.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        there = body.replace("\r\n", "\n").strip()
        if here == there:
            report(f"live {path} is byte-for-byte this file", True)
            continue
        at = next((i for i, (a, b) in enumerate(zip(here, there)) if a != b),
                  min(len(here), len(there)))
        report(f"live {path} is byte-for-byte this file", False,
               f"differs at character {at}: public has {there[at:at + 40]!r}")
    print("\n    A failure above means the public copy is not this copy: either the")
    print("    deploy has not happened, or it is still running. Nothing here is wrong.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--quick", action="store_true",
                    help="skip the per-script --check runs (the slow part)")
    ap.add_argument("--live", action="store_true",
                    help="also ask arasteh.art whether it is serving this version "
                         "(run after pushing)")
    args = ap.parse_args()

    if args.live:
        live()
        print()
        if failures:
            print(f"{len(failures)} check(s) failed:")
            for f in failures:
                print("  - " + f)
            return 1
        print("the public site matches this working tree.")
        return 0

    if args.quick:
        print("[skip]  the seven script --checks (--quick)")
    else:
        run_scripts()
    run_node()
    crawl()
    structured()
    hand_written()
    availability()
    logo()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print("  - " + f)
        return 1
    print("everything consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
