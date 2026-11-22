# -*- coding: utf-8 -*-
"""The languages the site's own words come in (author 2026-11-22).

One table, read by sync_head.py (the head bootstrap that picks the visitor's
language), sync_appnav.py (the language switch in the nav) and build_i18n.py (the
dictionaries). The first round is English plus the 24 registered editions (ISBN
wave 1); a language joins by adding a row here and a dictionary in i18n/.

Each row: (code, native name, direction). The code is the site's edition slug, the
name of the dictionary file (i18n/<code>.json -> assets/i18n/<code>.js) and the
value stored in localStorage["arasteh-ui"]. Order is the order of the switch:
English, Persian and Danish first (the same three that lead every Opening's
language line), then the rest by their own names.
"""

UI_LANGS = [
    ("en", "English", "ltr"),
    ("fa", "فارسی", "rtl"),
    ("da", "Dansk", "ltr"),
    ("de", "Deutsch", "ltr"),
    ("es", "Español", "ltr"),
    ("fr", "Français", "ltr"),
    ("it", "Italiano", "ltr"),
    ("lv", "Latviešu", "ltr"),
    ("lt", "Lietuvių", "ltr"),
    ("nl", "Nederlands", "ltr"),
    ("no", "Norsk", "ltr"),
    ("pl", "Polski", "ltr"),
    ("pt", "Português", "ltr"),
    ("pt-br", "Português (Brasil)", "ltr"),
    ("sk", "Slovenčina", "ltr"),
    ("sv", "Svenska", "ltr"),
    ("tr", "Türkçe", "ltr"),
    ("ru", "Русский", "ltr"),
    ("uk", "Українська", "ltr"),
    ("hy", "Հայերեն", "ltr"),
    ("ar", "العربية", "rtl"),
    ("zh", "中文", "ltr"),
    ("ja", "日本語", "ltr"),
    ("ko", "한국어", "ltr"),
]

CODES = [c for c, _n, _d in UI_LANGS]
NATIVE = {c: n for c, n, _d in UI_LANGS}
RTL = {c for c, _n, d in UI_LANGS if d == "rtl"}


def short(code: str) -> str:
    """The few letters the phone tab shows under the globe."""
    return code.upper()
