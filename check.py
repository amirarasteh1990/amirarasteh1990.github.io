#!/usr/bin/env python3
"""
check.py — one command that answers "is the site consistent?"

The site is stamped together by eight scripts: the nav shell, the footer, the head
block, the book text, the gallery derivatives, the 111 Opening pages, the name
subsets, and the published guestbook index. Each can already answer --check on its
own, but nobody remembers to run eight of them, and the interesting failures are
the ones no single script owns: a
link pointing at a file that was renamed, a service worker caching a path that no
longer exists, a hand-written page drifting away from the generator that owns the
same markup everywhere else.

So this runs all of them, then the checks between them:

  * every sync/build script's own --check
  * node --check on each script in assets/js and on sw.js  (skipped if no node)
  * every local href/src/srcset in all 124 pages resolves to a file on disk
  * every url(...) in the stylesheet resolves, and every path in sw.js's SHELL
  * sitemap.xml, feed.xml and the manifest parse, and every JSON-LD block is JSON
  * the three hand-written Opening pages still carry the generator's own hreflang
    cluster and reading toolbar, byte for byte

Nothing here writes: it is safe to run at any time, and it is the last thing to
run before a push.

    python check.py            everything
    python check.py --quick    skip the script --checks (the slow part)
"""
from __future__ import annotations

import argparse
import base64
import datetime
import html as htmllib
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import xml.dom.minidom
from pathlib import Path

from sync_head import STYLE_HREF

SITE = Path(__file__).resolve().parent
IGNORED_DIRS = {".git", ".wrangler", "node_modules"}

SCRIPTS = ["sync_appnav.py", "sync_footers.py", "sync_head.py", "sync_book_text.py",
           "sync_gallery.py", "build_read_pages.py", "build_name_fonts.py",
           "sync_guestbook.py"]

SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "javascript:", "data:")

failures: list[str] = []


