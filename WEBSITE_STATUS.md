# Website status & orientation — arasteh.art

> Onboarding notes for anyone (human or agent) starting work on this site.
> Last updated: 2026-07-18.
>
> Quick command reference: [USEFUL_COMMANDS.md](USEFUL_COMMANDS.md).

**What it is:** Amir Arasteh's personal site (paintings + the book *Sounds / Sedaha*).
Static HTML/CSS/JS, with no framework or deployment build step.

## Hosting / deploy

- GitHub Pages **user site**. Repo: `github.com/amirarasteh1990/amirarasteh1990.github.io` (remote `origin`).
- Custom domain **arasteh.art** (`CNAME` file), HTTPS. `.nojekyll` present, so files are served as-is with no Jekyll.
- Deploy = commit + push to `main`.
- **Git is author-only.** Never commit, push, or stage. Leave changes in the working tree and report them.

## File map

| Path | Page |
| --- | --- |
| `index.html` | Home: visible author name, primary Books / Paintings paths, quieter Guestbook / Support / Telegram links |
| `sedaha/index.html` | The book page (`/sedaha/`): canonical cover preview, read-first hero, three complete editions, searchable openings in 114 languages |
| `sedaha/read/index.html` (+ `fa/`, `da/`) | In-browser samples: the book's Opening in English / Persian / Danish, each linked from that edition's "Opening" button and cross-linked (text synced) |
| `editions/first-edition/index.html` | Frozen registered first-edition (2026) archival page + ISBNs |
| `paintings/index.html`, `paintings/sounds/index.html` | Painting galleries (dialog viewer with captions, arrows, Escape, and focus restoration) |
| `comments/index.html` | Guestbook (Cusdis embed) |
| `support/index.html` | Donation links |
| `license.html` | License (book = author's custom terms: free complete unchanged electronic sharing, all other rights reserved, NO CC claim per 2026-07-16 book decision; paintings = All Rights Reserved) |
| `404.html` | Branded not-found page (GitHub Pages serves it automatically) |
| `sitemap.xml`, `robots.txt` | Search-engine discoverability (update `sitemap.xml` when adding a page) |
| `assets/css/style.css` | **The only stylesheet**, shared by all pages |
| `assets/js/share.js` | Share-button behavior: native share sheet, clipboard fallback + toast (see below) |
| `assets/js/gallery.js` | Accessible painting dialog: previous/next, keyboard navigation, Escape, and trigger-focus restoration |
| `assets/fonts/…` | Self-hosted woff2 subsets of the book's brand faces (see Fonts below) |
| `assets/img/…` | Web-resolution images only (hi-res masters kept private, not in repo) |
| `sync_book_text.py` | Pulls canonical book text into the site (see below) |
| `build_webfonts.py` | Regenerates `assets/fonts/` from the book repo's TTFs (run only when those change) |

## Fonts

The site uses the **book's own faces**, self-hosted as small woff2 subsets in `assets/fonts/`
(both SIL OFL): **EB Garamond** for headings and all book-text surfaces (the reader pages, the
hero excerpt), via the `--serif` CSS variable, falling back to Georgia; **Vazirmatn** for
Arabic-script content site-wide via a `:lang(fa)`/`:lang(ar)`/… rule (the Persian reader, native
names in the language list). UI chrome (buttons, cards, footer) stays the system sans stack.
Regenerate only if the book repo's TTFs change; never add a Google-Fonts/CDN `<link>`
(self-hosting keeps the site dependency-free and private). See [USEFUL_COMMANDS.md](USEFUL_COMMANDS.md).

## Painting and cover files

`sync_gallery.py` derives both gallery images and the web-sized English cover preview. Gallery
masters come from `../1_Sedaha/Volume1/CoverPics`; `assets/img/book-cover.jpg` comes from the
canonical generated `CoverPics/_generated/cover_EN.jpg`. Verify derived images after a painting
or cover rebuild; the check and rebuild commands are in [USEFUL_COMMANDS.md](USEFUL_COMMANDS.md).

### Painting files vs the book's picture numbers

The gallery images (`assets/img/paintings/sounds/`) keep the book repo's FILE names, but the
book's Picture Index numbers pictures sequentially, so the three mid-section paintings shift
everything after them. Mapping (verified against the book PDF; used in the gallery's alts +
lightbox captions): `01`=Picture 1 · Opening, `02`=Picture 2 · Book One, `03`=Picture 3,
`03_2`=**Picture 4**, `04`=Picture 5, `05`=Picture 6, `06`=Picture 7, `06_2`=**Picture 8**,
`07`=Picture 9, `08`=Picture 10, `08_2`=**Picture 11**, `09`=Picture 12 · End of Book One,
`10`=Picture 13 · Back Cover, `cover`=the cover painting.

Note: the read pages' CTA paragraph is localized per page (FA in Persian, DA in Danish); the
rest of the site chrome stays English.

## Book files are NOT in the repo

EPUB/PDF live as **GitHub Release assets**, not committed (keeps the repo small):

- tag `books` — rolling / current editions the `/sedaha/` page links to
  (same-name assets are replaced as editions are updated).
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

Never hand-edit inside `<!--S:…-->` markers; synchronization overwrites them. The check and apply
commands are in [USEFUL_COMMANDS.md](USEFUL_COMMANDS.md).

## Share buttons (`assets/js/share.js`)

Each **live** edition carries a **Share** button next to its EPUB / PDF / Opening buttons
(on `/sedaha/` and on that language's read page). It opts in with `class="btn-share"` and
`data-share-url` / `data-share-title` / `data-share-text`; the shared URL is that language's
**Opening page** (`/sedaha/read/xx/`). The script (delegated from `document`, so it covers any
page that loads it) uses the native share sheet where the browser supports it and falls back to
copy-to-clipboard with a small toast. The share payload is the **link only** (title + URL, not the
`data-share-text` line): some apps render text + URL as one block, so a pasted whole-message would
not navigate. The poetic blurb + Opening painting ride in the page's OG card instead. `data-share-text`
is kept on the buttons but unused, so the sentence can be re-enabled in one line in `share.js`.

The **preview card** a chat app shows is read from the **static `og:` tags in the `<head>` of the
shared page**, not from the button — crawlers don't run JS. Each read page already has its own
`og:title` / `og:url`, so the card differs per language automatically. To reword or localize a
card, edit that read page's head (the cover painting image is shared by all). Add a Share button
only to editions that have a real page to land on; "Coming soon" rows have none.

**Card wording (2026-07-18, author-set):** the read pages' cards are deliberately spare — one
title line, one poetic line, no "free", nothing repeated; the painting, the title, and the domain
(which is the author's name) carry the whole card. The description is the **author's own Persian
line** with EN/DA renderings of it:

| page | `og:title` | `og:description` |
| --- | --- | --- |
| `/sedaha/read/` | The opening of «Sounds» | The thread of words that were once sounds… |
| `/sedaha/read/fa/` | سرآغاز «صداها» | سررشته‌ی کلماتی که زمانی صدا بوده‌اند… |
| `/sedaha/read/da/` | Åbningen af «Lyde», på dansk | Tråden af ord, der engang var lyde… |

The FA description (سررشته = the thread's end) is the reference. Every card description ends with a single typographic ellipsis, without a preceding space, to carry the thread forward into the book. It names the very thread/yarn
painting the card shows (Picture 1, `01.jpg`). The FA title drops "in Persian" because the
Persian script announces the language itself. **Card title rule (2026-07-17, author-set): the
book title in a card is that edition's OWN translated title in «…»** (FA «صداها», EN «Sounds»,
DA «Lyde», DE «Klänge» …) — NOT the Latin "Sedaha (Sounds)". The generated pages pull the title
from the edition's `00_Title_Info.md` block 0001 automatically; on these three hand pages it is
literal. `og:site_name` was **removed from the read pages**; the "arasteh.art" line chat apps
show under a card is the platform's own domain label from the URL and cannot be removed from
our side. All three pages carry `og:locale` (`en_US` / `fa_IR` / `da_DK`). The `<title>` tag,
`meta name="description"`, and `og:image:alt` stay fuller/English on purpose (browser tab /
search snippet / screen readers, not the share card).

## Generated Opening pages (`build_read_pages.py`, 111 languages)

Beyond the hand-maintained EN/FA/DA pages, `/sedaha/read/<slug>/` exists for **all 111 other
editions** of the book repo — every language listed on `/sedaha/` now has an Opening page.
These pages are **fully generated** by `build_read_pages.py` — never edit them by hand. Each
page pulls the edition's own Opening text (block 0007) and native Opening heading (block 0006)
from the book repo (`Other_Languages/<CODE>/00_Opening.md`), plus the edition's own translated
book title (first line of `00_Title_Info.md` block 0001), which replaces the "Sedaha (Sounds)"
placeholder inside the LANGS `og_title`, wrapped «…» (or the 《…》/『…』 the ZH/JA entries carry).
From the generator's LANGS table it adds: the `og:title` sentence, a native `og:description`
(the "thread of words that were
once sounds" line in that edition's own wording), a localized CTA ("the full <language>
edition is on the way; until then the book is free in Persian, English, and Danish"),
`og:locale`, and RTL handling (ar he ur ckb ps bal glk lrc mzn prs sd ug yi). No EPUB/PDF
buttons — those editions aren't released yet; the CTA sends readers to `/sedaha/`. The script
also idempotently wires an "Opening" link into each language's row on `/sedaha/` and the URLs
into `sitemap.xml`. Slugs are the lowercased book-repo folder codes (e.g. `prs`, `ckb`, `nds`,
`me`).

Adding a language means adding one LANGS entry plus its book-repo Opening, then regenerating and
checking the pages using [USEFUL_COMMANDS.md](USEFUL_COMMANDS.md).
When an edition's EPUB/PDF is released, its page graduates: either add download buttons to
the generator template conditionally, or promote the page to hand-maintained like EN/FA/DA.

## Publishing model

- **Website changes:** after the relevant checks and diff review, the author commits and pushes
  `main`; GitHub Pages usually publishes the site within about a minute.
- **Book files:** rebuild editions in the sibling book repo (`../1_Sedaha/Volume1`), then replace
  only the reviewed assets on the rolling `books` release. Existing `/sedaha/` links need no
  website change.
- A new language row, download link, or other HTML change still requires a website deployment.

Exact check, preview, commit, deployment, and release workflows live in
[USEFUL_COMMANDS.md](USEFUL_COMMANDS.md). Public actions there are deliberately guarded.

## Conventions & do-not-touch

- **No em dashes in prose.** The author dislikes them; use periods / commas / colons instead.
  (Em dashes inside page *titles and headings* are fine.)
- Every page carries Open Graph + `twitter:card` meta for link-preview cards. Keep new pages consistent.
- Every page has a semantic `<main id="main">` landmark and a keyboard skip link. Shared text
  controls target a 44px minimum height; compact language-list links remain at least 30px high.
- The homepage keeps Books and Paintings as its only primary cards. Guestbook, Support, and
  Telegram remain secondary links so the work leads the hierarchy.
- **Book naming: Sedaha-forward.** In share text, preview cards, page titles/meta and secondary
  mentions, name the book **Sedaha (Sounds)** — or **«Sedaha»** (its own Persian quotation style)
  in the poetic share line. Keep plain **Sounds** only where it is the registered/legal title
  (the `/sedaha/` `<h1>`, which is auto-synced from the book source; the `/editions/first-edition/`
  archival page) or a fixed handle/URL (`Sounds_AmirArasteh`; the `/paintings/sounds/` path). The
  shared-opening cards use the **Opening painting** (`/assets/img/paintings/sounds/01.jpg` = the book's
  Picture 1), not the cover. **Exception (2026-07-17):** in the read pages' `og:title` share cards,
  the book is named by that edition's OWN translated title in «…», not the Latin brand (see
  "Card wording" above).
- **Never edit** `assets/img/logo-lockup.png` or the cover image. The logo is the author's full
  painting and is used whole (never cropped or redrawn).
- Announcements (new editions AND new paintings) go to the Telegram channel:
  <https://t.me/Sounds_AmirArasteh>. It is linked from the home hub-note, every page footer,
  and the book page's follow note; keep new pages' footers consistent.

## Analytics

GitHub release assets expose cumulative download counts per file; replacing a same-name asset
resets that file's count. The site has no page-view analytics, so visits to pages and in-browser
samples are not tracked. See [USEFUL_COMMANDS.md](USEFUL_COMMANDS.md) for the count commands.
