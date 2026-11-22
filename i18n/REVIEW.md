# Review: the website's words, second reader

A translator has written `i18n/<code>.json` from `i18n/BRIEF.md` (read it: its rules are
the rules here too). You are the independent second reader. The site is arasteh.art; the
English strings and where they sit are in `i18n/source.json`; each edition's own facts
(book title, "Book One", author name, Opening word, excerpt line, picture words,
register sample) are in `i18n/context.json`.

## What to do, per language

1. **Read every entry against the English.** Fix what is wrong, not what is merely
   different from how you would say it:
   - meaning errors, omissions, additions;
   - unnatural or machine-like phrasing a native reader would stumble on;
   - register: one form of address throughout, the one `register_sample` uses;
   - consistency: the same English word gets the same translation everywhere (thread,
     note / reader note, Opening, Picture, Paintings, Guestbook, Support, License,
     the painting viewer's controls);
   - the fixed names exactly as the brief says (author name from context, `Arasteh` and
     `Sedaha` in Latin letters, book title and "Book One" from context);
   - grammar around markers `<0>…</0>` and around `{n}` / `{q}` (any number must read
     correctly).
2. **Picture labels** ("Picture {n}", "Picture {n} · Opening", "Cover", "Back Cover",
   "End"): use the edition's own words — `picture_prefix` is the word the book prints
   before a painting's number, `picture_index_title` the heading of its list of paintings,
   `opening_word` its name for the Opening.
3. **Navigation tabs** (keys `Home`, `Books`, `Paintings`, `Guestbook`, `Support`): on a
   phone each tab holds about 11 Latin letters (about 5 Chinese/Japanese/Korean
   characters); anything longer is cut off with "…". The same key is also the footer
   link and part of page titles, so one word must serve all three. If the label is
   longer than 11, choose a shorter natural word if your language has one; otherwise keep
   it and say so. Labels measured too long at the start of this review:
   de Support "Unterstützen" · it Guestbook "Libro ospiti" · lv Guestbook "Viesu grāmata" ·
   lt Guestbook "Svečių knyga" · nl Paintings "Schilderijen".
4. **License texts** (license page, first-edition page): compare clause by clause; the
   legal meaning must be identical, nothing added or dropped.
5. **The excerpt** key ("… a thread of words that were once sounds…") must be
   `excerpt_from_opening` from context, exactly.
6. **Missing keys:** if the validator reports a key missing (new strings added after the
   translation, such as the note that the English license text is binding), translate it.

## Deliver

Edit `i18n/<code>.json` in place (UTF-8, no BOM, keep the key order) and run
`"C:\Program Files\Python311\python.exe" build_i18n.py validate <code>` from the site root
until it prints OK. The console is cp1252: never print non-ASCII to it (write any notes to
a file under `%TEMP%` if you need to look at them).

Reply with one block per language: `code: OK, N changes`, then up to 10 lines
`key → new text (why)` for the changes that matter most, then any doubt you could not
settle. Do not edit any other file; no git commands.
