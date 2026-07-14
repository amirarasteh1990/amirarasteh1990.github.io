# Website status & orientation — arasteh.art

> Onboarding notes for anyone (human or agent) starting work on this site.
> Last updated: 2026-07-12.

**What it is:** Amir Arasteh's personal site (paintings + the book *Sounds / Sedaha*).
Static HTML/CSS, no framework, no build step.

## Hosting / deploy

- GitHub Pages **user site**. Repo: `github.com/amirarasteh1990/amirarasteh1990.github.io` (remote `origin`).
- Custom domain **arasteh.art** (`CNAME` file), HTTPS. `.nojekyll` present, so files are served as-is with no Jekyll.
- Deploy = commit + push to `main`.
- **Git is author-only.** Never commit, push, or stage. Leave changes in the working tree and report them.

## File map

| Path | Page |
| --- | --- |
| `index.html` | Home, a 2×2 hub (Books / Paintings / Comments / Support) |
| `sedaha/index.html` | The book page (`/sedaha/`): hero, hook line, download list of 114 languages |
| `sedaha/read/index.html` (+ `fa/`, `da/`) | In-browser samples: the book's Opening in English / Persian / Danish, each linked from that edition's "Opening" button and cross-linked (text synced) |
| `editions/first-edition/index.html` | Frozen registered first-edition (2026) archival page + ISBNs |
| `paintings/index.html`, `paintings/sounds/index.html` | Painting galleries (CSS-only lightbox) |
| `comments/index.html` | Guestbook (Cusdis embed) |
| `support/index.html` | Donation links |
| `license.html` | License (book = CC BY-NC-ND 4.0; paintings = All Rights Reserved) |
| `404.html` | Branded not-found page (GitHub Pages serves it automatically) |
| `sitemap.xml`, `robots.txt` | Search-engine discoverability (update `sitemap.xml` when adding a page) |
| `assets/css/style.css` | **The only stylesheet**, shared by all pages |
| `assets/js/share.js` | Share-button behavior: native share sheet, clipboard fallback + toast (see below) |
| `assets/img/…` | Web-resolution images only (hi-res masters kept private, not in repo) |
| `sync_book_text.py` | Pulls canonical book text into the site (see below) |

## Book files are NOT in the repo

EPUB/PDF live as **GitHub Release assets**, not committed (keeps the repo small):

- tag `books` — rolling / current editions the `/sedaha/` page links to
  (uploaded with `gh release upload books … --clobber`).
- tag `first-edition-2026` — frozen registered set linked from `/editions/first-edition/`.

Download links in the HTML point at these tags. **Release uploads are gated on the author
reviewing the exact file set first**, so confirm assets are actually uploaded before assuming a link works.

## Book-text sync (`sync_book_text.py`)

Keeps the site in step with the book repo (sibling `../1_Sedaha/Volume1/export_translation.py`).
Synced regions now: the English title on `/sedaha/` (inline `<!--S:title:EN-->`), and the Opening
in three languages on the read pages — `/sedaha/read/` (EN), `/sedaha/read/fa/` (FA), `/sedaha/read/da/`
(DA) — block markers `<!-- SYNC:opening:XX START/END -->`, all pulled from block `0007` of
`00_source_md/00_Opening.md`. If you edit any upstream, re-run the sync. To add another language's
sample, add its `/sedaha/read/<xx>/` page with the markers and a `SYNC` entry (needs that language's
opening in `00_Opening.md`).

- `python sync_book_text.py --check` — report drift, change nothing.
- `python sync_book_text.py` — rewrite synced regions.
- Never hand-edit inside `<!--S:…-->` markers; they are overwritten on the next run.

## Share buttons (`assets/js/share.js`)

