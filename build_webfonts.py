"""Regenerate the site's webfonts (assets/fonts/*.woff2) from the book repo's TTFs.

The site self-hosts small subsets of the book's own brand faces:
  * EB Garamond (regular / italic / semibold) — the Latin serif used on the
    cover, the logo lockup, and the printed interior.
  * Vazirmatn (regular + a true 600 weight instanced from the variable font) —
    the Persian face, applied site-wide to Arabic-script `lang` content.

Both are SIL OFL licensed, so self-hosting subsets is permitted.

Run only when the book repo's fonts change (rare). Needs the book repo checked
out as a sibling (../1_Sedaha) and its venv's fontTools + brotli:

    ..\\1_Sedaha\\Volume1\\sedaha\\Scripts\\python.exe build_webfonts.py
"""
from pathlib import Path

from fontTools.subset import Subsetter, Options, load_font, save_font
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
BOOK_FONTS = HERE.parent / "1_Sedaha" / "Volume1" / "fonts"
OUT = HERE / "assets" / "fonts"

# Latin + punctuation (covers English, Danish, the guillemets, ellipsis, dashes)
LATIN = "U+0020-017F,U+02BB-02BC,U+2010-2027,U+2030-203A,U+2044,U+20AC,U+2212"
# Arabic script + ZWNJ + basic Latin punctuation that appears inside Persian text
ARABIC = ("U+0020-007E,U+00AB,U+00BB,U+0600-06FF,U+0750-077F,U+08A0-08FF,"
          "U+200C-200F,U+2010-2027,U+FB50-FDFF,U+FE70-FEFF")


def _expand(r):
    r = r.strip().replace("U+", "")
    if "-" in r:
        a, b = r.split("-")
        return range(int(a, 16), int(b, 16) + 1)
    return [int(r, 16)]


def subset_to_woff2(src, out_name, unicodes):
    opts = Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]          # keep shaping (crucial for Arabic script)
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    font = src if isinstance(src, TTFont) else load_font(str(src), opts)
    ss = Subsetter(options=opts)
    ss.populate(unicodes=[u for r in unicodes.split(",") for u in _expand(r)])
    ss.subset(font)
    out = OUT / out_name
    save_font(font, str(out), opts)
    print(f"{out_name:28} {out.stat().st_size / 1024:7.1f} KB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subset_to_woff2(BOOK_FONTS / "EBGaramond-Regular.ttf", "ebgaramond-regular.woff2", LATIN)
    subset_to_woff2(BOOK_FONTS / "EBGaramond-Italic.ttf", "ebgaramond-italic.woff2", LATIN)
    subset_to_woff2(BOOK_FONTS / "EBGaramond-SemiBold.ttf", "ebgaramond-semibold.woff2", LATIN)
    subset_to_woff2(BOOK_FONTS / "Vazirmatn-Regular.ttf", "vazirmatn-regular.woff2", ARABIC)
    var = TTFont(str(BOOK_FONTS / "Vazirmatn-VariableFont_wght.ttf"))
    instantiateVariableFont(var, {"wght": 600}, inplace=True)
    subset_to_woff2(var, "vazirmatn-semibold.woff2", ARABIC)
    print("done ->", OUT)


if __name__ == "__main__":
    main()
