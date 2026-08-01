# Useful website commands

PowerShell cheat sheet for `arasteh.art`. Each code block is designed to be copied by itself unless marked as a sequence.

## Start here

Go to the website repository:

```powershell
Set-Location "C:\code\Others\1_Personal\amirarasteh.github.io"
```

See what has changed:

```powershell
git status --short
```

Before starting new work, update a clean working tree:

```powershell
git pull --ff-only
```

## Which maintenance command?

| What changed? | What to run |
| --- | --- |
| Ordinary HTML, CSS, JS, or documentation | Nothing; inspect and commit |
| Generated opening pages, language list, cards, or template | `build_read_pages.py` |
| Navigation shell — tab set, labels, or which tab a section highlights | `sync_appnav.py`, then `build_read_pages.py` |
| Installability / PWA head tags (manifest, standalone hints) | `sync_head.py`, then `build_read_pages.py` |
| Canonical English title or EN/FA/DA opening | `sync_book_text.py` |
| Gallery paintings or English cover preview | `sync_gallery.py` |
| Source TTF fonts | `build_webfonts.py` with the book virtual environment |
| Language names (a new language, or a new script among them) | `build_name_fonts.py` |
| The other names a language answers to in search (Farsi, Bangla, Mandarin) | Edit `assets/js/lang-alias.js`; nothing to rebuild. First name in each list wins ties |
| A guestbook note approved or featured in the private queue | `sync_guestbook.py --repo OWNER/PRIVATE_REPO` |
| A new complete edition released (EPUB/PDF uploaded) | `build_read_pages.py`. It reads the release, so the cards, counts, copy and status all follow. Nothing to type by hand |
| Paintings added or renamed | `sync_gallery.py`, then `build_read_pages.py` (sitemap images) |
| Anything at all, before pushing | `check.py` |
| EPUB/PDF | Upload to the `books` release; never commit book files |

EN/FA/DA opening pages are hand-maintained. The other 111 opening pages are generated; never edit those generated HTML files directly.

## Generated opening pages

Check without changing files:

```powershell
python build_read_pages.py --check
```

Regenerate when needed:

```powershell
python build_read_pages.py
```

Verify afterward:

```powershell
python build_read_pages.py --check
```

## Synchronize canonical book text

Check without changing files:

```powershell
python sync_book_text.py --check
```

Apply the synchronization:

```powershell
python sync_book_text.py
```

Verify afterward:

```powershell
python sync_book_text.py --check
```

Never hand-edit text inside `SYNC` markers; synchronization overwrites it.

## Navigation shell

The adaptive app shell (a bottom tab bar on phones, a sticky top bar on laptops)
is one `<nav class="appnav">` block owned by `sync_appnav.py` and stamped into
every page between `APPNAV` markers. Its styling lives in `assets/css/style.css`.

Check without changing files:

```powershell
python sync_appnav.py --check
```

Apply to every page:

```powershell
python sync_appnav.py
```

Then refresh the generated pages so they carry the same block:

```powershell
python build_read_pages.py
```

Never hand-edit markup inside `APPNAV` markers; the sync overwrites it. To change
the tabs, labels, or icons, edit the `TABS` list in `sync_appnav.py`.

## Installability (PWA)

The site is installable: a phone can Add to Home Screen and launch it full-screen.
This is the web-app manifest (`manifest.webmanifest`, with the `icon-192`,
`icon-512` and `icon-maskable-512` images) plus a small head block owned by
`sync_head.py` and stamped between `PWA` markers on every page.

Check without changing files:

```powershell
python sync_head.py --check
```

Apply to every page:

```powershell
python sync_head.py
```

Then refresh the generated pages so they carry the same block:

```powershell
python build_read_pages.py
```

The app icons are derived once from `assets/img/apple-touch-icon-180.png`. Only
regenerate them if that master changes:

```powershell
python -c "from PIL import Image; L=Image.Resampling.LANCZOS; s=Image.open('assets/img/apple-touch-icon-180.png').convert('RGB'); s.resize((192,192),L).save('assets/img/icon-192.png','PNG',optimize=True); s.resize((512,512),L).save('assets/img/icon-512.png','PNG',optimize=True); c=Image.new('RGB',(512,512),s.getpixel((2,2))); c.paste(s.resize((410,410),L),(51,51)); c.save('assets/img/icon-maskable-512.png','PNG',optimize=True)"
```

