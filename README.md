# arasteh.art

Personal portfolio site of **Amir Arasteh** — paintings and books — served via GitHub Pages.

> Working on this site? See [`WEBSITE_STATUS.md`](WEBSITE_STATUS.md) for orientation and conventions.

## Structure
- `index.html` — portfolio home (gallery of works)
- `sedaha/` — *Sounds, Book 1* section (URL `/sedaha/`): cover, description, multilingual downloads
- `assets/` — styles and **web-resolution** images

## Books are NOT in this repo
Book files (EPUB/PDF) are published as **GitHub Release** assets — a single rolling
release (tag `books`) that is overwritten on each update (`gh release upload books ... --clobber`).
The `sedaha/` page links to those assets. This keeps the repo tiny and avoids git history bloat.

## Images
Only **web-resolution** copies of paintings live here (for display). High-resolution
masters are kept in a separate private archive and are **not** committed to this repo.

## License
See [`LICENSE`](LICENSE). In short: the **book** *Sounds, Book 1* is CC BY-NC-ND 4.0
(share the complete file freely, non-commercial, no derivatives); all **paintings/artwork**
are © Amir Arasteh, All Rights Reserved.
