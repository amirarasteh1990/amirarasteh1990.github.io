# Website status & orientation — arasteh.art

> Onboarding notes for anyone (human or agent) starting work on this site.
> Last updated: 2026-10-07.
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
| `sedaha/index.html` | Book doorway: cover, excerpt, availability, nine quick language links, search, and a collapsed generated language list that works without JavaScript |
| `sedaha/languages/index.html` | Retired catalogue URL; redirects to `/sedaha/#allLangs` |
| `assets/js/editions.js` | Generated search data from the same edition record as the HTML language list |
| `assets/js/finder.js` | The search on `/sedaha/`, and the cycling line. Answers one / several / none in place |
| `sedaha/read/index.html` (+ `fa/`, `da/`) | In-browser samples: the book's Opening in English / Persian / Danish, each linked from that edition's "Opening" button and cross-linked (text synced) |
| `editions/first-edition/index.html` | Frozen registered first-edition (2026) archival page + ISBNs |
| `paintings/index.html` | Collection chooser: Sedaha, The World Through Boteh-Jegheh, and the forthcoming A Yarn-Laden Truck |
| `paintings/sounds/index.html`, `paintings/boteh-jegheh/index.html` | Galleries with captioned dialogs, previous/next controls, keyboard navigation, and stable painting fragments |
| `comments/index.html` | Native guestbook: account-free public comment form, multilingual archive, and book-page visual language |
| `support/index.html` | Donation links |
| `license.html` | License (book = author's custom terms: free complete unchanged electronic sharing, all other rights reserved, NO CC claim per 2026-07-16 book decision; paintings = All Rights Reserved) |
| `404.html` | Branded not-found page (GitHub Pages serves it automatically) |
| `sitemap.xml`, `robots.txt` | Search-engine discoverability (update `sitemap.xml` when adding a page) |
| `assets/css/style.css` | **The shared stylesheet**; Support also has a small page-specific style block |
| `assets/js/share.js` | Share-button behavior: native share sheet, clipboard fallback + toast (see below) |
| `assets/js/gallery.js` | Accessible painting dialog: previous/next, keyboard navigation, Escape, trigger-focus restoration, and one address per painting (`#picture-4`) |
| `assets/js/reader.js` | The reading toolbar on the 112 public opening pages: type size, measure, light/dark. Remembers the choice for every edition at once |
| `assets/js/lang-alias.js` | The other names each language answers to (Farsi, Bangla, Mandarin, Filipino, Castellano, Telegu…). The book-page finder consults it; no page regeneration needed |
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

**The dark logo has its own lettering.** `sync_gallery.py` derives
`logo-lockup-dark.png` with lighter lettering while preserving the painting pixels.
CSS backgrounds select the light or dark variant for `.brand-logo`, `.foot-logo`, and
`.nf-logo`, including a manually selected theme. `check.py` verifies that the painting
is unchanged; do not redraw, filter, or crop the original logo.

The guestbook is native HTML and uses this same stylesheet, so its writing desk, reader-note
cards, controls, and empty states follow the selected theme without a second theme system.

## One availability story (`status_rows()` is the edition record)

**Everything a visitor is told about what exists is derived from one record.** `status_rows()`
in `build_read_pages.py` joins the book repo's own lists with the assets actually on the
GitHub release, and yields per language: native and English name, direction, opening URL,
state, formats, file sizes, release date, slug, share line.

Current consumers:

| What | Function |
| --- | --- |
| Opening-page downloads and top action bar | `render(L, row, n_complete)` |
| Search data | `patch_editions_js` → `editions_js` |
| Nine quick language links | `patch_quick_starts` → `quick_starts_html` |
| Collapsed HTML language list | `patch_all_languages` → `all_languages_html`, between `LANGUAGES:` markers |
| Homepage/book metadata and the book's availability line | `patch_availability`, `patch_meter` |
| File sizes on the three hand-maintained Opening pages | `patch_hand_sizes` |
| Atom feed | `patch_feed` |

**Add consumers to this record instead of maintaining another edition list.** The old
featured-card, regional-browser, and status-table layouts are no longer published.
`patch_status_page` now maintains only the redirect to `/sedaha/#allLangs`.

Keep **EPUB before PDF** (`FMT_ORDER`). Edition states describe the complete book;
each displayed language already has an Opening. Counts are generated, never maintained
in prose. `check.py` compares both the search data and static catalogue with the visible
edition record and checks availability copy for consistency.

The book page still serves **find my language** and **start reading**. Its full list
is in a native `<details>` element, so it adds no visible catalogue until requested.
Generate it with `build_read_pages.py`; never hand-edit the `LANGUAGES:` region.

If the release lookup fails, the existing generator warns and falls back to local book
builds. Those files are not proof of publication. Verify the release before deploying
regenerated availability data produced with that warning.

## `HIDDEN_SLUGS` — editions the book has and the site does not show

`HIDDEN_SLUGS` currently contains `{"he", "sr"}`. The Hebrew exclusion dates from
2026-07-26, the author's decision: he writes from Iran and does not want the
site to become a political object. **The book is untouched** — the edition is translated, and
ships in the book repo and the releases. Only arasteh.art stays quiet about it.

Serbian was hidden on 2026-08-05 during publisher review. Preserve that exclusion
until the author changes it; the website switch does not remove GitHub release assets.

`shown(rows)` filters the public search data, quick links, static catalogue, and feed.
The generator also excludes the Opening page, hreflang entry, and sitemap URL.
`check.py` verifies the edition's name, native name, URL, and hreflang tag do not appear
on public pages, in the sitemap/feed, or in `lang-alias.js`.

The published total remains **114, the number of languages the book has**; the site
lists 112. Preserve this author decision. The disclosure says "Browse all languages"
and groups the visible editions by complete book versus Opening only.

One coupling to know about: the "in final review" count comes from `TIER_A` in the **book
repo's** `build.py`, read live. An uncommitted edit there changes what this site publishes.

## The language finder

There is one search box, on `/sedaha/`. Search indexes only native/English names,
aliases from `assets/js/lang-alias.js`, and language codes. Accent folding also handles
letters such as ø, æ, ß, đ, ð, þ, ł, ı, and œ. A full native/English name, code, or first
alias takes precedence over partial matches: "farsi" resolves directly to Persian.

- One match offers its Opening, state, available EPUB/PDF files and sizes, and Share.
- Several matches show the first five. **View all matches** expands only the remaining
  results for that query in the same result region and focuses the first added link.
  Changing the query or clearing it resets the expanded results.
- No match offers the complete language list and contact with the author.
- Escape and the clear button reset the field. The result region uses `aria-live="polite"`.

**Browse all languages works without JavaScript.** `build_read_pages.py` emits one link
per visible edition, sorted by English name within two groups: complete books and
Opening-only editions. Both groups link to the edition's Opening, where downloads are
available. The links preserve native names, language tags, and RTL direction. JavaScript
fits long labels after opening the disclosure; it never creates a duplicate list.
`/sedaha/#allLangs` opens this disclosure when scripts run. The retired
`/sedaha/languages/` redirects there.

The nine quick choices are also static HTML. The finder may replace the Chinese fallback
with a complete edition matching the visitor's browser language, if it is not already
offered. The cycling language line respects reduced motion and pauses in hidden tabs.

Download help appears with file offers in search. The English Opening also explains EPUB
versus PDF and GitHub hosting. The navigation/footer shell remains English and is marked
with its language and direction; the Opening text and native names carry their own tags.
File sizes are visible beside download buttons rather than available only on hover.

## Cache updates

Pages are fetched network-first. Same-origin assets are served from cache and refreshed
in the background; GitHub downloads bypass the service worker. Bump `sw.js`'s `VERSION`
when deploying changed assets. The stylesheet URL is owned by `sync_head.py` and must
match the offline shell.

The finder URL is versioned in `sedaha/index.html` and the shell. Keep these identical:
an old finder would append its dynamic catalogue to the new static list. The guestbook
script URL is also versioned in its page and the shell, and its query version must match
the service worker version. `check.py` checks these relationships.

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

`sync_gallery.py` derives both gallery images and the web-sized English cover preview. The Sedaha gallery
masters come from `../1_Sedaha/Volume1/CoverPics`; other collections use the sibling
`../Paintings/` archive; `assets/img/book-cover.jpg` comes from the
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

The **preview card** is read from the Opening page's static Open Graph tags, not
from the share button. Each page has its own title and URL and uses the Opening painting
(`assets/img/paintings/sounds/01.jpg`). For generated languages, edit the generator's
metadata rather than its output. Opening-only editions can also be shared because they
have real pages; the search result states whether the complete book is available.

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

## Generated Opening pages (`build_read_pages.py`)

Beyond the hand-maintained EN/FA/DA pages, the generator knows 111 other editions.
It publishes 109 of those after `HIDDEN_SLUGS`, giving 112 public Opening pages in total.
Every language listed on `/sedaha/` has an Opening page.
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
Opening page, which read as a promise withdrawn. The same generator maintains the search data, static language links, and sitemap URLs. Slugs
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

**Opening-specific controls minimize visible English.** The shared navigation and footer
remain English. The old Opening-specific labels were: "← Sounds",
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
When an edition's EPUB/PDF is released, regeneration adds its own download buttons
automatically. Keep the page generated; no promotion to hand-maintained HTML is needed.

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

- **Book-page excerpt (author-approved 2026-10-07):** Use
  "… a thread of words that were once sounds…" in the book-page hero.
  This shorter excerpt is website copy; the canonical Opening is maintained in the book repo.
- **Boteh-Jegheh gallery introduction (author-approved 2026-10-07):**
  "Rooted in Persian art, the boteh-jegheh (known as paisley in English) becomes a way
  of looking at the world. Its familiar form takes on the colours and character of
  different places."
- **Book introduction (author-approved 2026-10-07):** Under the book-page title, use
  “A novel originally written in Persian, accompanied by the author’s paintings.”
- **Individual painting descriptions (author preference 2026-10-07):** Do not add descriptions
  to the paintings. Keep the existing titles and labels.
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
  (the auto-synced title inside the `/sedaha/` heading's `Sedaha (Sounds)` wrapper;
  the `/editions/first-edition/` archival page) or a fixed handle/URL (`Sounds_AmirArasteh`; the `/paintings/sounds/` path). The
  shared-opening cards use the **Opening painting** (`/assets/img/paintings/sounds/01.jpg` = the book's
  Picture 1), not the cover. **Exception (2026-07-17):** in the read pages' `og:title` share cards,
  the book is named by that edition's OWN translated title in «…», not the Latin brand (see
  "Card wording" above).
- **Never edit** `assets/img/logo-lockup.png` or the cover image. The logo is the author's full
  painting and is used whole (never cropped or redrawn).
- Announcements (new editions AND new paintings) go to the Telegram channel:
  <https://t.me/Sounds_AmirArasteh>. It is linked from the home secondary links and full-page footers;
  keep new pages' footers consistent.

## Analytics

GitHub release assets expose cumulative download counts per file; replacing a same-name asset
resets that file's count. The site has no page-view analytics, so visits to pages and in-browser
samples are not tracked. See [USEFUL_COMMANDS.md](USEFUL_COMMANDS.md) for the count commands.
