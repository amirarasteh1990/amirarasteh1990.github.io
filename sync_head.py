# -*- coding: utf-8 -*-
"""Stamp one canonical progressive-web-app head block into every page.

The site sets .nojekyll, so there are no server-side includes: the PWA tags --
like the footer and the nav shell -- must be literal HTML in each <head>. This
script owns that block and is its single source of truth. build_read_pages.py
imports head_html() from here, so the 122 generated pages carry the identical
tags and a regeneration cannot silently drop them (the same arrangement
sync_footers.py / sync_appnav.py use).

The block makes arasteh.art installable: a web-app manifest plus the iOS/Android
"standalone" hints, so a phone can Add to Home Screen and launch it full-screen,
without a browser chrome. It also carries the dark-mode theme-color, which pairs
with the light theme-color already in each page head (that one has no media query,
so it stays the default; the dark one overrides it only under a dark preference).
It is delimited by <!-- PWA:START --> / <!-- PWA:END --> markers and inserted just
before </head>. The apple-touch-icon, favicons and the light per-page theme-color
already live in each head and are left untouched.

    python sync_head.py            rewrite every page
    python sync_head.py --check    report drift, change nothing; exit 1 if stale
"""
import argparse
import io
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent

START = "<!-- PWA:START (managed by sync_head.py — edit there, not the pages) -->"
END = "<!-- PWA:END -->"


def head_html() -> str:
    """The managed head block, indented to sit at column 0 inside <head>."""
    return (
        START + "\n"
        '<link rel="manifest" href="/manifest.webmanifest">\n'
        '<meta name="mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">\n'
        '<meta name="apple-mobile-web-app-title" content="Arasteh">\n'
        '<meta name="theme-color" content="#17130f" media="(prefers-color-scheme: dark)">\n'
        + END
    )


HEAD_END_RE = re.compile(r'</head>')
BLOCK_RE = re.compile(r'\n?' + re.escape(START) + r'.*?' + re.escape(END), re.S)


def restamp(html: str) -> str:
    """Remove any existing block, then insert a fresh one right before </head>."""
    html = BLOCK_RE.sub("", html)
    block = head_html()
    return HEAD_END_RE.sub(lambda _m: block + "\n</head>", html, count=1)


def pages() -> list[Path]:
    return sorted(p for p in SITE.rglob("*.html") if ".git" not in p.parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="report pages whose PWA block is out of date, change nothing")
    args = ap.parse_args()

    stale, written, skipped = [], [], []

    for path in pages():
        rel = path.relative_to(SITE).as_posix()
        html = io.open(path, encoding="utf-8").read()
        if not HEAD_END_RE.search(html):
            skipped.append(rel + "  (no </head>)")
            continue
        new = restamp(html)
        if new == html:
            continue
        if args.check:
            stale.append(rel)
        else:
            io.open(path, "w", encoding="utf-8", newline="").write(new)
            written.append(rel)

    for rel in skipped:
        print("[warn] skipped %s" % rel)

    total = len(pages()) - len(skipped)
    if args.check:
        for rel in stale:
            print("[stale] %s" % rel)
        print("[%s] %d pages, %d out of date" %
              ("drift" if stale else "ok", total, len(stale)))
        return 1 if stale else 0

    print("[ok] %d pages, %d rewritten" % (total, len(written)))
    if written:
        print("       generated pages also carry this block via build_read_pages.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
