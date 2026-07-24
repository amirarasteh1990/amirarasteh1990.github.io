# -*- coding: utf-8 -*-
"""Stamp one canonical navigation shell into every user-facing page.

The site sets .nojekyll, so there are no server-side includes: the nav -- like
the footer -- is literal HTML in each page. This script owns that block and is
its single source of truth. build_read_pages.py imports appnav_html() from here,
so the 122 generated pages carry the identical shell and a regeneration cannot
silently drop it (the same arrangement sync_footers.py uses for the footer).

The block is one adaptive <nav class="appnav">: a bottom tab bar on phones and a
sticky top bar on laptops. All the phone/desktop switching lives in
assets/css/style.css; this file only owns the markup and which tab is current.
It is delimited by <!-- APPNAV:START --> / <!-- APPNAV:END --> markers -- the
same machine-managed-marker convention the read pages already use for their
opening text (<!-- SYNC:opening:XX START -->) -- and inserted right after each
page's skip-link, so the shell is the first thing after "Skip to content".

    python sync_appnav.py            rewrite every page
    python sync_appnav.py --check    report drift, change nothing; exit 1 if stale

Whenever the tab set or labels change here, rerun build_read_pages.py too so the
generated Opening pages and /sedaha/languages/ pick the change up.
"""
import argparse
import io
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent

# (key, href, label, inner SVG). Keys double as the value a page passes as the
# "current" tab. Five destinations -- the comfortable maximum for a tab bar.
TABS = [
    ("home",      "/",           "Home",
     '<path d="M3 10.6 12 3l9 7.6"/><path d="M5.5 9.5V21h13V9.5"/>'),
    ("books",     "/sedaha/",    "Books",
     '<path d="M12 6.5v14"/><path d="M12 6.5C10.4 5.2 7.8 4.5 4 4.5v14c3.8 0 '
     '6.4.7 8 2 1.6-1.3 4.2-2 8-2v-14c-3.8 0-6.4.7-8 2z"/>'),
    ("paintings", "/paintings/", "Paintings",
     '<rect x="3" y="4.5" width="18" height="15" rx="2"/>'
     '<circle cx="8.5" cy="10" r="1.5"/><path d="m21 15.5-4.5-4.5L5 19.5"/>'),
    ("guestbook", "/comments/",  "Guestbook",
     '<path d="M20.5 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 20.5 12z"/>'),
    ("support",   "/support/",   "Support",
     '<path d="M12 20.3C6.9 16.9 3.5 13.6 3.5 9.9 3.5 7.4 5.4 5.6 7.8 5.6c1.6 0 '
     '3 .8 3.8 2.1.8-1.3 2.2-2.1 3.8-2.1 2.4 0 4.3 1.8 4.3 4.3 0 3.7-3.4 7-8.5 '
     '10.4z"/>'),
]

START = "<!-- APPNAV:START (managed by sync_appnav.py — edit there, not the pages) -->"
END = "<!-- APPNAV:END -->"


def appnav_html(current: str = "") -> str:
    """The whole <nav> element, at column 0, ready to sit after the skip-link.

    current -- key of the tab that points at this page (gets aria-current);
               "" for pages outside the five sections (404, license, editions).
    """
    lis = []
    for key, href, label, svg in TABS:
        cur = ' aria-current="page"' if key == current else ""
        lis.append(
            '      <li><a href="%s"%s>'
            '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">%s</svg>'
            '<span>%s</span></a></li>' % (href, cur, svg, label)
        )
    return (
        START + "\n"
        '<nav class="appnav" aria-label="Primary">\n'
        '  <div class="appnav-inner">\n'
        '    <a class="appnav-brand" href="/">Arasteh</a>\n'
        '    <ul class="appnav-tabs">\n'
        + "\n".join(lis) + "\n"
        '    </ul>\n'
        '  </div>\n'
        '</nav>\n'
        + END
    )


# Which tab is current for a given site-relative path.
def current_for(rel: str) -> str:
    rel = rel.replace("\\", "/")
    if rel == "index.html":
        return "home"
    if rel.startswith("sedaha/"):
        return "books"          # the book page, all Opening pages, languages
    if rel.startswith("paintings/"):
        return "paintings"
    if rel.startswith("comments/"):
        return "guestbook"
    if rel.startswith("support/"):
        return "support"
    return ""                   # 404.html, license.html, editions/*


SKIP_RE = re.compile(r'(<a class="skip-link" href="#main">[^<]*</a>)')
BODY_RE = re.compile(r'(<body[^>]*>)')
# a leading newline is swallowed so repeated runs stay byte-stable
BLOCK_RE = re.compile(r'\n?' + re.escape(START) + r'.*?' + re.escape(END), re.S)


def restamp(html: str, current: str) -> str:
    """Remove any existing shell, then insert a fresh one after the skip-link
    (or, failing that, right after the opening <body> tag)."""
    html = BLOCK_RE.sub("", html)
    block = appnav_html(current)
    if SKIP_RE.search(html):
        return SKIP_RE.sub(lambda m: m.group(1) + "\n" + block, html, count=1)
    return BODY_RE.sub(lambda m: m.group(1) + "\n" + block, html, count=1)


def pages() -> list[Path]:
    return sorted(p for p in SITE.rglob("*.html") if ".git" not in p.parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="report pages whose shell is out of date, change nothing")
    args = ap.parse_args()

    stale, written, skipped = [], [], []

    for path in pages():
        rel = path.relative_to(SITE).as_posix()
        html = io.open(path, encoding="utf-8").read()
        if not (SKIP_RE.search(html) or BODY_RE.search(html)):
            skipped.append(rel + "  (no skip-link or <body>)")
            continue
        new = restamp(html, current_for(rel))
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
