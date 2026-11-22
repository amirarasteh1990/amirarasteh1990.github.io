# -*- coding: utf-8 -*-
"""The site's own words in other languages (author 2026-11-22): list, check, publish.

    python build_i18n.py extract     list every site string -> i18n/source.json
    python build_i18n.py build       check i18n/<code>.json, write assets/i18n/<code>.js
    python build_i18n.py check       report problems, change nothing (check.py runs it)

How it fits together (assets/js/i18n.js has the runtime side):

  extract  serves the site locally and opens every page in headless Chrome with
           ?ui=x-extract. In that mode i18n.js walks the page exactly as it does when
           translating and, instead of translating, prints every msgid it would have
           looked up. So the list is what the runtime will ask for, by construction:
           the same segmenting, the same whitespace rule, the same <0>…</0> markers
           and {n} numbers. Strings that only appear on interaction (the finder's
           results, the guestbook's status lines) are added from EXTRA below. A string
           that appears on only a few Opening pages is a per-language variant (an
           aria-label naming that page's language) and is left in English.
  build    checks each dictionary against source.json -- every msgid present, the
           same markers properly nested, the same {n} and {slots} -- and writes
           assets/i18n/<code>.js. Then run sync_head.py, so every page asks for the
           new files (the version in their URL is a hash of them).

Console output is ASCII only (cp1252 console).
"""
import argparse
import concurrent.futures as cf
import hashlib
import html
import http.server
import io
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

SITE = Path(__file__).resolve().parent
I18N = SITE / "i18n"
OUT = SITE / "assets" / "i18n"
SOURCE = I18N / "source.json"
sys.path.insert(0, str(SITE))
from i18n_langs import CODES  # noqa: E402
from sync_appnav import SHELL  # noqa: E402

IGNORED_DIRS = {".git", ".wrangler", "node_modules", "guestbook-worker"}
SKIP_PAGES = {"sedaha/languages/index.html"}     # a redirect stub
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]

# Strings a script writes only on interaction, so a page load never shows them.
# (file, msgid). Templates use {name} slots (finder.js passes them through __t);
# plain strings are matched where they land, numbers as {n}.
EXTRA = [
    ("finder.js", "The whole book is free to read."),
    ("finder.js", "The opening is here; the whole book is in final review."),
    ("finder.js", "The opening is here; the whole book is in preparation."),
    ("finder.js", "The opening is here; the whole book is being revised."),
    ("finder.js", "Read the opening"),
    ("finder.js", "View all matches"),
    ("finder.js", "Browse all languages"),
    ("finder.js", "Write to Amir"),
    ("finder.js", "Download help"),
    ("finder.js", "Until it is ready, the whole book can be read in <0>{n} other languages</0>, among them"),
    ("finder.js", "The complete file may be shared freely, unchanged. Short excerpts may be quoted "
                  "if each names its source: the book\u2019s title, the author\u2019s name and "
                  "arasteh.art. <0>License</0>"),
    ("finder.js", "EPUB adjusts to your screen. PDF keeps the printed page. The files are hosted on "
                  "GitHub, so the download opens there. If that is blocked on your network, "
                  "<0>write to Amir</0> and he will send them to you."),
    ("finder.js", "{n} languages match"),
    ("finder.js", "{n} languages match \u201c{q}\u201d"),
    ("finder.js", "No language matches"),
    ("finder.js", "No language matches \u201c{q}\u201d."),
    ("guestbook.js", "Posting was confirmed without a readable note."),
    ("guestbook.js", "The note box is not connected yet."),
    ("guestbook.js", "The note could not be posted."),
    ("guestbook.js", "Add your name and your note before posting."),
    ("guestbook.js", "Posting\u2026"),
    ("guestbook.js", "Posting your note\u2026"),
    ("guestbook.js", "The note could not be posted just now."),
    ("guestbook.js", "Posted. Amir has been notified."),
    ("guestbook.js", "Posting took too long. Please try again."),
    ("guestbook.js", "The guestbook could not be reached. Your note is still here; please try again."),
    ("guestbook.js", "Post"),
    ("guestbook.js", "Publishing"),
    ("guestbook.js", "All languages"),
    ("guestbook.js", "Multilingual"),
    ("guestbook.js", "Other"),
    ("guestbook.js", "One reader note"),
    ("guestbook.js", "{n} reader notes"),
    ("guestbook.js", "The reader notes could not be opened."),
    ("guestbook.js", "The reader notes could not be opened just now. Please try again later."),
    ("share.js", "Link copied"),
    ("share.js", "Copy this link:"),
    ("reader.js", "Colours: light. Switch to dark."),
    ("reader.js", "Colours: dark. Switch to light."),
    ("reader.js", "Colours: light. Switch to dark. (Following the system.)"),
    ("reader.js", "Colours: dark. Switch to light. (Following the system.)"),
    ("lang-mine.js", "Hide this suggestion"),
    ("backtotop.js", "Back to top"),
    ("i18n.js", "Language"),
]