def report(label: str, ok: bool, detail: str = "") -> bool:
    print(("[ok]    " if ok else "[FAIL]  ") + label + (("  " + detail) if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def pages() -> list[Path]:
    return sorted(
        p for p in SITE.rglob("*.html")
        if not IGNORED_DIRS.intersection(p.relative_to(SITE).parts)
    )


# --------------------------------------------------------------- the scripts
def run_scripts() -> None:
    for name in SCRIPTS:
        proc = subprocess.run([sys.executable, name, "--check"], cwd=SITE,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        bad = [ln for ln in (proc.stdout or "").splitlines()
               if ln.startswith(("[drift]", "[stale]", "[warn]"))]
        detail = bad[0] if bad else ""
        report(f"{name} --check", proc.returncode == 0, detail)


def run_node() -> None:
    node = shutil.which("node")
    if not node:
        print("[skip]  node --check (node not installed)")
        return
    files = (sorted((SITE / "assets" / "js").glob("*.js")) + [SITE / "sw.js"] +
             sorted((SITE / "guestbook-worker").glob("*.mjs")))
    bad = []
    for f in files:
        proc = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        if proc.returncode != 0:
            bad.append(f"{f.name}: {proc.stderr.strip().splitlines()[0]}")
    report(f"node --check on {len(files)} scripts", not bad, bad[0] if bad else "")
    worker_test = SITE / "guestbook-worker" / "test.mjs"
    if worker_test.is_file():
        proc = subprocess.run([node, str(worker_test)], cwd=SITE,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        report("account-free guestbook Worker contract",
               proc.returncode == 0, detail[0] if proc.returncode and detail else "")

# ------------------------------------------------------------ the link graph
def resolve(page: Path, url: str) -> Path | None:
    """Where a link points on disk, or None if it is not ours to check."""
    url = url.strip()
    if not url or url.startswith("#") or url.lower().startswith(SKIP_SCHEMES):
        return None
    url = urllib.parse.urldefrag(url)[0].split("?")[0]
    if not url:
        return None
    url = urllib.parse.unquote(url)
    target = (SITE / url.lstrip("/")) if url.startswith("/") else (page.parent / url)
    if url.endswith("/"):
        target = target / "index.html"
    return target


def links_in(body: str) -> list[str]:
    out = re.findall(r'(?:href|src)="([^"]+)"', body)
    for sets in re.findall(r'srcset="([^"]+)"', body):
        out += [part.strip().split(" ")[0] for part in sets.split(",") if part.strip()]
    return out


def crawl() -> None:
    missing = []
    for page in pages():
        body = page.read_text(encoding="utf-8")
        for url in links_in(body):
            target = resolve(page, htmllib.unescape(url))
            if target is not None and not target.exists():
                missing.append(f"{page.relative_to(SITE).as_posix()} -> {url}")
    report(f"{len(pages())} pages: every local link resolves", not missing,
           f"{len(missing)} broken, first: {missing[0]}" if missing else "")

    css = SITE / "assets" / "css" / "style.css"
    body = css.read_text(encoding="utf-8")
    bad = [u for u in re.findall(r'url\(([^)]+)\)', body)
           if not u.strip('"\'').startswith("data:")
           and not (SITE / u.strip('"\'').lstrip("/")).exists()]
    report("style.css: every url() resolves", not bad, bad[0] if bad else "")
    report("style.css: braces balanced", body.count("{") == body.count("}"),
           f"{body.count('{')} open, {body.count('}')} close")

    sw = (SITE / "sw.js").read_text(encoding="utf-8")
    shell = re.search(r"var SHELL = \[(.*?)\];", sw, re.S)
    paths = re.findall(r"'([^']+)'", shell.group(1)) if shell else []
    def local_shell_path(value: str) -> str:
        return value.split("?", 1)[0].split("#", 1)[0]

    gone = [p for p in paths
            if not (SITE / (local_shell_path(p).lstrip("/") or "index.html")).exists()
            and not (SITE / local_shell_path(p).lstrip("/") / "index.html").exists()]
    report(f"sw.js: {len(paths)} shell paths exist", bool(paths) and not gone,
           gone[0] if gone else ("SHELL not found" if not paths else ""))

    style_pages = []
    stale_styles = []
    for page in pages():
        hrefs = re.findall(r'<link rel="stylesheet" href="([^"]+)"',
                           page.read_text(encoding="utf-8"))
        for href in hrefs:
            style_pages.append(page)
            if href != STYLE_HREF:
                stale_styles.append(f"{page.relative_to(SITE).as_posix()} -> {href}")
    report(f"{len(style_pages)} pages pin the current stylesheet",
           bool(style_pages) and not stale_styles,
           stale_styles[0] if stale_styles else "")
    shell_styles = [p for p in paths
                    if local_shell_path(p) == "/assets/css/style.css"]
    report("the pages and offline shell pin the same stylesheet version",
           shell_styles == [STYLE_HREF],
           shell_styles[0] if shell_styles else "stylesheet missing from SHELL")


# ---------------------------------------------------------- machine-readable
def structured() -> None:
    for name in ("sitemap.xml", "feed.xml"):
        try:
            xml.dom.minidom.parse(str(SITE / name))
            report(f"{name} parses", True)
        except Exception as exc:  # noqa: BLE001 - the message is the finding
            report(f"{name} parses", False, str(exc))
    try:
        json.loads((SITE / "manifest.webmanifest").read_text(encoding="utf-8"))
        report("manifest.webmanifest parses", True)
    except Exception as exc:  # noqa: BLE001
        report("manifest.webmanifest parses", False, str(exc))

    try:
        index = json.loads((SITE / "assets" / "data" / "guestbook.json")
                           .read_text(encoding="utf-8"))
        valid = index.get("version") == 1 and isinstance(index.get("entries"), list)
        report("guestbook.json parses as a versioned entry index", valid)
    except Exception as exc:  # noqa: BLE001
        report("guestbook.json parses as a versioned entry index", False, str(exc))

    bad, found = [], 0
    for page in pages():
        for block in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>',
                page.read_text(encoding="utf-8"), re.S):
            found += 1
            try:
                json.loads(block)
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{page.relative_to(SITE).as_posix()}: {exc}")
    report(f"{found} JSON-LD blocks parse", not bad, bad[0] if bad else "")


def guestbook() -> None:
    """The account-free guestbook owns its public data and exposes no credential."""
    page = (SITE / "comments" / "index.html").read_text(encoding="utf-8")
    report("the guestbook has a simple public-note form",
           'id="guestbookForm"' in page and 'type="email"' not in page
           and 'name="audience"' not in page and 'maxlength="500"' in page)
    report("the account-free public handoff is explicit",
           'No account is needed' in page
           and 'chosen name and comment are public' in page
           and 'Press Post' in page
           and 'Amir receives a notification' in page)
    endpoint = re.search(
        r'<meta name="guestbook-endpoint" content="([^"]*)">', page
    )
    script = (SITE / "assets" / "js" / "guestbook.js").read_text(encoding="utf-8")
    endpoint_ok = bool(endpoint) and (not endpoint.group(1) or
                                      endpoint.group(1).startswith("https://"))
    report("the form declares a secure Worker endpoint", endpoint_ok,
           "deployment URL pending" if endpoint and not endpoint.group(1) else "")
    report("the browser contains no GitHub write credential",
           "api.github.com" not in script and "Authorization" not in script
           and "GITHUB_TOKEN" not in script and "guestbook-endpoint" in page)
    submit = re.search(r'<button[^>]*id="guestbookSubmit"[^>]*>', page)
    report("one Post button sends directly to the intake endpoint",
           bool(submit) and ">Post</button>" in page
           and "fetch(endpoint" in script and "data.posted !== true" in script
           and "credentials: 'omit'" in script
           and "location.assign(" not in script and "/issues/new" not in script)
    report("a confirmed note appears immediately and survives a short refresh",
           "addConfirmedEntry" in script and "localStorage" in script
           and "PENDING_TTL" in script and "Publishing" in script)
    script_url = re.search(r'<script src="(/assets/js/guestbook\.js\?v=([^"]+))"', page)
    sw = (SITE / "sw.js").read_text(encoding="utf-8")
    sw_version = re.search(r"var VERSION = 'arasteh-v([^']+)'", sw)
    pinned = (bool(script_url) and bool(sw_version)
              and script_url.group(2) == sw_version.group(1)
              and f"'{script_url.group(1)}'" in sw)
    report("the guestbook page and offline shell pin the same script version", pinned)
    report("the guestbook loads its repository-owned note reader",
           '/assets/js/guestbook.js' in page)

    worker_path = SITE / "guestbook-worker" / "worker.mjs"
    worker = worker_path.read_text(encoding="utf-8") if worker_path.is_file() else ""
    config_path = SITE / "guestbook-worker" / "wrangler.jsonc"
    config_text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    report("the Worker creates only validated public guestbook issues",
           "api.github.com/repos/" in worker
           and "guestbook-submission:v2" in worker
           and "['guestbook', 'pending', 'shareable']" in worker
           and "GITHUB_TOKEN" in worker and "Authorization" in worker
           and "message: cleanText(raw.message, 'Note', 1, 500)" in worker)
    report("the Worker rate-limits a salted digest and stores no raw address",
           "CF-Connecting-IP" in worker and "RATE_LIMIT_SALT" in worker
           and "crypto.subtle.digest('SHA-256'" in worker
           and "SUBMIT_RATE_LIMITER.limit" in worker
           and "request_id" in worker
           and "request.headers.get('User-Agent')" not in worker)
    try:
        worker_config = json.loads(config_text)
        config_ok = (
            worker_config.get("workers_dev") is True
            and worker_config.get("vars", {}).get("ALLOWED_ORIGINS") ==
            "https://arasteh.art"
            and worker_config.get("vars", {}).get("GITHUB_REPO") ==
            "amirarasteh1990.github.io"
            and set(worker_config.get("secrets", {}).get("required", [])) ==
            {"GITHUB_TOKEN", "RATE_LIMIT_SALT"}
            and worker_config.get("ratelimits", [{}])[0].get("name") ==
            "SUBMIT_RATE_LIMITER"
        )
    except (OSError, json.JSONDecodeError, IndexError):
        config_ok = False
    report("Wrangler requires secrets and the free-plan rate limiter", config_ok)

    workflow_path = SITE / ".github" / "workflows" / "publish-guestbook.yml"
    workflow = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    report("valid new issues publish and notify the owner automatically",
           "issues:" in workflow and "contents: write" in workflow
           and "types: [opened, labeled, unlabeled, edited]" in workflow
           and "issues: write" in workflow
           and "pages: write" in workflow
           and "actions/checkout@v7" in workflow
           and "ref: ${{ github.event.repository.default_branch }}" in workflow
           and "github.event.action == 'opened'" in workflow
           and "github.actor == github.repository_owner" in workflow
           and "contains(github.event.issue.body, '<!-- guestbook-submission:v2 ')" in workflow
           and "ensure_label guestbook" in workflow
           and "ensure_label rejected" in workflow
           and "--new-submission" in workflow
           and "assignees[]=amirarasteh1990" in workflow
           and 'python sync_guestbook.py --repo "$GITHUB_REPOSITORY" --issue "$ISSUE_NUMBER"' in workflow
           and "git add -- comments/entries assets/data/guestbook.json" in workflow
           and 'repos/$GITHUB_REPOSITORY/pages/builds' in workflow)

    automation_ok = False
    try:
        import sync_guestbook as guestbook_sync
        sample = {
            "id": "2026-08-02-abc12345",
            "language": "en",
            "language_name": "English",
            "audience": "public",
            "submitted_at": "2026-08-02T12:00:00.000Z",
        }
        token = base64.urlsafe_b64encode(
            json.dumps(sample).encode("utf-8")
        ).decode("ascii").rstrip("=")
        body = (f"<!-- guestbook-submission:v2 {token} -->\n\n"
                "## Name or pen name\n\n<pre>A Reader</pre>\n\n"
                "## Language (automatic)\n\nEnglish (`en`)\n\n"
                "## Reader note\n\n<pre>A &amp; B</pre>")
        entry, audience = guestbook_sync.decode_submission(body, 1)
        marker_ok = (entry["name"] == "A Reader" and entry["message"] == "A & B"
                     and audience == "public")
        bound = guestbook_sync.bind_to_issue(
            entry, {"created_at": "2026-08-03T08:30:00Z"}, 27
        )
        automation_ok = (
            bound["id"] == "2026-08-03-issue-27"
            and bound["published"] == "2026-08-03"
            and guestbook_sync.should_publish(
                {"guestbook", "pending", "shareable"}, "public", True
            )
            and not guestbook_sync.should_publish(
                {"guestbook", "rejected"}, "public"
            )
            and not guestbook_sync.should_publish({"guestbook"}, "private", True)
        )
        try:
            guestbook_sync.decode_submission(
                body.replace("A &amp; B", "x" * 501), 2
            )
            automation_ok = False
        except guestbook_sync.GuestbookError:
            pass
    except Exception:  # noqa: BLE001 - a failed parser is the finding
        marker_ok = False
    report("the public issue marker round-trips into a validated entry", marker_ok)
    report("GitHub-owned IDs and dates protect automatic publication", automation_ok)

    legacy = []
    # Keep the retired provider name and identifier out of the tree even in this
    # guard, while still catching an accidental paste of either literal.
    needles = ("cus" + "dis", "8b259adb-2d93-412b-925f-" + "530dd86d91a5")
    suffixes = {".html", ".css", ".js", ".mjs", ".md", ".py", ".toml", ".json"}
    for path in SITE.rglob("*"):
        if (not path.is_file()
                or IGNORED_DIRS.intersection(path.relative_to(SITE).parts)
                or path.suffix.lower() not in suffixes):
            continue
        body = path.read_text(encoding="utf-8", errors="replace").lower()
        if any(needle in body for needle in needles):
            legacy.append(path.relative_to(SITE).as_posix())
    report("no legacy comment-service trace remains", not legacy,
           legacy[0] if legacy else "")


# ------------------------------------------------- hand-written vs generated
def hand_written() -> None:
    """The three hand-maintained Opening pages carry markup the generator owns for
    the other 111. Nothing stamps it there, so compare it here."""
    sys.path.insert(0, str(SITE))
    import build_read_pages as gen

    hand = ["sedaha/read/index.html", "sedaha/read/fa/index.html", "sedaha/read/da/index.html"]
    bare = [rel for rel in hand
            if 'class="op-bar"' not in (SITE / rel).read_text(encoding="utf-8")]
    report("EN/FA/DA Opening pages: the top action bar is there too", not bare,
           ", ".join(bare))
    for what, want in (("hreflang cluster", gen.alternates()),
                       ("reading toolbar", gen.reader_tools_html())):
        off = [rel for rel in hand
               if want not in (SITE / rel).read_text(encoding="utf-8")]
        report(f"EN/FA/DA Opening pages: {what} matches the generator", not off,
               ", ".join(off))

    # the language strip differs per page (each marks a different language current),
    # so ask the generator for the one that page should be carrying
    off = [rel for rel, slug in zip(hand, ("", "fa/", "da/"))
           if gen.op_langs_html(slug) not in (SITE / rel).read_text(encoding="utf-8")]
    report("EN/FA/DA Opening pages: language strip matches the generator", not off,
           ", ".join(off))

    stale = [rel for rel in hand
             if "read-kicker" in (SITE / rel).read_text(encoding="utf-8")]
    report("EN/FA/DA Opening pages: no leftover English kicker", not stale, ", ".join(stale))

    missing = [rel for rel in hand
               if "/assets/js/reader.js" not in (SITE / rel).read_text(encoding="utf-8")]
    report("EN/FA/DA Opening pages: reader.js loaded", not missing, ", ".join(missing))


def availability() -> None:
    """One availability story, told the same everywhere.

    The generator can be perfectly happy while the page is wrong, and the reason
    this exists is that Italian was complete and downloadable for weeks while
    three pages said three. /sedaha/ is a doorway now and names no language at
    all, so the guard moved with the data: what must hold is that editions.js
    carries every edition the site shows, with the files each one really has."""
    sys.path.insert(0, str(SITE))
    import build_read_pages as gen

    rows = gen.status_rows()
    site_rows = gen.shown(rows)
    done = [r["en"] for r in gen.complete_rows(site_rows)]
    book = (SITE / "sedaha" / "index.html").read_text(encoding="utf-8")
    data = (SITE / "assets" / "js" / "editions.js").read_text(encoding="utf-8")

    listed = re.findall(r'"slug":"([^"]+)"', data)
    report(f"editions.js carries all {len(site_rows)} languages the site shows",
           len(listed) == len(site_rows),
           f"{len(listed)} in the data, {len(site_rows)} in the record")

    ready = [ln for ln in data.splitlines() if '"state":"ready"' in ln]
    report(f"editions.js marks all {len(done)} complete editions as such",
           len(ready) == len(done), f"{len(ready)} ready in the data, {len(done)} complete")

    fileless = [ln for ln in ready if '"files"' not in ln]
    report("every complete edition in the data has files to offer", not fileless,
           re.search(r'"en":"([^"]+)"', fileless[0]).group(1) if fileless else "")

    stray = len(re.findall(r'<div class="ed-featured"|<li class="dl-row"|class="continent"',
                           book))
    report("/sedaha/ still holds no catalogue of its own", stray == 0,
           f"{stray} catalogue elements found")

    home = (SITE / "index.html").read_text(encoding="utf-8")
    # site_rows, not rows: patch_availability() stamps the pages from shown(rows), so
    # checking against the unfiltered book list asks the pages to state a number they
    # were never given. Dormant until 2026-08-05, because it only bites when a HIDDEN
    # edition is downloadable — Hebrew ships on the release but not on the site, so the
    # two counts diverged by exactly one the day the full set was uploaded.
    sentence = gen.availability(site_rows, len(rows))["long"]
    tellers = {"index.html": home, "sedaha/index.html": book}
    off = [name for name, body in tellers.items() if sentence not in body]
    report("the availability sentence is the same on every page that tells it",
           not off, ", ".join(off))

    stale = [name for name, body in tellers.items()
             if re.search(r"free to read in .*hundred", body)
             and "og:image:alt" not in body.split("hundred")[0][-200:]]
    report("no page still claims the whole book in a hundred languages", not stale,
           ", ".join(stale))

    # An edition the author has asked the site not to carry must be absent from all
    # of it, not merely unlinked: the page, the lists, the hreflang cluster, the
    # sitemap, the feed, the search aliases. The book keeps it; the site is quiet.
    for slug in sorted(gen.HIDDEN_SLUGS):
        row = next((r for r in rows if r["slug"] == slug), None)
        needles = [f"/sedaha/read/{slug}/", f'hreflang="{row["lang"]}"' if row else "",
                   row["native"] if row else "", row["en"] if row else ""]
        needles = [n for n in needles if n]
        seen = []
        for path in list(pages()) + [SITE / "sitemap.xml", SITE / "feed.xml",
                                     SITE / "assets" / "js" / "lang-alias.js"]:
            body = path.read_text(encoding="utf-8")
            hit = [n for n in needles if n in body]
            if hit:
                seen.append(f"{path.relative_to(SITE).as_posix()} ({hit[0]})")
        name = row["en"] if row else slug
        report(f"{name} is hidden from the site, as asked", not seen,
               f"{len(seen)} page(s), first: {seen[0]}" if seen else "")


def logo() -> None:
    """The dark logo must be the same painting, and must arrive by CSS.

    Two failures are being guarded against, both of which happened. The first: the
    dark variant was made by recolouring palette entries, which the painting shares,
    so the artwork itself was repainted. Nothing in the page would have shown that.
    So the painting's pixels are compared against the light file directly.

    The second: a <picture media="(prefers-color-scheme:dark)"> looks right and
    ignores the reader's own theme choice, because that choice works by re-pointing
    the stylesheet's media rule and has no effect on markup. So the logo must not be
    an <img> at all, and the cream plaque it used to sit on must be gone."""
    light = SITE / "assets" / "img" / "logo-lockup.png"
    dark = SITE / "assets" / "img" / "logo-lockup-dark.png"
    if not report("the dark logo exists", dark.exists(),
                  "" if dark.exists() else "run python sync_gallery.py"):
        return

    try:
        from PIL import Image
    except ImportError:
        report("the dark logo keeps the painting", True, "skipped: Pillow not installed")
    else:
        a, b = (Image.open(p).convert("RGBA") for p in (light, dark))
        if a.size != b.size:
            report("the dark logo keeps the painting", False,
                   f"{a.size} against {b.size}")
        else:
            w, h = a.size
            pa, pb = a.load(), b.load()
            # the painting is every row above the first fully clear one
            solid = [y for y in range(h)
                     if sum(1 for x in range(w) if pa[x, y][3] > 40) > w * 0.9]
            gap = next((y for y in range(solid[-1] + 1, h)
                        if all(pa[x, y][3] <= 40 for x in range(w))), h)
            bad = next(((x, y) for y in range(gap) for x in range(w)
                        if pa[x, y] != pb[x, y]), None)
            report("the dark logo keeps the painting, pixel for pixel", bad is None,
                   f"rows 0-{gap - 1} match" if bad is None
                   else f"differs at {bad}; the artwork has been altered")
            lit = sum(1 for y in range(gap, h) for x in range(w)
                      if pb[x, y][3] > 0 and pb[x, y][:3] != pa[x, y][:3])
            report("the dark logo relettered the name", lit > 0, f"{lit} pixels")

    css = (SITE / "assets" / "css" / "style.css").read_text(encoding="utf-8")
    imgs = [p.relative_to(SITE).as_posix() for p in pages()
            if re.search(r"<img[^>]*logo-lockup", p.read_text(encoding="utf-8"))]
    report("no page pins the logo to one theme with an <img>", not imgs,
           f"{len(imgs)} page(s), first: {imgs[0]}" if imgs else "")

    # a page's own <style> is later in the document than the sheet holding the dark
    # rule, so declaring the image there silently defeats the swap on that page
    own = [p.relative_to(SITE).as_posix() for p in pages()
           if any("logo-lockup" in s for s in
                  re.findall(r"<style[^>]*>(.*?)</style>",
                             p.read_text(encoding="utf-8"), re.S))]
    report("no page declares the logo image in its own <style>", not own,
           f"{len(own)} page(s), first: {own[0]}" if own else "")

    m = re.search(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{(.*)", css, re.S)
    block = m.group(1) if m else ""
    report("the dark theme swaps the logo file",
           "logo-lockup-dark" in block, "" if "logo-lockup-dark" in block
           else "the dark block never names the dark asset")
    plaque = [line.strip() for line in block.splitlines()
              if re.search(r"(logo|nf-logo)\b", line)
              and re.search(r"background:\s*rgba\(2[34]", line)]
    report("the logo sits on no cream plaque in the dark",
           not plaque, plaque[0] if plaque else "")


def band() -> None:
    """The texture behind the language boxes is the painting, not the cover.

    Worth a check because the two look alike at a glance and the wrong one is the
    cover composition, title lettering and all, tiled behind a hundred chips. The
    asset is also a decoration under a scrim, so it has a weight ceiling: if it ever
    creeps back up to gallery quality, that is a mistake, not a decision."""
    css = (SITE / "assets" / "css" / "style.css").read_text(encoding="utf-8")
    report("the language boxes no longer wear the cover",
           "book-cover-band" not in css,
           "" if "book-cover-band" not in css else "style.css still names the cover band")
    jpg = SITE / "assets" / "img" / "book-painting-band.jpg"
    webp = jpg.with_suffix(".webp")
    if not report("the painting band exists", jpg.is_file() and webp.is_file(),
                  "" if webp.is_file() else "run python sync_gallery.py"):
        return
    kb = webp.stat().st_size // 1024
    report("the painting band stays a decoration", kb <= 48,
           f"{kb} KB webp" + ("" if kb <= 48 else "; too heavy for a chip texture"))


def paintings() -> None:
    """The collection index shows the galleries that exist, and only those.

    The failure this guards against is the one the index started with: tiles saying
    "Coming soon" over no image at all, sitting beside a real gallery and reading
    like links that are broken rather than ones that do not exist yet. So the tile
    count is held to the gallery folders on disk, and every tile must have a picture
    to show."""
    page = (SITE / "paintings" / "index.html").read_text(encoding="utf-8")
    tiles = re.findall(r'<a class="painting-collection"[^>]*data-gallery="([^"]+)"', page)
    folders = sorted(p.name for p in (SITE / "paintings").iterdir() if p.is_dir())
    report("every gallery on disk has a tile, and no tile is invented",
           sorted(tiles) == folders, f"{tiles} against {folders}")

    missing = [g for g in tiles
               if not (SITE / "assets" / "img" / "paintings" / "index" / f"{g}.webp").is_file()]
    report("every tile has a painting to show", not missing, ", ".join(missing))

    # the generic card system belongs to the home page; this index must not reach into it
    css = (SITE / "assets" / "css" / "style.css").read_text(encoding="utf-8")
    report("the paintings index overrides no shared card rule",
           not re.search(r"\.paintings-page\s+\.cards?\b", css))
    report("and the gallery's CSS is shared, not inlined per page",
           "<style>" not in (SITE / "paintings" / "sounds" / "index.html")
                            .read_text(encoding="utf-8"))


LIVE = "https://arasteh.art"


def live() -> None:
    """Is the public site the site in this folder?

    Asked because a reviewer read arasteh.art, saw four complete editions and
    region-first browsing, and could not tell whether that was a stale crawler, a
    stale CDN, or simply a deploy that had never happened. It was the third. Rather
    than argue about caches, fetch the pages and compare them with what is here.

    Each request carries a cache-busting query and a no-store header, so what comes
    back is what GitHub Pages is serving now."""
    import urllib.error
    import urllib.request

    pages_to_check = {
        "/": SITE / "index.html",
        "/sedaha/": SITE / "sedaha" / "index.html",
        # /sedaha/languages/ is retired: a redirect stub, nothing to compare
        "/assets/css/style.css": SITE / "assets" / "css" / "style.css",
    }
    stamp = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp()))
    for path, local in pages_to_check.items():
        url = f"{LIVE}{path}?nocache={stamp}"
        try:
            req = urllib.request.Request(url, headers={
                "Cache-Control": "no-store", "Pragma": "no-cache",
                "User-Agent": "arasteh-check"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001 - the message is the finding
            report(f"live {path}", False, f"{type(exc).__name__}: {exc}")
            continue
        # byte comparison, not a keyword search: Pages serves these files verbatim,
        # so anything short of equality means the public copy is a different file.
        # Looking for a phrase instead would have passed happily on a version that
        # merely shared that phrase, which is the ambiguity this exists to remove.
        here = local.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        there = body.replace("\r\n", "\n").strip()
        if here == there:
            report(f"live {path} is byte-for-byte this file", True)
            continue
        at = next((i for i, (a, b) in enumerate(zip(here, there)) if a != b),
                  min(len(here), len(there)))
        report(f"live {path} is byte-for-byte this file", False,
               f"differs at character {at}: public has {there[at:at + 40]!r}")
    print("\n    A failure above means the public copy is not this copy: either the")
    print("    deploy has not happened, or it is still running. Nothing here is wrong.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--quick", action="store_true",
                    help="skip the per-script --check runs (the slow part)")
    ap.add_argument("--live", action="store_true",
                    help="also ask arasteh.art whether it is serving this version "
                         "(run after pushing)")
    args = ap.parse_args()

    if args.live:
        live()
        print()
        if failures:
            print(f"{len(failures)} check(s) failed:")
            for f in failures:
                print("  - " + f)
            return 1
        print("the public site matches this working tree.")
        return 0

    if args.quick:
        print("[skip]  the eight script --checks (--quick)")
    else:
        run_scripts()
    run_node()
    crawl()
    structured()
    guestbook()
    hand_written()
    availability()
    logo()
    band()
    paintings()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print("  - " + f)
        return 1
    print("everything consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
