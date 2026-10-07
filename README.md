# arasteh.art

Personal portfolio site of **Amir Arasteh** — paintings and books — served via GitHub Pages.

> Working on this site? See [WEBSITE_STATUS.md](WEBSITE_STATUS.md) for orientation and conventions.
> For the command cheat sheet, see [USEFUL_COMMANDS.md](USEFUL_COMMANDS.md).

## Structure
- `index.html` — portfolio home with Books and Paintings as the primary paths
- `sedaha/` — *Sounds, Book 1*: cover, language search, a collapsed language list, and links to multilingual Openings/downloads
- `sedaha/languages/` — legacy URL redirecting to `/sedaha/#allLangs`
- `paintings/` — collection chooser and the Sedaha / Boteh-Jegheh galleries
- `comments/`, `support/` — public guestbook and support links
- `assets/` — styles and **web-resolution** images

## Books are NOT in this repo
Book files (EPUB/PDF) are published as **GitHub Release** assets — a single rolling
release (tag `books`) that is overwritten on each update (`gh release upload books ... --clobber`).
The `sedaha/` page links to those assets. This keeps the repo tiny and avoids git history bloat.

## Images
Only **web-resolution** copies of paintings live here (for display). High-resolution
masters are kept in a separate private archive and are **not** committed to this repo.

## License
See [`LICENSE`](LICENSE). In short: the **book** *Sedaha (Sounds), Book 1* may be read and
shared free of charge as the complete, unchanged file; all other rights are reserved by the
author. All **paintings/artwork** are © Amir Arasteh, All Rights Reserved.

## Language navigation

The book page's full language list is generated HTML and works without JavaScript.
Search enhances it: “View all matches” expands only matching editions.
`build_read_pages.py` owns the `LANGUAGES:` region and `assets/js/editions.js`;
both use the same edition record. Run `python check.py` after regeneration.
