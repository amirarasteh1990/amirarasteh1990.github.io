# -*- coding: utf-8 -*-
"""Stamp one canonical footer into every hand-written page.

The site sets .nojekyll, so there are no server-side includes: every footer is
literal HTML in the page. Left to hand-editing they drift, and they had --
/comments/ was missing its Guestbook link, /support/ its Support link,
license.html and /editions/first-edition/ had no route back to the book at all,
and the contact address appeared on four pages out of twelve for no reason.

This script owns the footer for the twelve hand-written pages. The 111 generated
Opening pages and the generated /sedaha/languages/ page get the same footer by
importing footer_html() from here, so `python build_read_pages.py` cannot
silently revert them.

    python sync_footers.py           rewrite
    python sync_footers.py --check   report drift, change nothing

After changing anything here, run build_read_pages.py too so the generated
pages pick the change up.
"""
import argparse
import io
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
EMAIL = "amirarasteh1990@gmail.com"

# The canonical set, in reading order. Keys are what a page passes to `omit`
# when the link would point at the page you are already on.
LINKS = [
    ("books",     "/sedaha/",      "Books"),
    ("paintings", "/paintings/",   "Paintings"),
    ("guestbook", "/comments/",    "Guestbook"),
    ("support",   "/support/",     "Support"),
    ("license",   "/license.html", "License"),
    ("telegram",  "https://t.me/Sounds_AmirArasteh", "Telegram"),
]

LOGO = """    <a class="foot-logo" href="/" aria-label="Arasteh, home">
      <picture>
        <source srcset="/assets/img/logo-lockup-web.webp" type="image/webp">
        <img src="/assets/img/logo-lockup.png" width="380" height="676" alt="">
      </picture>
    </a>
"""


def footer_html(omit: str = "", logo: bool = True, panel: bool = False) -> str:
    """The whole <footer> element, indented to sit at column 0 of a page body.

    omit  -- key of the one link to leave out, because it points at this page
    logo  -- False only on the homepage, which the logo would link to itself
    panel -- the homepage wraps its footer in .foot-panel to sit on the hero
    """
    pad = "      " if panel else "    "
    shown = [(href, label) for key, href, label in LINKS if key != omit]

    # every link but the last is followed by a separator; the address moves to
    # its own line, which keeps six links plus an email from wrapping awkwardly
    lines = ['%s<a href="%s">%s</a>%s' % (pad, href, label,
                                          " &middot;" if i < len(shown) - 1 else "<br>")
             for i, (href, label) in enumerate(shown)]
    lines.append('%sContact: <a href="mailto:%s">%s</a>' % (pad, EMAIL, EMAIL))
    body = "\n".join(lines) + "\n"

    inner = LOGO if logo else ""
    if panel:
        inner += ('    <div class="foot-panel">\n'
                  '      &copy; 2026 Amir Arasteh &middot;\n'
                  + body + "    </div>\n")
    else:
        inner += "    &copy; 2026 Amir Arasteh &middot;\n" + body

    return ('<footer class="site-footer">\n'
            '  <div class="container">\n'
            + inner +
            '  </div>\n'
            '</footer>')


# Hand-written pages only. /sedaha/languages/ and the 111 Opening pages are
# generated -- listing them here would fight build_read_pages.py.
# /sedaha/read/ (English), /read/fa/ and /read/da/ ARE hand-written.
PAGES = [
    ("index.html",                        dict(logo=False, panel=True)),
    ("404.html",                          dict()),
    ("license.html",                      dict(omit="license")),
    ("support/index.html",                dict(omit="support")),
    ("comments/index.html",               dict(omit="guestbook")),
    ("paintings/index.html",              dict(omit="paintings")),
    # a child of the gallery: keep Paintings, it walks back up to the index
    ("paintings/sounds/index.html",       dict()),
    ("sedaha/index.html",                 dict(omit="books")),
    ("editions/first-edition/index.html", dict()),
    ("sedaha/read/index.html",            dict()),
    ("sedaha/read/fa/index.html",         dict()),
    ("sedaha/read/da/index.html",         dict()),
]

FOOTER_RE = re.compile(r'<footer class="site-footer">.*?</footer>', re.S)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report pages whose footer is out of date, change nothing")
    args = ap.parse_args()

    stale, written, missing = [], [], []

    for rel, opts in PAGES:
        path = SITE / rel
        if not path.exists():
            missing.append(rel)
            continue
        html = io.open(path, encoding="utf-8").read()
        if not FOOTER_RE.search(html):
            missing.append(rel + "  (no <footer class=\"site-footer\">)")
            continue
        want = footer_html(**opts)
        new = FOOTER_RE.sub(lambda _m: want, html, count=1)
        if new == html:
            continue
        if args.check:
            stale.append(rel)
        else:
            io.open(path, "w", encoding="utf-8", newline="").write(new)
            written.append(rel)

    for rel in missing:
        print("[warn] skipped %s" % rel)

    if args.check:
        for rel in stale:
            print("[stale] %s" % rel)
        print("[%s] %d hand-written pages, %d out of date"
              % ("drift" if stale else "ok", len(PAGES) - len(missing), len(stale)))
        return 1 if stale else 0

    for rel in written:
        print("[write] %s" % rel)
    print("[ok] %d hand-written pages, %d rewritten"
          % (len(PAGES) - len(missing), len(written)))
    if written:
        print("       now run: python build_read_pages.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