## Gallery and cover preview

Check derived images:

```powershell
python sync_gallery.py --check
```

Rebuild changed images:

```powershell
python sync_gallery.py
```

Rebuild every derived image only when deliberately needed:

```powershell
python sync_gallery.py --force
```

## Webfonts

Run only when the source TTF files or font-generation logic change:

```powershell
..\1_Sedaha\Volume1\sedaha\Scripts\python.exe build_webfonts.py
```

## Guestbook moderation

Visitors choose **For Amir only** or **Share it with others**. Private notes are
blocked from publication by the sync script. For a shareable note, add `approved`
in the private repository to publish it and optionally add `featured` to show it
near the front. Add `rejected`, or remove `approved`, to unpublish it on the next
sync.

For a complete local test without Cloudflare, follow the two-terminal commands in
`guestbook-worker/README.md`. Local pages automatically use the local intake at
`http://127.0.0.1:8787/`; the production endpoint meta can remain empty.

Pull all approved notes into one public JSON file per note and rebuild the compact
browser index. Replace the repository placeholder with the private queue's name:

```powershell
python sync_guestbook.py --repo OWNER/PRIVATE_REPO
```

Validate the public archive without contacting GitHub or changing files:

```powershell
python sync_guestbook.py --check
```

Review the generated entry files and index in the working-tree diff, then run
`python check.py`. The sync does not stage, commit, or push anything.

The one-time intake setup is documented in `guestbook-worker/README.md`. After
deploying it, put its HTTPS URL in the `guestbook-endpoint` meta tag in
`comments/index.html`. On the public site, submission remains unavailable until
that value exists; localhost uses the local intake described above.
There is deliberately no email fallback: the page says Amir received a note only
after the Worker verifies that GitHub created its private moderation issue.

## Preview locally

Start the local server:

```powershell
python -m http.server 8000
```

Open this in a second PowerShell window:

```powershell
Start-Process "http://localhost:8000"
```

Press `Ctrl+C` in the server window to stop it.

## Check everything at once

One command, no writes, run it last before a push. It runs every sync/build
script's own `--check`, `node --check` on each script, and the checks that no
single script owns: every local link resolving to a file, the service worker's
shell paths existing, `sitemap.xml` / `feed.xml` / the manifest / all 115 JSON-LD
blocks parsing, and the three hand-written opening pages still matching the
markup the generator stamps into the other 111.

```powershell
python check.py
```

Skip the eight script `--check` runs (the slow part) and keep the rest:

```powershell
python check.py --quick
```

Anything that fails is listed again at the end; the exit code is 1.

### After pushing: is the public site this site?

```powershell
python check.py --live
```

Fetches the home page, the book page, the language page and the stylesheet from
`arasteh.art` with a cache-busting query and compares each **byte for byte** with
the file here. A failure means the public copy is a different file, so the deploy
has not happened or has not finished; it never means something in this folder is
wrong. It also prints the first character that differs, which usually says at a
glance which change is missing.

## Inspect before committing

Check whitespace errors:

```powershell
git --no-pager diff --check
```

See a summary:

```powershell
git --no-pager diff --stat
```

Review the full changes:

```powershell
git --no-pager diff
```

## Commit and deploy — guarded

Pushing `main` publishes through GitHub Pages. Complete these steps in order.

1. Confirm that every listed change belongs in the commit:

```powershell
git status --short
```

2. Stage everything only after that review:

```powershell
git add -A
```

3. Check the staged files and staged content:

```powershell
git --no-pager diff --cached --stat
```

```powershell
git --no-pager diff --cached
```

```powershell
git --no-pager diff --cached --check
```

4. Enter the commit message when prompted:

```powershell
$message = Read-Host "Commit message"; git commit -m $message
```

5. Deploy only after typing `PUSH` exactly:

```powershell
if ((Read-Host "Type PUSH to deploy to arasteh.art") -ceq "PUSH") { git push origin main } else { Write-Host "Cancelled; nothing was pushed." }
```

## Publish current EPUB/PDF files — guarded

The public files come from **`Volume1/online/`**, and only from there. That is where
`python build.py online` puts them, flat and named `Sedaha_<Language>.{epub,pdf}`.

Build them first, in the book repository:

```powershell
Set-Location "C:\code\Others\1_Personal\1_Sedaha\Volume1"; python build.py online
```