Each **live** edition carries a **Share** button next to its EPUB / PDF / Opening buttons
(on `/sedaha/` and on that language's read page). It opts in with `class="btn-share"` and
`data-share-url` / `data-share-title` / `data-share-text`; the shared URL is that language's
**Opening page** (`/sedaha/read/xx/`). The script (delegated from `document`, so it covers any
page that loads it) uses the native share sheet where the browser supports it and falls back to
copy-to-clipboard with a small toast.

The **preview card** a chat app shows is read from the **static `og:` tags in the `<head>` of the
shared page**, not from the button — crawlers don't run JS. Each read page already has its own
`og:title` / `og:url`, so the card differs per language automatically. To reword or localize a
card, edit that read page's head (the cover painting image is shared by all). Add a Share button
only to editions that have a real page to land on; "Coming soon" rows have none.

## Publishing: from edit to live

**A. Website change (HTML / CSS / anything in this repo):**

1. Edit the file(s).
2. If a synced value changed upstream, run `python sync_book_text.py`.
3. Optional sanity check: `python -m http.server 8000` and open `http://localhost:8000`.
4. Author pushes: `git add -A && git commit -m "…" && git push`.
5. Live at arasteh.art in ~1 min (GitHub Pages rebuilds automatically).

**B. Book file change (EPUB / PDF):**

1. Edit and rebuild the edition in the **book repo** (`../1_Sedaha/Volume1`, using that repo's own build tooling). The files are not built here.
2. Author, after reviewing the exact files, uploads them: `gh release upload books <files> --clobber`.
3. Done. The `/sedaha/` download links already point at the `books` tag, so the site serves the new file with **no website push needed**.
4. Exception: if you added a *new* language row or link in `sedaha/index.html`, that is a website change, so also do flow A.

## Conventions & do-not-touch

- **No em dashes in prose.** The author dislikes them; use periods / commas / colons instead.
  (Em dashes inside page *titles and headings* are fine.)
- Every page carries Open Graph + `twitter:card` meta for link-preview cards. Keep new pages consistent.
- **Never edit** `assets/img/logo-lockup.png` or the cover image. The logo is the author's full
  painting and is used whole (never cropped or redrawn).
- New-edition announcements go to the Telegram channel: <https://t.me/Sounds_AmirArasteh>.

## Common commands

Run from the repo root (`c:\code\Others\1_Personal\amirarasteh.github.io`).

**Preview locally** (it's static, no build):

```bash
python -m http.server 8000        # then open http://localhost:8000
```

**Sync book text** from the book repo:

```bash
python sync_book_text.py --check  # report drift only, change nothing
python sync_book_text.py          # apply the sync
```

**Inspect changes:**

```bash
git status
git diff
```

**Commit & deploy — AUTHOR ONLY.** Pushing to `main` publishes the live site
(GitHub Pages rebuilds in ~1 min). An agent must never run these; leave changes in the
working tree and let the author push.

```bash
git add -A
git commit -m "message"
git push                          # deploys to arasteh.art
```

**Publish book files (GitHub Releases) — AUTHOR ONLY, and only after reviewing the exact file set.**

```bash
# replace/add a current edition on the rolling 'books' tag
gh release upload books Sedaha_English.pdf Sedaha_English.epub --clobber

# create a tag the first time, if it doesn't exist yet
gh release create books --title "Sounds — current editions" --notes "…"
gh release create first-edition-2026 --title "Sounds — first edition (2026)" --notes "…"

# list what a release currently holds
gh release view books
```

**Download counts** (the only built-in analytics, per file, no dashboard):

```bash
# one line per file: count <tab> filename
gh api repos/amirarasteh1990/amirarasteh1990.github.io/releases/tags/books \
  --jq '.assets[] | "\(.download_count)\t\(.name)"'

# same, sorted most-downloaded first
gh api repos/amirarasteh1990/amirarasteh1990.github.io/releases/tags/books \
  --jq '.assets[] | "\(.download_count)\t\(.name)"' | sort -rn
```

Swap `books` for `first-edition-2026` to count the frozen registered set instead.

Notes:

- Counts **release-asset downloads only** — people who clicked an EPUB/PDF link. It is
  cumulative and tied to each asset, so replacing a file with `--clobber` resets that
  file's counter to zero.
- **Page views are not tracked.** GitHub Pages gives no visitor analytics, so views of
  arasteh.art itself — home, the book page, the in-browser read/Opening samples,
  paintings — are invisible. Measuring those would need an added analytics snippet
  (none is on the site today).
