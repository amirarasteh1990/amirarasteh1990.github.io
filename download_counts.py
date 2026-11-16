#!/usr/bin/env python3
"""download_counts.py - how often each book and painting file has been downloaded.

Reads the `books` and `paintings` releases through the public GitHub API (one
unauthenticated, read-only GET per release; 60 an hour are allowed) and prints, per
release, every asset with its download count, most downloaded first, and the total.

    python download_counts.py                    # the table
    python download_counts.py --csv              # CSV on stdout
    python download_counts.py --csv counts.csv   # CSV to a file
    python download_counts.py -r books           # one release only

GitHub counts are per asset and cumulative; replacing an asset (--clobber) starts
its count again at zero. A release that does not exist yet is reported, not an error.
Writes nothing anywhere except the optional CSV file.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request

REPO = "amirarasteh1990/amirarasteh1990.github.io"
RELEASES = ("books", "paintings")
API = "https://api.github.com/repos/{repo}/releases/tags/{tag}"


def _ascii(text: object) -> str:
    """The console is cp1252; print ASCII only."""
    return str(text).encode("ascii", "replace").decode("ascii")


def fetch(tag: str) -> list[dict] | None:
    """The assets of one release, or None if the release does not exist."""
    req = urllib.request.Request(API.format(repo=REPO, tag=tag), headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "download-counts-script",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            release = json.load(r)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise SystemExit(_ascii(f"GitHub API {exc.code} for release '{tag}': {exc.reason}"))
    except urllib.error.URLError as exc:
        raise SystemExit(_ascii(f"cannot reach the GitHub API: {exc.reason}"))
    return [{"release": tag, "name": a["name"], "download_count": a["download_count"],
             "size": a["size"]} for a in release.get("assets", [])]


def main() -> int:
    ap = argparse.ArgumentParser(description="Download counts of the book and painting files.")
    ap.add_argument("--release", "-r", nargs="+", default=list(RELEASES), metavar="TAG",
                    help=f"releases to read (default: {' '.join(RELEASES)})")
    ap.add_argument("--csv", nargs="?", const="-", metavar="FILE",
                    help="write CSV (release,asset,download_count,size) to FILE, or stdout")
    args = ap.parse_args()

    rows, missing = [], []
    for tag in args.release:
        assets = fetch(tag)
        if assets is None:
            missing.append(tag)
            continue
        rows += sorted(assets, key=lambda a: (-a["download_count"], a["name"].lower()))

    if args.csv:
        out = sys.stdout if args.csv == "-" else open(args.csv, "w", newline="", encoding="utf-8")
        try:
            w = csv.writer(out, lineterminator="\n")
            w.writerow(["release", "asset", "download_count", "size"])
            for r in rows:
                w.writerow([r["release"], r["name"], r["download_count"], r["size"]])
        finally:
            if out is not sys.stdout:
                out.close()
        for tag in missing:
            print(f"release '{tag}' not found (not published yet)", file=sys.stderr)
        return 0

    width = max([len(_ascii(r["name"])) for r in rows] + [5])
    grand = 0
    for tag in args.release:
        if tag in missing:
            print(f"\n{tag}: release not found (not published yet)")
            continue
        mine = [r for r in rows if r["release"] == tag]
        total = sum(r["download_count"] for r in mine)
        grand += total
        print(f"\n{tag}: {len(mine)} assets, {total} downloads")
        print(f"  {'count':>7}  asset")
        print(f"  {'-' * 7}  {'-' * width}")
        for r in mine:
            print(f"  {r['download_count']:>7}  {_ascii(r['name'])}")
        print(f"  {total:>7}  total {tag}")
    print(f"\n{grand} downloads across {', '.join(t for t in args.release if t not in missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
