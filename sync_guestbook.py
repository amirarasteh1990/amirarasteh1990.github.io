#!/usr/bin/env python3
"""Import approved private issues and build the public guestbook index.

The browser-facing data contains only the chosen public name, note, language and
date. Pending submissions stay in a private GitHub repository. This script never
commits, stages, pushes, labels, closes, or otherwise writes to GitHub.

    python sync_guestbook.py --check
    python sync_guestbook.py --repo OWNER/PRIVATE_REPOSITORY
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
ENTRIES = SITE / "comments" / "entries"
INDEX = SITE / "assets" / "data" / "guestbook.json"
MARKER = re.compile(r"<!-- guestbook-submission:v1 ([A-Za-z0-9_-]+) -->")
ID_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]{6,64}$")
LANG_RE = re.compile(r"^(?:[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*|mul|und)$")


class GuestbookError(ValueError):
    pass


def clean_text(value: object, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise GuestbookError(f"{field} must be text")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not minimum <= len(value) <= maximum:
        raise GuestbookError(f"{field} must be {minimum}-{maximum} characters")
    if "\x00" in value:
        raise GuestbookError(f"{field} contains a null character")
    return value


def clean_line(value: object, field: str, minimum: int, maximum: int) -> str:
    value = clean_text(value, field, minimum, maximum)
    if "\n" in value:
        raise GuestbookError(f"{field} must stay on one line")
    return value


def validate_entry(raw: object, source: str) -> dict:
    if not isinstance(raw, dict):
        raise GuestbookError(f"{source}: entry must be an object")
    entry_id = clean_text(raw.get("id"), "id", 10, 80)
    if not ID_RE.fullmatch(entry_id):
        raise GuestbookError(f"{source}: invalid id {entry_id!r}")
    language = clean_text(raw.get("language"), "language", 2, 35)
    if not LANG_RE.fullmatch(language):
        raise GuestbookError(f"{source}: invalid language {language!r}")
    published = clean_text(raw.get("published"), "published", 10, 10)
    try:
        dt.date.fromisoformat(published)
    except ValueError as exc:
        raise GuestbookError(f"{source}: invalid published date") from exc
    featured = raw.get("featured", False)
    if not isinstance(featured, bool):
        raise GuestbookError(f"{source}: featured must be true or false")
    return {
        "id": entry_id,
        "name": clean_line(raw.get("name"), "name", 1, 80),
        "message": clean_text(raw.get("message"), "message", 1, 3000),
        "language": language,
        "language_name": clean_line(raw.get("language_name"), "language_name", 1, 80),
        "published": published,
        "featured": featured,
    }


def local_entries() -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    for path in sorted(ENTRIES.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            entry = validate_entry(raw, path.relative_to(SITE).as_posix())
        except (json.JSONDecodeError, OSError, GuestbookError) as exc:
            raise GuestbookError(str(exc)) from exc
        if path.stem != entry["id"]:
            raise GuestbookError(f"{path.name}: filename must equal its id")
        if entry["id"] in seen:
            raise GuestbookError(f"duplicate guestbook id {entry['id']}")
        seen.add(entry["id"])
        entries.append(entry)
    return sorted(entries, key=lambda e: (e["published"], e["id"]), reverse=True)


def index_object(entries: list[dict]) -> dict:
    return {"version": 1, "entries": entries}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8", newline="\n")


def check() -> int:
    try:
        entries = local_entries()
        actual = json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, GuestbookError) as exc:
        print(f"[stale] guestbook: {exc}")
        return 1
    expected = index_object(entries)
    if actual != expected:
        print("[stale] assets/data/guestbook.json: run python sync_guestbook.py")
        return 1
    print(f"[ok] guestbook: {len(entries)} published entries, index current")
    return 0


def decode_submission(body: str, issue_number: int) -> tuple[dict, str]:
    found = MARKER.search(body or "")
    if not found:
        raise GuestbookError(f"issue #{issue_number}: submission marker missing")
    token = found.group(1)
    token += "=" * (-len(token) % 4)
    try:
        raw = json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuestbookError(f"issue #{issue_number}: invalid submission marker") from exc
    submitted = clean_text(raw.get("submitted_at"), "submitted_at", 20, 40)
    try:
        date = dt.datetime.fromisoformat(submitted.replace("Z", "+00:00")).date().isoformat()
    except ValueError as exc:
        raise GuestbookError(f"issue #{issue_number}: invalid submitted_at") from exc
    audience = clean_line(raw.get("audience"), "audience", 6, 7)
    if audience not in {"private", "public"}:
        raise GuestbookError(f"issue #{issue_number}: invalid audience")
    entry = validate_entry({
        "id": raw.get("id"),
        "name": raw.get("name"),
        "message": raw.get("message"),
        "language": raw.get("language"),
        "language_name": raw.get("language_name"),
        "published": date,
        "featured": False,
    }, f"issue #{issue_number}")
    return entry, audience


def moderation_issues(repo: str) -> list[dict]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise GuestbookError("--repo must be OWNER/REPOSITORY")
    gh = shutil.which("gh")
    if not gh:
        raise GuestbookError("GitHub CLI (gh) is not installed")
    proc = subprocess.run([
        gh, "api", "--paginate", "--slurp",
        f"repos/{repo}/issues?state=all&labels=guestbook&per_page=100",
    ], cwd=SITE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode:
        raise GuestbookError(proc.stderr.strip() or "GitHub issue lookup failed")
    try:
        pages = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GuestbookError("GitHub returned invalid JSON") from exc
    return [issue for page in pages for issue in page if "pull_request" not in issue]


def sync(repo: str | None) -> int:
    imported = 0
    updated = 0
    removed = 0
    if repo:
        try:
            issues = moderation_issues(repo)
            known_ids: set[str] = set()
            published_ids: set[str] = set()
            for issue in issues:
                entry, audience = decode_submission(issue.get("body") or "", int(issue["number"]))
                known_ids.add(entry["id"])
                labels = {label.get("name", "").lower() for label in issue.get("labels", [])}
                if audience != "public" or "approved" not in labels or "rejected" in labels:
                    continue
                entry["featured"] = "featured" in labels
                published_ids.add(entry["id"])
                path = ENTRIES / f"{entry['id']}.json"
                existed = path.exists()
                old = json.loads(path.read_text(encoding="utf-8")) if existed else None
                write_json(path, entry)
                if not existed:
                    imported += 1
                elif old != entry:
                    updated += 1
            for entry_id in sorted(known_ids - published_ids):
                path = ENTRIES / f"{entry_id}.json"
                if path.exists():
                    path.unlink()
                    removed += 1
        except (OSError, json.JSONDecodeError, GuestbookError) as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
    try:
        entries = local_entries()
        write_json(INDEX, index_object(entries))
    except (OSError, GuestbookError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    if repo:
        print(f"guestbook: {imported} imported, {updated} updated, {removed} removed, "
              f"{len(entries)} published")
    else:
        print(f"guestbook index rebuilt from {len(entries)} published entries")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate without writing")
    parser.add_argument("--repo", help="private moderation repository, OWNER/REPOSITORY")
    args = parser.parse_args()
    if args.check:
        return check()
    return sync(args.repo)


if __name__ == "__main__":
    raise SystemExit(main())
