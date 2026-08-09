#!/usr/bin/env python3
"""Import valid public GitHub issues and build the public guestbook index.

The browser-facing data contains only the chosen public name, note, language and
date. New submissions publish automatically and stay as public issues in the
website repository. This
script never commits, stages, pushes, labels, closes, or otherwise writes to GitHub.

    python sync_guestbook.py --check
    python sync_guestbook.py --repo OWNER/REPOSITORY
    python sync_guestbook.py --repo OWNER/REPOSITORY --issue NUMBER
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
ENTRIES = SITE / "comments" / "entries"
INDEX = SITE / "assets" / "data" / "guestbook.json"
MARKER_V1 = re.compile(r"<!-- guestbook-submission:v1 ([A-Za-z0-9_-]+) -->")
MARKER_V2 = re.compile(r"<!-- guestbook-submission:v2 ([A-Za-z0-9_-]+) -->")
PUBLIC_BODY = re.compile(
    r"## Name or pen name\s*\n+\s*<pre>(.*?)</pre>\s*\n+"
    r"## Language \(automatic\).*?\n+"
    r"## Reader note\s*\n+\s*<pre>(.*?)</pre>",
    re.DOTALL,
)
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


def decode_token(token: str, issue_number: int) -> dict:
    token += "=" * (-len(token) % 4)
    try:
        value = json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuestbookError(f"issue #{issue_number}: invalid submission marker") from exc
    if not isinstance(value, dict):
        raise GuestbookError(f"issue #{issue_number}: invalid submission marker")
    return value


def decode_submission(body: str, issue_number: int) -> tuple[dict, str]:
    body = body or ""
    v2 = MARKER_V2.search(body)
    v1 = MARKER_V1.search(body)
    if v2:
        raw = decode_token(v2.group(1), issue_number)
        fields = PUBLIC_BODY.search(body)
        if not fields:
            raise GuestbookError(f"issue #{issue_number}: public note fields missing")
        raw["name"] = clean_line(
            html.unescape(fields.group(1)), "name", 1, 40
        )
        raw["message"] = clean_text(
            html.unescape(fields.group(2)), "message", 1, 500
        )
    elif v1:
        raw = decode_token(v1.group(1), issue_number)
    else:
        raise GuestbookError(f"issue #{issue_number}: submission marker missing")
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


def bind_to_issue(entry: dict, issue: dict, issue_number: int) -> dict:
    """Use GitHub-owned values for identity and publication order."""
    created = clean_text(issue.get("created_at"), "created_at", 20, 40)
    try:
        published = dt.datetime.fromisoformat(
            created.replace("Z", "+00:00")
        ).date().isoformat()
    except ValueError as exc:
        raise GuestbookError(f"issue #{issue_number}: invalid created_at") from exc
    bound = dict(entry)
    bound["id"] = f"{published}-issue-{issue_number}"
    bound["published"] = published
    return validate_entry(bound, f"issue #{issue_number}")


def should_publish(labels: set[str], audience: str, new_submission: bool = False) -> bool:
    """Publish valid public notes; only owner moderation may reject one."""
    return ("guestbook" in labels and audience == "public"
            and (new_submission or "rejected" not in labels))


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


def moderation_issue(repo: str, issue_number: int) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise GuestbookError("--repo must be OWNER/REPOSITORY")
    if issue_number < 1:
        raise GuestbookError("--issue must be a positive issue number")
    gh = shutil.which("gh")
    if not gh:
        raise GuestbookError("GitHub CLI (gh) is not installed")
    proc = subprocess.run([
        gh, "api", f"repos/{repo}/issues/{issue_number}",
    ], cwd=SITE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode:
        raise GuestbookError(proc.stderr.strip() or "GitHub issue lookup failed")
    try:
        issue = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GuestbookError("GitHub returned invalid JSON") from exc
    if not isinstance(issue, dict) or "pull_request" in issue:
        raise GuestbookError(f"issue #{issue_number}: not a guestbook issue")
    return issue


def sync_one(repo: str, issue_number: int, new_submission: bool = False) -> int:
    try:
        issue = moderation_issue(repo, issue_number)
        entry, audience = decode_submission(issue.get("body") or "", issue_number)
        entry = bind_to_issue(entry, issue, issue_number)
        labels = {label.get("name", "").lower() for label in issue.get("labels", [])}
        path = ENTRIES / f"{entry['id']}.json"
        publish = should_publish(labels, audience, new_submission)
        action = "unchanged"
        if publish:
            entry["featured"] = not new_submission and "featured" in labels
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            write_json(path, entry)
            action = "published" if old != entry else "unchanged"
        elif path.exists():
            path.unlink()
            action = "removed"
        entries = local_entries()
        write_json(INDEX, index_object(entries))
    except (OSError, json.JSONDecodeError, GuestbookError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    print(f"guestbook issue #{issue_number}: {action}; {len(entries)} published")
    return 0


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
                labels = {label.get("name", "").lower() for label in issue.get("labels", [])}
                try:
                    entry, audience = decode_submission(
                        issue.get("body") or "", int(issue["number"])
                    )
                    entry = bind_to_issue(entry, issue, int(issue["number"]))
                except GuestbookError:
                    # Anyone can open a public issue. A malformed issue must not
                    # block a manual rebuild of the remaining valid archive.
                    continue
                known_ids.add(entry["id"])
                if not should_publish(labels, audience):
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
    parser.add_argument("--repo", help="moderation repository, OWNER/REPOSITORY")
    parser.add_argument("--issue", type=int, help="sync one guestbook issue number")
    parser.add_argument("--new-submission", action="store_true",
                        help="ignore owner-only labels on a newly opened issue")
    args = parser.parse_args()
    if args.check:
        return check()
    if args.issue is not None:
        if not args.repo:
            parser.error("--issue requires --repo")
        return sync_one(args.repo, args.issue, args.new_submission)
    if args.new_submission:
        parser.error("--new-submission requires --issue")
    return sync(args.repo)


if __name__ == "__main__":
    raise SystemExit(main())