# Never a site word: as a label it is a language's own name (i18n.js agrees).
EXCLUDE = {"English"}
# An address is not a word either (the contact e-mail, arasteh.art).
ADDRESS = re.compile(r"^[^\s<>]*[@.][^\s<>]*$")

# The Persian shell (sync_appnav.SHELL, reader.js, share.js) maps back to English,
# so a visitor in another language gets their own words on the Persian pages too.
def alias_fa() -> dict:
    w = SHELL["fa"]
    a = {w["tabs"][k]: v for k, v in
         {"home": "Home", "books": "Books", "paintings": "Paintings",
          "guestbook": "Guestbook", "support": "Support"}.items()}
    a.update({
        w["nav"]: "Primary",
        html.unescape(w["copyright"]): "\u00a9 2026 Amir Arasteh",
        w["license"]: "License",
        w["telegram"]: "Telegram",
        w["contact"]: "Contact:",
        w["logo"]: "Arasteh, home",
        w["skip"]: "Skip to content",
        "\u0631\u0646\u06af\u200c\u0647\u0627: \u0631\u0648\u0634\u0646. \u062a\u063a\u06cc\u06cc\u0631 \u0628\u0647 \u062a\u06cc\u0631\u0647.":
            "Colours: light. Switch to dark.",
        "\u0631\u0646\u06af\u200c\u0647\u0627: \u062a\u06cc\u0631\u0647. \u062a\u063a\u06cc\u06cc\u0631 \u0628\u0647 \u0631\u0648\u0634\u0646.":
            "Colours: dark. Switch to light.",
        "\u0631\u0646\u06af\u200c\u0647\u0627: \u0631\u0648\u0634\u0646. \u062a\u063a\u06cc\u06cc\u0631 \u0628\u0647 \u062a\u06cc\u0631\u0647. (\u0645\u0637\u0627\u0628\u0642 \u062f\u0633\u062a\u06af\u0627\u0647)":
            "Colours: light. Switch to dark. (Following the system.)",
        "\u0631\u0646\u06af\u200c\u0647\u0627: \u062a\u06cc\u0631\u0647. \u062a\u063a\u06cc\u06cc\u0631 \u0628\u0647 \u0631\u0648\u0634\u0646. (\u0645\u0637\u0627\u0628\u0642 \u062f\u0633\u062a\u06af\u0627\u0647)":
            "Colours: dark. Switch to light. (Following the system.)",
        "\u067e\u06cc\u0648\u0646\u062f \u06a9\u067e\u06cc \u0634\u062f": "Link copied",
        "\u0627\u06cc\u0646 \u067e\u06cc\u0648\u0646\u062f \u0631\u0627 \u06a9\u067e\u06cc \u06a9\u0646\u06cc\u062f:": "Copy this link:",
    })
    return a


