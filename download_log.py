#!/usr/bin/env python3
"""download_log.py -- who downloads the books and paintings: readers or robots, from where.

Every download button on arasteh.art goes through the guestbook Worker's /dl/ route,
which records one event (time, file, country, network owner, kind of client, the
site the click came from; never an IP address) and then hands the file over from the
GitHub release, which still counts it as before (download_counts.py, `show downloads`).

    python download_log.py --setup         # once: make the private key, store it in the Worker
    python download_log.py                 # the last 7 days, summarised
    python download_log.py --days 30
    python download_log.py --day 2026-11-17 --raw    # every event of one day (TSV)

The key lives in ~/.sedaha_stats_key (outside the repo) and as the Worker secret
STATS_KEY; only someone holding it can read the events. Output is ASCII only (the
console is cp1252), so non-Latin text in a user agent shows as '?'.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

WORKER = "https://arasteh-guestbook.amir-arasteh.workers.dev/"
KEY_FILE = Path.home() / ".sedaha_stats_key"
WORKER_DIR = Path(__file__).resolve().parent / "guestbook-worker"
KINDS = ("browser", "bot", "other", "none")
BURST_MINUTES, BURST_MIN = 30, 25   # this many downloads inside this window = a burst


def a(text: object) -> str:
    return str(text).encode("ascii", "replace").decode("ascii")


def setup(new: bool) -> int:
    if KEY_FILE.is_file() and not new:
        key = KEY_FILE.read_text(encoding="utf-8").strip()
        print(f"using the existing key in {KEY_FILE}")
    else:
        key = secrets.token_urlsafe(32)
        KEY_FILE.write_text(key, encoding="utf-8")
        print(f"new key written to {KEY_FILE}")
    npx = "npx.cmd" if os.name == "nt" else "npx"
    print("storing it in the Worker as STATS_KEY (wrangler secret put) ...")
    done = subprocess.run([npx, "wrangler", "secret", "put", "STATS_KEY"], input=key,
                          text=True, cwd=WORKER_DIR)
    if done.returncode:
        print("wrangler failed; nothing else changed. Is wrangler logged in to the guestbook account?")
        return 1
    print("done. Deploy the Worker (npm run deploy) if you have not yet.")
    return 0


def fetch_day(day: str, key: str) -> list[dict]:
    req = urllib.request.Request(f"{WORKER}dl-stats?day={day}", headers={
        "Authorization": f"Bearer {key}", "User-Agent": "arasteh-download-log"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")).get("events", [])
    except urllib.error.HTTPError as exc:
        msg = {401: "the key was refused (run --setup again?)",
               503: "the Worker has no store or key yet (see --setup and the README)"}
        raise SystemExit(f"{day}: HTTP {exc.code}: {msg.get(exc.code, exc.reason)}")


def bursts(events: list[dict]) -> list[list[dict]]:
    """Runs of >= BURST_MIN downloads where each falls within BURST_MINUTES of the run's start."""
    out, i = [], 0
    ev = sorted(events, key=lambda e: e["t"])
    times = [dt.datetime.fromisoformat(e["t"].replace("Z", "+00:00")) for e in ev]
    while i < len(ev):
        j = i
        while j + 1 < len(ev) and times[j + 1] - times[i] <= dt.timedelta(minutes=BURST_MINUTES):
            j += 1
        if j - i + 1 >= BURST_MIN:
            out.append(ev[i:j + 1])
            i = j + 1
        else:
            i += 1
    return out


def top(counter: collections.Counter, n: int = 6) -> str:
    return ", ".join(f"{a(k) or '(none)'} {v}" for k, v in counter.most_common(n)) or "-"


def summarise(day: str, events: list[dict]) -> None:
    kinds = collections.Counter(e.get("k", "none") for e in events)
    print(f"\n{day}  total {len(events)}  " + "  ".join(f"{k} {kinds.get(k, 0)}" for k in KINDS))
    if not events:
        return
    print(f"  countries : {top(collections.Counter(e.get('c', '') for e in events))}")
    print(f"  networks  : {top(collections.Counter(e.get('o', '') for e in events))}")
    print(f"  came from : {top(collections.Counter(e.get('f', '') for e in events))}")
    print(f"  files     : {top(collections.Counter(e.get('r', '') for e in events))}")
    bots = collections.Counter(e.get("u", "")[:70] for e in events if e.get("k") != "browser")
    if bots:
        print(f"  non-browser agents: {top(bots, 4)}")
    for run in bursts(events):
        net = collections.Counter(e.get("o", "") for e in run).most_common(1)[0]
        agent = collections.Counter(e.get("u", "")[:70] for e in run).most_common(1)[0][0]
        land = collections.Counter(e.get("c", "") for e in run).most_common(1)[0][0]
        print(f"  BURST {run[0]['t'][11:16]}-{run[-1]['t'][11:16]} UTC: {len(run)} files, "
              f"{len({e.get('a') for e in run})} distinct; network {a(net[0]) or '?'} ({net[1]}), "
              f"country {land or '?'}, agent {a(agent) or '(none)'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarise who downloads the books and paintings.")
    ap.add_argument("--setup", action="store_true", help="make/store the private key (once)")
    ap.add_argument("--new-key", action="store_true", help="with --setup: replace the key")
    ap.add_argument("--days", type=int, default=7, help="how many days back (default 7)")
    ap.add_argument("--day", help="one day, YYYY-MM-DD (UTC)")
    ap.add_argument("--raw", action="store_true", help="print every event as TSV")
    args = ap.parse_args()
    if args.setup:
        return setup(args.new_key)
    if not KEY_FILE.is_file():
        print(f"no key in {KEY_FILE}: run  python download_log.py --setup  first")
        return 1
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    today = dt.datetime.now(dt.timezone.utc).date()
    days = [args.day] if args.day else [str(today - dt.timedelta(days=n))
                                          for n in range(args.days - 1, -1, -1)]
    shown = 0
    for day in days:
        events = fetch_day(day, key)
        if not events and not args.day:
            continue                      # quiet days say nothing
        shown += 1
        if args.raw:
            for e in sorted(events, key=lambda e: e["t"]):
                print("\t".join(a(e.get(k, "")) for k in ("t", "r", "a", "m", "k", "c", "o", "n", "f", "u")))
        else:
            summarise(day, events)
    if not shown:
        print(f"no downloads recorded in the last {len(days)} day(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
