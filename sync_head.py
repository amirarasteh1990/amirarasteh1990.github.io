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
without a browser chrome. It also registers /sw.js, which keeps a visited opening
readable when the connection goes, and points at the Atom feed of new editions
(/feed.xml, written by build_read_pages.py). It also carries the dark-mode theme-color, which pairs
with the light theme-color already in each page head (that one has no media query,
so it stays the default; the dark one overrides it only under a dark preference).
It carries two more things that must be in every head: a preload for the one
webfont used above the fold, and the theme switch (see THEME_JS below), which has
to run after the stylesheet and before first paint or a stored choice flashes.

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
IGNORED_DIRS = {".git", ".wrangler", "node_modules"}

START = "<!-- PWA:START (managed by sync_head.py — edit there, not the pages) -->"
END = "<!-- PWA:END -->"


# Light/dark is authored once, as a (prefers-color-scheme:dark) block in
# style.css. Duplicating that whole palette under a [data-theme] attribute just
# to make it switchable would mean two copies of dark mode drifting apart, so
# the switch re-points the stylesheet's own media rule instead: "all" to force
# dark, "not all" to force light, the original query to follow the system again.
# One authored copy; with JavaScript off, the system preference decides, exactly
# as it did before. The control lives in the reading toolbar (assets/js/reader.js);
# this runs in <head>, after the stylesheet, so a stored choice never flashes.
THEME_JS = (
    '<script>/* theme switch: see sync_head.py. Repoints the stylesheet\'s own '
    'dark-mode media rule; with JS off the system preference decides, as before. */\n'
    '(function(){var K="arasteh-theme",R=[],M,B,i,j,r;\n'
    'for(i=0;i<document.styleSheets.length;i++){try{r=document.styleSheets[i].cssRules}'
    'catch(e){continue}for(j=0;j<r.length;j++){if(r[j].media&&'
    '/prefers-color-scheme[^)]*dark/.test(r[j].media.mediaText))R.push(r[j].media)}}\n'
    'M=document.querySelector(\'meta[name="theme-color"]:not([media])\');B=M?M.content:"";\n'
    'function get(){try{return localStorage.getItem(K)||"auto"}catch(e){return"auto"}}\n'
    'function apply(t){var q=t=="dark"?"all":t=="light"?"not all":"(prefers-color-scheme:dark)";\n'
    'for(var i=0;i<R.length;i++){try{R[i].mediaText=q}catch(e){}}\n'
    'if(M)M.content=t=="dark"?"#17130f":t=="light"?"#F5EFE3":B;\n'
    'var d=document.documentElement;d.setAttribute("data-theme",t);'
    'd.style.colorScheme=t=="auto"?"":t}\n'
    'window.__theme={get:get,usable:R.length>0,'
    'set:function(t){try{localStorage.setItem(K,t)}catch(e){}apply(t)}};\n'
    'apply(get())})();</script>\n'
)


def head_html() -> str:
    """The managed head block, indented to sit at column 0 inside <head>."""
    return (
        START + "\n"
        # the one face used above the fold on every page (headings, reading text)
        '<link rel="preload" href="/assets/fonts/ebgaramond-regular.woff2" as="font" '
        'type="font/woff2" crossorigin>\n'
        + THEME_JS +
        '<link rel="manifest" href="/manifest.webmanifest">\n'
        '<meta name="mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">\n'
        '<meta name="apple-mobile-web-app-title" content="Arasteh">\n'
        '<meta name="theme-color" content="#17130f" media="(prefers-color-scheme: dark)">\n'
        '<link rel="alternate" type="application/atom+xml" '
        'title="Sedaha (Sounds) — new editions" href="/feed.xml">\n'
        '<script>if("serviceWorker" in navigator)addEventListener("load",function(){'
        'navigator.serviceWorker.register("/sw.js").catch(function(){})});</script>\n'
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
    return sorted(
        p for p in SITE.rglob("*.html")
        if not IGNORED_DIRS.intersection(p.relative_to(SITE).parts)
    )


# The retired /sedaha/languages/ is a redirect stub: no nav, no head block,
# nothing to keep in step. Stamping a shell into a signpost would only make it
# heavier than the page it points at.
_pages = pages
def pages():
    return [p for p in _pages()
            if p.relative_to(SITE).as_posix() != "sedaha/languages/index.html"]

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
