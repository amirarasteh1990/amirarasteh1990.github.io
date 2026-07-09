#!/usr/bin/env python3
"""
sync_book_text.py — Pull canonical text/metadata from the BOOK repo into this site, so
the book and the site never drift. Single source of truth = the book repo.

Sources it reads from:
  * book Markdown blocks    — e.g. the Opening, from 00_source_md/00_Opening.md
  * export config metadata  — title_text / author_text in export_translation.py
                              (the same values the generated books use)

Run whenever you change any of those in the book repo:
    python sync_book_text.py            # rewrite the synced regions in the HTML
    python sync_book_text.py --check    # report drift only; change nothing; exit 1 if out of sync

Two kinds of synced regions in the HTML:
  * block  — multi-line, between  <!-- SYNC:ID START -->  /  <!-- SYNC:ID END -->   (e.g. the Opening)
  * inline — one value, between   <!--S:ID-->  ...  <!--/S-->   on one line          (e.g. title, author)
Never edit inside those markers by hand — they get overwritten on the next run.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
BOOK_VOL = SITE.parent / "1_Sedaha" / "Volume1"        # book working repo (sibling). Edit if moved.
BOOK_SRC = BOOK_VOL / "00_source_md"
EXPORT_PY = BOOK_VOL / "export_translation.py"
SOUNDS = SITE / "sedaha" / "index.html"   # book page (URL /sedaha/; title text stays "Sounds")

# Each region: file, id, mode ("block" | "inline"), src spec, optional "entities" for non-ASCII inline.
#   src = ("md", md_path, block_id, lang_tag)   |   ("cfg", language_name, field_name)
SYNC = [
    {"file": SOUNDS, "id": "title:EN", "mode": "inline", "src": ("cfg", "English", "title_text")},
    {"file": SOUNDS, "id": "author",   "mode": "inline", "src": ("cfg", "English", "author_text")},
    {"file": SOUNDS, "id": "title:FA", "mode": "inline", "src": ("cfg", "Farsi", "title_text"),
     "entities": True},
]


def _md_paragraphs(md_path: Path, block_id: str, lang_tag: str) -> list[str]:
    text = md_path.read_text(encoding="utf-8")
    m = re.search(rf"^##\s+{re.escape(block_id)}\s*$", text, re.M)
    if not m:
        raise ValueError(f"{md_path.name}: block {block_id} not found")
    rest = text[m.end():]
    nxt = re.search(r"^##\s+\S+\s*$", rest, re.M)
    block = rest[:nxt.start()] if nxt else rest
    tm = re.search(rf"^\*\*{re.escape(lang_tag)}\*\*\s*$", block, re.M)
    if not tm:
        raise ValueError(f"{md_path.name}: **{lang_tag}** not found in block {block_id}")
    after = block[tm.end():]
    nt = re.search(r"^\*\*[A-Za-z-]+\*\*\s*$", after, re.M)
    seg = after[:nt.start()] if nt else after
    seg = re.sub(r"<!--.*?-->", "", seg, flags=re.S)
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", seg) if p.strip()]
    if not paras:
        raise ValueError(f"{md_path.name}: no {lang_tag} text in block {block_id}")
    return paras


def _cfg_field(lang: str, field: str) -> str:
    text = EXPORT_PY.read_text(encoding="utf-8")
    km = re.search(rf'^\s*"{re.escape(lang)}":\s*\{{', text, re.M)
    if not km:
        raise ValueError(f"{EXPORT_PY.name}: config block for {lang} not found")
    fm = re.search(rf'"{re.escape(field)}":\s*"((?:[^"\\]|\\.)*)"', text[km.end():])
    if not fm:
        raise ValueError(f"{EXPORT_PY.name}: {field} not found for {lang}")
    return fm.group(1)


def _entities(s: str) -> str:
    return "".join(ch if ord(ch) < 128 else f"&#{ord(ch)};" for ch in s)


def _render(region: dict) -> str:
    kind = region["src"][0]
    if kind == "md":
        paras = _md_paragraphs(*region["src"][1:])
        return "\n".join(f"<p>{html.escape(p, quote=False)}</p>" for p in paras)
    if kind == "cfg":
        val = _cfg_field(*region["src"][1:])
        return _entities(val) if region.get("entities") else html.escape(val, quote=False)
    raise ValueError(f"unknown source kind: {kind}")


def sync_region(region: dict, check: bool = False, indent: str = "    ") -> bool:
    rid = region["id"]
    body = region["file"].read_text(encoding="utf-8")
    rendered = _render(region)
    if region["mode"] == "block":
        start, end = f"<!-- SYNC:{rid} START -->", f"<!-- SYNC:{rid} END -->"
        m = re.search(re.escape(start) + r"(.*?)" + re.escape(end), body, re.S)
        if not m:
            raise ValueError(f"{region['file'].name}: block markers for '{rid}' not found")
        indented = "\n".join(indent + ln for ln in rendered.splitlines())
        new = f"{start}\n{indented}\n{indent}{end}"
    else:  # inline
        open_t, close_t = f"<!--S:{rid}-->", "<!--/S-->"
        m = re.search(re.escape(open_t) + r"(.*?)" + re.escape(close_t), body, re.S)
        if not m:
            raise ValueError(f"{region['file'].name}: inline markers for '{rid}' not found")
        new = f"{open_t}{rendered}{close_t}"
    if m.group(0) == new:
        print(f"[ok]    {rid}: in sync")
        return True
    if check:
        print(f"[drift] {rid}: OUT OF SYNC")
        return False
    region["file"].write_text(body[:m.start()] + new + body[m.end():], encoding="utf-8")
    print(f"[write] {rid}: updated")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync canonical book text/metadata into the site.")
    ap.add_argument("--check", action="store_true",
                    help="Report drift only; change nothing; exit 1 if any region is out of sync.")
    args = ap.parse_args()
    for p in (BOOK_SRC, EXPORT_PY):
        if not p.exists():
            sys.exit(f"Book repo path not found: {p}\nEdit the paths at the top of this script.")
    ok = True
    for region in SYNC:
        ok &= sync_region(region, check=args.check)
    if args.check and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
