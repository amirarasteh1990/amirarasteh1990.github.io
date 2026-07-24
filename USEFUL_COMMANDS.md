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
| Canonical English title or EN/FA/DA opening | `sync_book_text.py` |
| Gallery paintings or English cover preview | `sync_gallery.py` |
| Source TTF fonts | `build_webfonts.py` with the book virtual environment |
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

Collect ordinary EPUB/PDF files while excluding print/wrap PDFs:

```powershell
$files = Get-ChildItem "..\1_Sedaha\Volume1\registration" -File | Where-Object { $_.Extension -eq ".epub" -or ($_.Extension -eq ".pdf" -and $_.BaseName -notmatch "_(print|wrap)$") } | Select-Object -ExpandProperty FullName
```

Review the exact upload list:

```powershell
$files
```

Upload and replace same-name assets only after typing `UPLOAD`:

```powershell
if ((Read-Host "Type UPLOAD to replace the listed public book assets") -ceq "UPLOAD") { gh release upload books @files --clobber } else { Write-Host "Cancelled; no assets were uploaded." }
```

`--clobber` replaces same-name assets and resets their download counts. The `first-edition-1.0` release is frozen; do not overwrite it.

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

Inspect the frozen release without changing it:

```powershell
gh release view first-edition-1.0
```

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
