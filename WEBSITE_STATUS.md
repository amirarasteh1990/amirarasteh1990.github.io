# Website status & orientation — arasteh.art

> Onboarding notes for anyone (human or agent) starting work on this site.
> Last updated: 2026-08-01.
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
| `sedaha/index.html` | The book page (`/sedaha/`): **a doorway, not a catalogue.** Cover, title, one line of the book, the cycling language, one availability line, the search, two links out. ~9 KB, from 89 |
| `sedaha/languages/index.html` | **The catalogue.** Every language, its state, its files, with the project's own numbers behind a disclosure |
| `assets/js/editions.js` | Generated: the languages as data, for the finder. The doorway carries no list of its own |
| `assets/js/finder.js` | The search on `/sedaha/`, and the cycling line. Answers one / several / none in place |
| `sedaha/read/index.html` (+ `fa/`, `da/`) | In-browser samples: the book's Opening in English / Persian / Danish, each linked from that edition's "Opening" button and cross-linked (text synced) |
| `editions/first-edition/index.html` | Frozen registered first-edition (2026) archival page + ISBNs |
| `paintings/index.html`, `paintings/sounds/index.html` | Painting galleries (dialog viewer with captions, arrows, Escape, and focus restoration) |
| `comments/index.html` | Native guestbook: account-free public comment form, multilingual archive, and book-page visual language |
| `support/index.html` | Donation links |
| `license.html` | License (book = author's custom terms: free complete unchanged electronic sharing, all other rights reserved, NO CC claim per 2026-07-16 book decision; paintings = All Rights Reserved) |
| `404.html` | Branded not-found page (GitHub Pages serves it automatically) |
| `sitemap.xml`, `robots.txt` | Search-engine discoverability (update `sitemap.xml` when adding a page) |
| `assets/css/style.css` | **The only stylesheet**, shared by all pages |
| `assets/js/share.js` | Share-button behavior: native share sheet, clipboard fallback + toast (see below) |
| `assets/js/gallery.js` | Accessible painting dialog: previous/next, keyboard navigation, Escape, trigger-focus restoration, and one address per painting (`#picture-4`) |
| `assets/js/reader.js` | The reading toolbar on the 114 opening pages: type size, measure, light/dark. Remembers the choice for every edition at once |
| `assets/js/lang-alias.js` | The other names each language answers to (Farsi, Bangla, Mandarin, Filipino, Castellano, Telegu…). Both language finders consult it; add freely, no rebuild needed |
| `assets/js/guestbook.js` | One-button Worker posting, immediate confirmed-note display, safe card rendering, search, language filter, sorting, and pagination |
| `assets/data/guestbook.json` | Generated public index of published notes; contains names, notes, languages, dates, and public IDs only |
| `comments/entries/` | One public JSON file per published note, kept as the durable repository archive |
| `guestbook-worker/` | Cloudflare Worker source, contract test, Wrangler free-plan configuration, and local mock server |
| `.github/workflows/publish-guestbook.yml` | GitHub-only automation: valid new issues publish immediately, notify Amir, and remain owner-moderated |
| `sync_guestbook.py` | Pulls valid public guestbook issues into entry files and regenerates the index; the script itself never performs Git writes |
| `assets/fonts/…` | Self-hosted woff2 subsets of the book's brand faces (see Fonts below) |
| `assets/fonts/names/…` | One tiny subset per script holding only the letters the 114 language names need (`build_name_fonts.py`) |
| `assets/img/…` | Web-resolution images only (hi-res masters kept private, not in repo) |
| `sw.js` | Service worker: pages network-first, same-origin assets from cache, nothing cross-origin touched |
| `sync_book_text.py` | Pulls canonical book text into the site (see below) |
| `build_webfonts.py` | Regenerates `assets/fonts/` from the book repo's TTFs (run only when those change) |
| `check.py` | One read-only command that runs every other script's `--check` plus the cross-script checks. Run before pushing |

## Light and dark

Dark mode is authored **once**, as the `@media (prefers-color-scheme:dark)` block at the
end of `style.css`. The switch in the reading toolbar does not duplicate that palette under
an attribute; it re-points that media rule at run time (`all` to force dark, `not all` to
force light, the original query to follow the system again), from the small script
`sync_head.py` puts in every `<head>`. So there is one copy of dark mode to maintain, and
with JavaScript off the system preference still decides, exactly as before.

**The logo needs paper in dark mode.** It is a painting with the name lettered into it in
dark ink on transparency, so on a dark page the paisley survives and the wordmark vanishes.
The dark block gives `.logo-panel`, `.site-footer .foot-logo` and `.nf-logo` a warm cream
plate to sit on. The artwork is never filtered, inverted or cropped: it is given paper, which
is how it is printed in the book.

The guestbook is native HTML and uses this same stylesheet, so its writing desk, reader-note
cards, controls, and empty states follow the selected theme without a second theme system.

## One availability story (`status_rows()` is the edition record)

**Everything a visitor is told about what exists is derived from one record.** `status_rows()`
in `build_read_pages.py` joins the book repo's own lists with the assets actually on the
GitHub release, and yields per language: native and English name, direction, opening URL,
state, formats, file sizes, release date, slug, share line.

It used to feed only the status table and the hero counter, while the complete-edition cards
and the marketing copy were kept by hand. That is exactly how the **Italian edition came to
be complete, downloadable, and named nowhere a visitor would look** for six weeks. Consumers
now generated from the record:

| What | Function |
| --- | --- |
| What each Opening page offers below its text | `render(L, row)` — its own files once that edition is complete |
| The complete-edition cards on `/sedaha/` | `patch_featured` → `featured_html` (between `EDITIONS:` markers) |
| The list of every other complete edition | `patch_featured` → `more_complete_html` (between `MORE:` markers) |
| Both descriptions + the hub card on `/`, and on `/sedaha/` | `patch_availability` → `availability` |
| The hero count and the progress tally | `patch_meter`, `patch_availability` |
| State + download links on all 114 browse rows | `patch_index` (`data-state`, used by the search) |
| The status table, its filters and counts | `patch_status_page` → `render_status` |
| The Atom feed | `patch_feed` |

**Add a consumer here rather than a second list.** `check.py` verifies the cards sit inside
their grid, that every complete edition is named on the page, and that the sentence is
identical everywhere it is told.

Two conventions worth keeping: **EPUB before PDF** everywhere (`FMT_ORDER`), and the status
labels all describe the *complete edition* (`STATES`), because every one of the 114 already
has a readable Opening and "Ready to read" did not distinguish anything.

Complete editions are **counted, not listed** in prose: "23 complete editions to download,
more on the way". Naming them was right at four and wrong at twenty-three.

**Where they are shown moved on 2026-07-27.** `/sedaha/` became a doorway and shows no
edition at all: cover, title, one line of the book, the cycling language, one availability
line, the search, and two links out. Everything below that — the cards, the compact list, the
A–Z and regional browsers, the progress section, the licence summary — moved to
`/sedaha/languages/` or was dropped. The page went from 89 KB to about 9 KB, and the
governing rule for anything added back is that it must serve **find my language** or **start
reading**.

The two shapes below are gone with it, kept here only because the reasoning still applies if
a list ever returns:

- **cards** for the three the book was published in, `FEATURED_FIRST`
- **one line each** for every other complete edition, `more_complete_html`, in the compact form
  the browse list uses, each with **its own share button** (`.lnk-share`): those editions had
  one while they were cards, and moving them into a list must not take it away.
- the **search result carries a share button too**, so any of the 113, including those with no
  card and no files yet, can be passed on from the book page. Anyone after one particular
  language uses the search box above, which answers with that language's own buttons.

Two traps live here, both now guarded:

- `patch_index` rewrites any `<li>` holding a `<span class="name">` into a browse row. The
  listed editions use that same inner markup, so they carry **`class="dl-row"`** and
  `patch_index` skips them. Without that the two patchers rewrote each other on every run.
- the `MORE:` end marker is matched with `(\s*<!-- MORE:END -->)`, no required newline, so the
  region still matches when it is **empty**. Each generated block ends on a tag, never on
  whitespace, so nothing accumulates between runs.

`check.py` verifies that cards plus listed rows account for every complete edition, with none
in both places.

## `HIDDEN_SLUGS` — editions the book has and the site does not show

`{"he"}` since 2026-07-26, the author's decision: he writes from Iran and does not want the
site to become a political object. **The book is untouched** — the edition is translated, and
ships in the book repo and the releases. Only arasteh.art stays quiet about it.

One line in `build_read_pages.py` removes the generated page (and deletes it if present), the
browse row, the status row, the hreflang cluster entry, the sitemap URL and the feed entry.
The search alias and the hand-written row were removed by hand; `check.py` verifies that the
name, the native name, the URL and the hreflang tag appear on **no** page, in the sitemap, the
feed or `lang-alias.js`.

The published number stays **114, the number of languages the book has**, which is why
`main()` passes `total` separately from the rows it lists. So the site says "the opening in
114 languages" while listing 113. To keep that from reading as a puzzle, nothing invites a
count of the list: the browse summary says "Browse every language", not "all 114", and the
search status says "Showing every language". The per-region counts still sum to 113. If you
would rather the number matched the list exactly, drop the `total` argument in `main()` and
every sentence becomes 113.

One coupling to know about: the "in final review" count comes from `TIER_A` in the **book
repo's** `build.py`, read live. An uncommitted edit there changes what this site publishes.

## The language finder

One box, on `/sedaha/` and `/sedaha/languages/`. Three things make it forgiving:

- `assets/js/lang-alias.js` — the other names a language answers to. **The first name in each
  list is treated as a full name**, which is what makes "farsi" answer Persian outright rather
  than shrug at Persian and Dari together.
- accent folding, so `turkce` finds Türkçe and `espanol` finds Español. Letters that do not
  decompose (ø, æ, ß, đ, ð, þ, ł, ı, œ) are mapped by hand, in both copies.
- the language's own code, since the URLs already expose it: `ja`, `pt-br`.

**A row is searchable by its two printed names, its aliases and its code, and by nothing
else.** Built field by field, deliberately: indexing the row's whole `textContent` swept in
everything else printed there, so "pdf" matched 23 languages and "opening" matched all of
them. The same rule applies on the status page, whose rows also carry a state label.

A search answers **in place**, in all three cases: one language gets its name, its state and
its buttons; several get a count and a row of names to pick from; none gets "No language
matches X" with a way to browse and a way to write to the author. The container is a
`role="region"` with `aria-live="polite"`, so a screen reader hears the answer without
hunting for it. Before this, several matches showed nothing at all and a miss was announced
at the foot of a collapsed list.

On `/sedaha/` the finder is **data-driven** (`finder.js` reading `editions.js`), because that
page carries no languages at all. Several matches show the first five and a way to all of
them; a complete edition's answer also carries a **Download help** disclosure, which is the
only place the GitHub-hosting note appears on the normal path, and the only moment it helps.
Escape clears the field. On `/sedaha/languages/` the same rules filter the visible table.

The A–Z and by-region browser that used to live on `/sedaha/` is gone with the rest of the
catalogue; `/sedaha/languages/` is the one list now. If a browser is ever rebuilt there and
it moves rows between arrangements, leave a **comment marker** where each row belongs rather
than remembering `nextSibling`: the latter happens to work only because rows are separated by
whitespace text nodes, and breaks the day the HTML is minified.

The **shell is marked `lang="en" dir="ltr"`** — nav, footer, skip link, reading toolbar,
share buttons. It is English on all 124 pages including the 111 that are not, and saying so
lets a screen reader switch voice instead of reading English through an Italian or Japanese
one. `sync_appnav`'s skip-link pattern allows attributes for exactly this reason: anchored on
`">"`, it silently failed to find the skip link on all 111 generated pages.

**Below 640px the status table stops being a table** and each edition becomes a stacked block
with 44px tap targets, instead of three columns and sideways scrolling. File sizes are printed
beside each download rather than hidden in a `title`, because a phone has no hover and the size
is what decides whether a book is downloaded on mobile data.

## `body class="writing"` (the guestbook only)

Every other page is read; the guestbook is written on. The page also carries `body.book`, so
it has the cover painting, warm floating sheet, serif voice, inset bookplate frame, and dark
palette of `/sedaha/`. The form and cards remain native page elements with no iframe or
third-party visual layer.

- **The footer is the same as every other page's.** The shared scripts still own its markup.
- On phones the tab bar **stays at the bottom, as on every other page**, and slides below the
  viewport only while a form field is focused. `guestbook.js` adds `.is-typing` to `<body>`
  from the form's `focusin` event and removes it 180ms after `focusout`, so moving between
  fields does not make it flicker. The body keeps its padding while the bar is away.
- Form content is plain text. Cards are assembled with `textContent`, never `innerHTML`, and
  each note receives its language and writing direction before rendering.
- The writing form has no language selector. It attaches the visitor's browser language as
  archive metadata, without making language a condition for leaving a note.
- The writing surface contains only a name and a plain-text note. Notes are limited to 500
  characters so comments remain readable and the Worker can enforce a small request boundary.
- The account and privacy boundary is explicit before submission: no account is required, and
  the chosen name and comment become public. There is no private-note mode.
- **Post** sends one request to the configured Worker. The page shows a success state and inserts
  the comment only after GitHub confirms issue creation; ambiguous or failed delivery keeps the
  form available and never produces a false receipt.
- The script URL is version-pinned in both `comments/index.html` and `sw.js`. This prevents a
  returning browser from combining new form markup with an older cached submission client
  during the first navigation after a deployment.

Reuse it on any future page whose point is a form, not prose.

## Guestbook data and moderation

The repository is the public source of truth. Published notes live individually under
`comments/entries/`, while `assets/data/guestbook.json` is the compact index fetched by the
page. This avoids one ever-growing hand-edited file while still requiring one request from a
visitor. The index is network-first in `sw.js`, with the last published copy available offline.

Only public presentation fields enter the generated archive: public ID, chosen name or pen
name, plain-text note, language code and name, publication date, and optional featured state.
There is no email field. The browser contains no GitHub token and requires no visitor account.

The form sends the chosen name, plain-text comment, automatic language metadata, and an empty
bot-trap field to the Cloudflare Worker declared by the `guestbook-endpoint` meta tag. The Worker
accepts only the exact production origin, limits the request body, validates the 40-character
name and 500-character comment again, and applies a rate limit before contacting GitHub. The
rate-limit key is a salted SHA-256 digest of the source address. This code does not persist or
log the raw address, browser user agent, or any email address.

The Worker holds one encrypted Cloudflare secret: a fine-grained GitHub token restricted to
**Issues: read and write** on `amirarasteh1990.github.io`. It has no Contents, Actions,
Administration, or account-wide repository access. A second random secret salts rate-limit
keys. Neither secret is committed, placed in Wrangler variables, or returned to the browser.

A successful request creates a human-readable public issue with `guestbook`, `pending`, and
`shareable`. A small versioned marker carries the generated public ID, automatic language
metadata, and submission time; the name and comment remain human-readable in the issue. GitHub
returns the issue number and creation time, which become the authoritative public ID and date.
Submitted metadata therefore cannot replace an older note or choose its archive position.

The Worker returns that canonical entry only after GitHub confirms issue creation. The page
renders it immediately and keeps a small confirmed copy in local storage for up to 24 hours.
This prevents the submitter's note from disappearing during the normal GitHub Actions and Pages
delay. Other readers receive the repository-owned copy after the Pages build finishes. Once the
public index contains the same ID, the browser removes its temporary copy automatically.

Publishing and moderation are label-based:

1. The Worker creates a valid issue with `guestbook`, `pending`, and `shareable`; it publishes
   automatically. There is no approval wait.
2. The workflow creates any missing moderation labels, replaces the issue labels with that safe
   set, and assigns the issue to `amirarasteh1990`. Assignment creates Amir's GitHub
   notification. `pending` means unread and can be removed after reading without changing the
   public note.
3. Add `featured` to keep a note near the front. Add `rejected` to remove it. Removing
   `rejected` publishes it again.
4. `.github/workflows/publish-guestbook.yml` processes later label changes and issue edits only
   when the event actor is the repository owner. It syncs that one moderated issue, validates
   the index, and commits only
   `comments/entries/` and `assets/data/guestbook.json` as `github-actions[bot]`. A push made
   with GitHub's built-in token does not start a legacy Pages build, so the workflow explicitly
   requests one after a changed archive is pushed.

The workflow uses GitHub's short-lived repository token with `issues: write`, `contents: write`,
and `pages: write`; no personal token is stored in the repository or Actions. Concurrency is
serialized and each run checks out the latest default branch. A new-submission sync ignores
owner-only moderation labels, then the workflow replaces the issue labels with the safe unread
set. The initial workflow runs only when the issue event carries both the repository-owner
identity of the Worker's fine-grained token and the versioned guestbook marker. A visitor
cannot activate that path by opening an issue directly. Only an owner action or an owner-run
manual dispatch can feature, revise, reject, or restore one. A malformed issue fails without
publishing.

`guestbook-worker/wrangler.jsonc` is the deploy-time source of truth. It declares the production
origin, public repository, two required secrets, and a three-attempts-per-minute rate limiter.
The Worker runs on the Cloudflare Free plan at
`https://arasteh-guestbook.amir-arasteh.workers.dev/`; that exact URL is configured in
`comments/index.html`. Version preview URLs are disabled. `node guestbook-worker/test.mjs`
exercises the full intake contract without a network call or external write.

For a manual recovery sync, run `python sync_guestbook.py --repo
amirarasteh1990/amirarasteh1990.github.io --issue NUMBER`. The script writes public entry files
and the index only; it never stages, commits, pushes, labels, or closes.
`python sync_guestbook.py --check` validates the local archive without accessing GitHub. For a
safe local page preview, run `guestbook-worker/dev-server.mjs` with `MOCK_GITHUB=1`; it uses the
production handler but never contacts GitHub.

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
- tag `first-edition-1.0` — frozen registered set linked from `/editions/first-edition/`.

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
only to editions that have a real page to land on; unreleased language rows have none.
(2026-07-24: the per-row "Coming soon" labels were removed from `/sedaha/` for a cleaner list;
a row without download links is implicitly in preparation, and `/sedaha/languages/` carries the
exact status.)

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
`og:locale`, and RTL handling (ar he ur ckb ps bal glk lrc mzn prs sd ug yi). The CTA's three
buttons hand over the **complete** book (the FA/EN/DA EPUBs on the release), because the
sentence above them says the whole book is free in those three; they used to lead to another
Opening page, which read as a promise withdrawn. The script also idempotently wires an
"Opening" link into each language's row on `/sedaha/` and the URLs into `sitemap.xml`. Slugs
are the lowercased book-repo folder codes (e.g. `prs`, `ckb`, `nds`, `me`).

**The invitation below the text follows the release.** Until an edition is complete, the page
carries its whole localized sentence ("the complete German edition is on the way; until then
the book is free in Persian, English and Danish") and the three EPUBs that exist. Once that
edition **is** complete, the second half of that sentence is false, so `render()` keeps only
its **first sentence** ("Das Buch beginnt hier.") and offers **that language's own** EPUB and
PDF, labelled with the book's own title: "Klänge EPUB".

Rewriting the promise in each language would be a translation job in the book repo; taking
the author's own words that far is not. `_first_sentence()` cuts on the sentence mark of the
script in question (`.。۔।։።។`, and more), and returns nothing for Thai and Lao, which write
without sentence punctuation. A page that gets nothing shows the buttons alone, which says
the same thing with no risk. **Its minimum length is 5 characters on purpose**: a bar that
suited German threw away every CJK opening, since 本はここから始まる。 is a whole sentence in ten.

**These pages carry no visible English.** The chrome around the text used to: "← Sounds",
"Sounds · Book One", "Opening in:", "all 114 →", "Share this opening". It is gone, not
translated, because 114 translations of six strings is 684 unreviewed strings:

- the two links out of the page name the book **in its own script** (`_title()` of that
  edition), each inside its own `<span lang dir>` so an RTL title cannot drag the arrow
  across (`unicode-bidi:isolate`)
- the language strip (`op_langs_html()`) is a globe icon, the languages naming themselves,
  and `114 →`
- the share button is icon-only, like the reading toolbar
- the redundant kicker is gone (the back link already names the book)
- what English remains is invisible: `aria-label`s and the "Link copied" toast, each marked
  `lang="en"` so a screen reader switches voice instead of reading English through, say, a
  Japanese one

`check.py` compares the three hand-written EN/FA/DA pages against `op_langs_html()` and
`reader_tools_html()`, so the four cannot drift.

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