Then come back here:

```powershell
Set-Location "C:\code\Others\1_Personal\amirarasteh.github.io"
```

Check GitHub CLI authentication:

```powershell
gh auth status
```

Inspect the rolling release:

```powershell
gh release view books
```

If the release does not exist, create it only after typing `CREATE`:

```powershell
if ((Read-Host "Type CREATE to create the public books release") -ceq "CREATE") { gh release create books --title "Sounds — current editions" --notes "Current downloadable editions." } else { Write-Host "Cancelled; no release was created." }
```

Collect what was built, newest first, with each file's size:

```powershell
$files = Get-ChildItem "..\1_Sedaha\Volume1\online" -File | Where-Object { $_.Extension -eq ".epub" -or $_.Extension -eq ".pdf" } | Sort-Object LastWriteTime -Descending
```

Review the exact upload list before sending anything:

```powershell
$files | Select-Object Name, @{n="MB";e={[math]::Round($_.Length/1MB,1)}}, LastWriteTime
```

A language you did not rebuild is simply absent from that list, and its copy on the
release is left untouched. If something you expected is missing, build it before
uploading rather than uploading a partial set and forgetting.

Upload and replace same-name assets only after typing `UPLOAD`:

```powershell
if ((Read-Host "Type UPLOAD to replace the listed public book assets") -ceq "UPLOAD") { gh release upload books @($files.FullName) --clobber } else { Write-Host "Cancelled; no assets were uploaded." }
```

`--clobber` replaces same-name assets and **resets their download counts**.

Then rebuild this site, because it reads the release: file sizes, the edition year,
the complete-edition count, every availability sentence, the status table and the
feed all come from those assets.

```powershell
python build_read_pages.py
```

```powershell
python check.py
```

### Two places this must never point

- **Not `Volume1/registration/`.** That folder is the archival deposit set, and it
  also holds `_print` and `_wrap` PDFs that must never reach a reader.
- **Not the `first-edition-1.0` release.** It is the frozen registered edition,
  permanently linked from `/editions/first-edition/` with its own ISBNs. Nothing is
  ever uploaded to it again. The rolling release is `books`.

## Release assets and download counts

List current assets:

```powershell
gh release view books
```

List counts by file:

```powershell
gh api repos/amirarasteh1990/amirarasteh1990.github.io/releases/tags/books --jq '.assets[] | [.download_count, .name] | @tsv'
```

Show the most downloaded first:

```powershell
gh api repos/amirarasteh1990/amirarasteh1990.github.io/releases/tags/books --jq '.assets | sort_by(.download_count) | reverse[] | [.download_count, .name] | @tsv'
```

### `show downloads` — counts plus change since last run

A small helper (defined in `~/sedaha-cli.ps1`, auto-loaded by the PowerShell
profile) prints each asset's count **and** how much it changed since the last
time you ran it. The default already includes the diff:

```powershell
show downloads
```

Add a total line, or turn the diff off:

```powershell
show downloads --total
```

```powershell
show downloads --no-diff
```

Peek at the diff without resetting the baseline:

```powershell
show downloads --no-save
```

The baseline snapshot lives in `~/.sedaha_download_counts.json` and only updates
when the diff is shown (i.e. not with `--no-diff` or `--no-save`). Delete that
file to reset the "since" point. If `show` is not recognized, the profile has not
loaded yet — open a new terminal, or run `. $PROFILE` once.

## Verify live preview metadata

Change only the URL when checking another language:

```powershell
$url = "https://arasteh.art/sedaha/read/fa/"; ((Invoke-WebRequest $url -UseBasicParsing).Content -split '\r?\n') | Select-String 'og:(title|description|url)'
```

For stale Telegram cards, open [@WebpageBot](https://t.me/WebpageBot), send `/updatepreview`, then send the exact public URL and test with a new message.

## Quick troubleshooting

- PowerShell shows `>>`: it is waiting for more input. Press `Ctrl+C`, then copy the complete command again.
- Git shows `(END)`: press `q` to leave the pager. Commands here use `--no-pager` where practical.
- Git warns that LF will become CRLF: this is a harmless Windows line-ending warning.
- `release not found`: inspect the tag name; create `books` only once and only with the guarded command above.

For detailed architecture and conventions, see [`WEBSITE_STATUS.md`](WEBSITE_STATUS.md).
