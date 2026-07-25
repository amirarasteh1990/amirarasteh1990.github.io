#!/usr/bin/env python3
"""
build_name_fonts.py — Tiny webfonts so the 114 language names always render.

The list of languages is the site's signature, and it is written in each
language's own script. Whether a visitor sees ಕನ್ನಡ or an empty box depends
entirely on the fonts their operating system happens to ship: Windows and most
Linux desktops have gaps (Sinhala, Khmer, Odia, Lao, Myanmar and others), and a
row of tofu is the one thing this page must never show.

The names need only the handful of characters they are spelled with — three to
thirteen per script — so a subset of exactly those glyphs is a couple of
kilobytes (the complex Indic shaping tables cost more: Devanagari is the worst
at ~26 KB). `unicode-range` means each face is fetched only if a page actually
prints that script, so the reading pages pull none of them and the two language
pages pull about 90 KB in total, once, then from cache.

Where the book repo already carries the face (it prints these editions with the
same Noto Serif families), the subset is cut from that TTF, so the web page and
the printed book spell a name in the same letters. For the scripts the book repo
has no face for, the exact subset is fetched once from Google Fonts, which
serves these OFL families with a `text=` parameter and returns nothing but the
glyphs asked for. The result is self-hosted; nothing is requested at page load.

Deliberately NOT applied to the reading pages: those carry whole chapters, where
a real font would be megabytes and the reader's own system font is the right
answer. Only the names are covered.

    python build_name_fonts.py            build the subsets + stamp the CSS block
    python build_name_fonts.py --check    report drift only; change nothing; exit 1
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parent
BOOK_FONTS = SITE.parent / "1_Sedaha" / "Volume1" / "fonts"
OUT = SITE / "assets" / "fonts" / "names"
CSS = SITE / "assets" / "css" / "style.css"

START = "/* NAMEFONTS:START (managed by build_name_fonts.py — run it, do not edit this block) */"
END = "/* NAMEFONTS:END */"

# Latin, Cyrillic, Greek and Arabic are left out on purpose: they are on every
# system, and the Arabic-script names already get the book's Vazirmatn.
# script            unicode-range          book repo TTF                      Google family
SCRIPTS = [
    ("armenian",   "U+0530-058F", "NotoSerifArmenian-Regular.ttf",   "Noto Serif Armenian"),
    ("hebrew",     "U+0590-05FF", "NotoSerifHebrew[wdth,wght].ttf",  "Noto Serif Hebrew"),
    ("devanagari", "U+0900-097F", "NotoSerifDevanagari-Regular.ttf", "Noto Serif Devanagari"),
    ("bengali",    "U+0980-09FF", "NotoSerifBengali-Regular.ttf",    "Noto Serif Bengali"),
    ("gurmukhi",   "U+0A00-0A7F", "NotoSerifGurmukhi-Regular.ttf",   "Noto Serif Gurmukhi"),
    ("gujarati",   "U+0A80-0AFF", None,                              "Noto Serif Gujarati"),
    ("oriya",      "U+0B00-0B7F", None,                              "Noto Serif Oriya"),
    ("tamil",      "U+0B80-0BFF", "NotoSerifTamil-Regular.ttf",      "Noto Serif Tamil"),
    ("telugu",     "U+0C00-0C7F", "NotoSerifTelugu-Regular.ttf",     "Noto Serif Telugu"),
    ("kannada",    "U+0C80-0CFF", None,                              "Noto Serif Kannada"),
    ("malayalam",  "U+0D00-0D7F", "NotoSerifMalayalam-Regular.ttf",  "Noto Serif Malayalam"),
    ("sinhala",    "U+0D80-0DFF", None,                              "Noto Serif Sinhala"),
    ("thai",       "U+0E00-0E7F", "NotoSerifThai-Regular.ttf",       "Noto Serif Thai"),
    ("lao",        "U+0E80-0EFF", None,                              "Noto Serif Lao"),
    ("myanmar",    "U+1000-109F", None,                              "Noto Serif Myanmar"),
    ("georgian",   "U+10A0-10FF", "NotoSerifGeorgian-Regular.ttf",   "Noto Serif Georgian"),
    ("ethiopic",   "U+1200-137F", "NotoSerifEthiopic-Regular.ttf",   "Noto Serif Ethiopic"),
    ("khmer",      "U+1780-17FF", None,                              "Noto Serif Khmer"),
    ("han",        "U+3400-9FFF", "NotoSerifSC[wght].ttf",           "Noto Serif SC"),
    ("hangul",     "U+AC00-D7AF", "NotoSerifKR[wght].ttf",           "Noto Serif KR"),
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")   # asks Google Fonts for woff2


def _range(spec: str) -> range:
    lo, hi = spec.replace("U+", "").split("-")
    return range(int(lo, 16), int(hi, 16) + 1)


def native_names() -> list[str]:
    """Every language name exactly as the site prints it (one source: the generator)."""
    import build_read_pages as gen
    return [L["native"] for L in gen.LANGS] + [c["native"] for c in gen.CORE]


def wanted() -> dict[str, str]:
    """script -> the characters the names actually need, in codepoint order."""
    chars = {name: set() for name, *_ in SCRIPTS}
    ranges = {name: _range(spec) for name, spec, *_ in SCRIPTS}
    for text in native_names():
        for ch in text:
            for name, block in ranges.items():
                if ord(ch) in block:
                    chars[name].add(ch)
                    break
    return {name: "".join(sorted(found)) for name, found in chars.items() if found}


def cut_local(ttf: Path, text: str, dest: Path) -> None:
    from fontTools.subset import Options, Subsetter, load_font, save_font
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    opts = Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]      # keep shaping: Indic and Khmer are unreadable without it
    opts.notdef_outline = True
    if "[" in ttf.name:               # variable font: pin the regular weight first
        font = TTFont(str(ttf))
        instantiateVariableFont(font, {"wght": 400}, inplace=True)
    else:
        font = load_font(str(ttf), opts)
    subsetter = Subsetter(options=opts)
    subsetter.populate(text=text)
    subsetter.subset(font)
    save_font(font, str(dest), opts)


def cut_remote(family: str, text: str, dest: Path) -> None:
    """Google Fonts returns exactly the glyphs in `text`; we then self-host them."""
    css_url = ("https://fonts.googleapis.com/css2?family="
               + urllib.parse.quote(family.replace(" ", "+"), safe="+")
               + "&text=" + urllib.parse.quote(text))
    css = urllib.request.urlopen(
        urllib.request.Request(css_url, headers={"User-Agent": UA}), timeout=30).read().decode()
    match = re.search(r"src:\s*url\((https://[^)]+)\)", css)
    if not match:
        raise RuntimeError(f"no font URL in the CSS for {family}")
    data = urllib.request.urlopen(
        urllib.request.Request(match.group(1), headers={"User-Agent": UA}), timeout=60).read()
    dest.write_bytes(data)


def css_block(built: list[str]) -> str:
    ranges = {name: spec for name, spec, *_ in SCRIPTS}
    faces = "\n".join(
        f'@font-face{{font-family:"Sedaha Names";font-style:normal;font-weight:400;'
        f"font-display:swap;\n"
        f'  src:url(/assets/fonts/names/{name}.woff2) format("woff2");'
        f"unicode-range:{ranges[name]}}}"
        for name in built)
    return (f"{START}\n"
            "/* One family, one face per script, each holding only the letters the 114\n"
            "   language names are spelled with. unicode-range keeps every other page\n"
            "   from touching them, and a script whose glyph is missing here simply\n"
            "   falls through to the reader's own system font. */\n"
            f"{faces}\n{END}")


def stamp_css(block: str, check: bool) -> bool:
    body = CSS.read_text(encoding="utf-8")
    if START in body:
        new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _m: block, body, flags=re.S)
    else:  # first run: sit with the other @font-face rules, above :root
        new = body.replace("\n:root{", f"\n{block}\n\n:root{{", 1)
    if new == body:
        print("[ok]    style.css: name-font block current")
        return True
    if check:
        print("[drift] style.css: name-font block missing or stale")
        return False
    CSS.write_text(new, encoding="utf-8", newline="\n")
    print("[write] style.css: name-font block")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--check", action="store_true",
                    help="report drift only; change nothing; exit 1 if stale")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    needed = wanted()
    built, missing = [], []
    for name, _spec, local, family in SCRIPTS:
        text = needed.get(name)
        if not text:
            continue
        dest = OUT / f"{name}.woff2"
        if dest.is_file():
            built.append(name)
            continue
        if args.check:
            print(f"[drift] {dest.relative_to(SITE)} missing")
            missing.append(name)
            continue
        ttf = BOOK_FONTS / local if local else None
        try:
            try:
                if not (ttf and ttf.is_file()):
                    raise FileNotFoundError(local or name)
                cut_local(ttf, text, dest)
                where = ttf.name
            except Exception as local_exc:  # noqa: BLE001 - the family is on Google Fonts too
                if ttf and ttf.is_file():
                    print(f"[warn]  {name}: {ttf.name} would not subset "
                          f"({type(local_exc).__name__}); asking Google Fonts instead")
                cut_remote(family, text, dest)
                where = f"{family} (Google Fonts, OFL)"
            built.append(name)
            print(f"[write] names/{name}.woff2  {dest.stat().st_size / 1024:5.1f} KB  "
                  f"{len(text)} glyphs  <- {where}")
        except Exception as exc:  # noqa: BLE001 - one script failing must not stop the rest
            missing.append(name)
            print(f"[warn]  {name}: no subset built ({type(exc).__name__}: {exc})")
            print(f"[warn]  those names fall back to the reader's system font, as before")

    ok = stamp_css(css_block(built), args.check)
    print(f"{len(built)} scripts covered" + (f", {len(missing)} left to the system" if missing else ""))
    return 1 if (args.check and (missing or not ok)) else 0


if __name__ == "__main__":
    sys.exit(main())
