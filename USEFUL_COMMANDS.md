# Useful website commands

Run these from:

```powershell
cd C:\code\Others\1_Personal\amirarasteh.github.io
```

For conventions and ownership details, see [`WEBSITE_STATUS.md`](WEBSITE_STATUS.md).

## Quick decision guide

| Change | Command |
| --- | --- |
| Ordinary HTML, CSS, JS, or documentation | No build command |
| Generated opening pages, language list, cards, or generator template | `python build_read_pages.py` |
| Canonical title or EN/FA/DA opening changed in the book repo | `python sync_book_text.py` |
| Gallery paintings or English cover preview changed | `python sync_gallery.py` |
| Source TTF fonts changed | Run `build_webfonts.py` with the book virtual environment |
| EPUB/PDF changed | Upload it to the `books` GitHub Release; do not commit it |

The EN/FA/DA opening pages are hand-maintained. The other 111 opening pages are generated; never edit those generated files directly.

## Inspect changes

```powershell
# Before editing, when the working tree is clean
git pull --ff-only

git status --short
git --no-pager diff --check
git --no-pager diff --stat
git --no-pager diff
```

## Generated opening pages

```powershell
# Check only; changes nothing and exits nonzero if stale
python build_read_pages.py --check

# Regenerate, then verify
python build_read_pages.py
python build_read_pages.py --check
```

## Synchronize canonical book text

```powershell
python sync_book_text.py --check
python sync_book_text.py
python sync_book_text.py --check
```

Do not hand-edit text inside `SYNC` markers; synchronization overwrites it.

## Gallery and cover preview

```powershell
python sync_gallery.py --check
python sync_gallery.py
python sync_gallery.py --check

# Rebuild every derived image only when deliberately needed
python sync_gallery.py --force
```

## Webfonts

Run only when the book repository's TTF files change:

```powershell
..\1_Sedaha\Volume1\sedaha\Scripts\python.exe build_webfonts.py
```

## Preview locally

```powershell
python -m http.server 8000
```

Open <http://localhost:8000>, then press `Ctrl+C` to stop the server.

## Stage, commit, and deploy

Pushing `main` deploys the website through GitHub Pages.

```powershell
git add <files-or-folders-you-reviewed>
git --no-pager diff --cached --check
git --no-pager diff --cached --stat
git --no-pager diff --cached
git commit -m "Describe the website change"
git push origin main
```

When every working-tree change is intentional, PowerShell 7 supports the documented one-liner:

```powershell
git add -A && git commit -m "Describe the website change" && git push origin main
```

## Publish current EPUB/PDF files

Book files belong in the rolling `books` release, not Git:

```powershell
gh auth status
gh release view books

# Create the rolling release only if it does not exist
gh release create books --title "Sounds — current editions" --notes "Current downloadable editions."

# Upload selected files
gh release upload books C:\path\to\Sedaha_English.pdf C:\path\to\Sedaha_English.epub --clobber
```

Upload all normal EPUB/PDF files from the book registration folder while excluding print/wrap PDFs:

```powershell
$files = Get-ChildItem "..\1_Sedaha\Volume1\registration" -File |
    Where-Object {
        $_.Extension -eq ".epub" -or
        ($_.Extension -eq ".pdf" -and $_.BaseName -notmatch "_(print|wrap)$")
    } |
    Select-Object -ExpandProperty FullName

$files
gh release upload books @files --clobber
```

Review `$files` before uploading. Do not overwrite the frozen `first-edition-2026` release casually.
Replacing a same-name asset with `--clobber` resets that asset's download count.

## Release assets and download counts

```powershell
gh release view books
gh release view first-edition-2026

# One row per asset
gh api repos/amirarasteh1990/amirarasteh1990.github.io/releases/tags/books `
    --jq '.assets[] | "\(.download_count)\t\(.name)"'

# Most downloaded first
gh api repos/amirarasteh1990/amirarasteh1990.github.io/releases/tags/books `
    --jq '.assets | sort_by(.download_count) | reverse[] | "\(.download_count)\t\(.name)"'
```

## Verify live preview metadata

```powershell
$url = "https://arasteh.art/sedaha/read/fa/"
$response = Invoke-WebRequest $url -UseBasicParsing
($response.Content -split "`n") | Select-String 'og:(title|description|url)'
```

For stale Telegram cards, open [@WebpageBot](https://t.me/WebpageBot), send `/updatepreview`, then send the exact URL and test with a new message.