def pages() -> list:
    out = []
    for p in sorted(SITE.rglob("*.html")):
        rel = p.relative_to(SITE).as_posix()
        if IGNORED_DIRS.intersection(p.relative_to(SITE).parts) or rel in SKIP_PAGES                 or p.name.startswith("__"):          # local test pages, never published
            continue
        out.append(rel)
    return out


def url_of(rel: str) -> str:
    return "/" + (rel[:-len("index.html")] if rel.endswith("index.html") else rel)


def page_hashes() -> dict:
    return {rel: hashlib.sha1((SITE / rel).read_bytes()).hexdigest()[:12] for rel in pages()}


# ---------------------------------------------------------------- extract
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _serve():
    handler = lambda *a, **k: _Quiet(*a, directory=str(SITE), **k)  # noqa: E731
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    srv.handle_error = lambda *a: None      # Chrome drops connections it no longer needs
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _chrome() -> str:
    for c in CHROME:
        if os.path.exists(c):
            return c
    sys.exit("no Chrome/Edge found")


PRE_RE = re.compile(r'<pre id="i18n-extract" hidden="">(.*?)</pre>', re.S)


def _dump(chrome: str, url: str) -> dict:
    prof = tempfile.mkdtemp(prefix="i18nx-")
    try:
        r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--user-data-dir=" + prof, "--virtual-time-budget=6000",
                            "--dump-dom", url], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        m = PRE_RE.search(dom)
        return json.loads(html.unescape(m.group(1))) if m else None
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def extract(only=None) -> int:
    chrome = _chrome()
    srv = _serve()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    todo = only or pages()
    found, failed = {}, []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_dump, chrome, base + url_of(rel) + "?ui=x-extract"): rel for rel in todo}
        for f in cf.as_completed(futs):
            rel = futs[f]
            try:
                got = f.result()
            except Exception as e:  # noqa: BLE001
                got = None
            if got is None:
                failed.append(rel)
            else:
                found[rel] = got
    for rel in list(failed):          # a first Chrome launch can be slow: one more try
        got = _dump(chrome, base + url_of(rel) + "?ui=x-extract")
        if got is not None:
            found[rel] = got
            failed.remove(rel)
    srv.shutdown()
    # the Opening pages and the native-check pages are one template each, so a string
    # on only a few of them is a variant naming that page's language (an aria-label,
    # a check page's title) and stays in English
    TEMPLATED = ("sedaha/read/", "sedaha/check/")
    reads = [r for r in found if r.startswith("sedaha/read/")]
    seen_on = {}
    for rel in sorted(found):
        for k, where in found[rel].items():
            seen_on.setdefault(k, {"where": where, "pages": []})["pages"].append(rel)
    src = {}
    for k, v in seen_on.items():
        if k in EXCLUDE or ADDRESS.match(k):
            continue
        others = [p for p in v["pages"] if not p.startswith(TEMPLATED)]
        if not others and len(v["pages"]) < max(10, len(reads) // 2):
            continue          # a per-language variant on a few Opening pages
        src[k] = {"where": v["where"], "pages": len(v["pages"]),
                  "example": (others or v["pages"])[0]}
    for f, k in EXTRA:
        src.setdefault(k, {"where": "js:" + f, "pages": 0, "example": ""})
    I18N.mkdir(exist_ok=True)
    SOURCE.write_text(json.dumps({"strings": src, "pages": page_hashes()},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print("pages read: %d  failed: %d  strings: %d  (%d words)"
          % (len(found), len(failed), len(src), sum(len(k.split()) for k in src)))
    for rel in failed[:20]:
        print("  FAILED " + rel)
    return 1 if failed else 0


# ---------------------------------------------------------------- check / build
MARK = re.compile(r"<(/?)(\d+)(/?)>")
SLOT = re.compile(r"\{(\w+)\}")


def _shape(s: str):
    """The markers (as a nesting-checked sequence) and slots a string carries."""
    stack, marks = [], []
    for m in MARK.finditer(s):
        n = int(m.group(2))
        if m.group(1):
            if not stack or stack[-1] != n:
                return None
            stack.pop()
        elif m.group(3):
            marks.append(("void", n))
        else:
            stack.append(n)
            marks.append(("open", n))
    if stack:
        return None
    return sorted(marks), sorted(SLOT.findall(s))


def problems(code: str, src: dict, tr: dict) -> list:
    out = []
    for k in src:
        v = tr.get(k)
        if not isinstance(v, str) or not v.strip():
            out.append("missing: " + k[:70])
            continue
        a, b = _shape(k), _shape(v)
        if b is None:
            out.append("broken markers: " + k[:70])
        elif a != b:
            out.append("markers/slots differ: " + k[:70])
    return out


def load_source() -> dict:
    if not SOURCE.exists():
        sys.exit("i18n/source.json is missing: run  python build_i18n.py extract")
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def validate(codes) -> int:
    """One translator's check: is i18n/<code>.json complete and well-formed?"""
    src = load_source()["strings"]
    bad = 0
    for code in codes:
        p = I18N / (code + ".json")
        try:
            tr = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print("%-6s cannot read %s: %s" % (code, p.name, str(e)[:80]))
            bad += 1
            continue
        probs = problems(code, src, tr)
        extra = [k for k in tr if k not in src]
        for x in probs + ["extra key: " + k[:70] for k in extra]:
            print("%-6s %s" % (code, x.encode("ascii", "replace").decode()))
        print("%-6s %s (%d strings)" % (code, "OK" if not probs and not extra else "%d problem(s)" % (len(probs) + len(extra)), len(src)))
        bad += bool(probs or extra)
    return 1 if bad else 0


def build(check_only: bool = False) -> int:
    data = load_source()
    src = data["strings"]
    alias = alias_fa()
    bad = 0
    stale = [rel for rel, h in page_hashes().items() if data["pages"].get(rel) != h]
    for code in CODES:
        if code == "en":
            payload = {}
        else:
            p = I18N / (code + ".json")
            if not p.exists():
                print("%-6s no dictionary yet" % code)
                bad += 1
                continue
            tr = json.loads(p.read_text(encoding="utf-8"))
            probs = problems(code, src, tr)
            if probs:
                bad += 1
                print("%-6s %d problem(s)" % (code, len(probs)))
                for x in probs[:8]:
                    print("        " + x.encode("ascii", "replace").decode())
                continue
            payload = {k: tr[k] for k in src}
        js = ("/* generated by build_i18n.py from i18n/%s.json -- edit that file */\n"
              "window.__I18N=%s;\nwindow.__I18N_ALIAS=%s;\n"
              % (code + ".json" if code != "en" else "source.json",
                 json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                 json.dumps(alias, ensure_ascii=False, separators=(",", ":"))))
        target = OUT / (code + ".js")
        if check_only:
            if not target.exists() or target.read_text(encoding="utf-8") != js:
                print("%-6s assets/i18n/%s.js is out of date: run build_i18n.py build" % (code, code))
                bad += 1
            continue
        OUT.mkdir(parents=True, exist_ok=True)
        target.write_text(js, encoding="utf-8", newline="\n")
    if stale:
        print("note: %d page(s) changed since the last extract (e.g. %s); run extract if their "
              "words changed" % (len(stale), stale[0]))
    print(("check" if check_only else "build") + (": OK" if not bad else ": %d language(s) need work" % bad))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["extract", "build", "check", "validate"])
    ap.add_argument("pages", nargs="*", help="extract: only these pages; validate: language codes")
    a = ap.parse_args()
    if a.cmd == "extract":
        return extract(a.pages or None)
    if a.cmd == "validate":
        return validate(a.pages)
    return build(check_only=(a.cmd == "check"))


if __name__ == "__main__":
    sys.exit(main())
