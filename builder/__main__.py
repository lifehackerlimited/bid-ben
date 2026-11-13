"""Build the Bid Ben site.

    python -m builder all            what the daily job runs: fetch the last few days, then rebuild every page
    python -m builder fetch          only fetch new notices into data/notices.json   (--days 4, or --from/--to dates)
    python -m builder build          only rebuild the pages from data/notices.json   (no internet needed)
    python -m builder issue          only (re)build this week's issue                (--date 2026-11-16 for another)
    python -m builder status         how many tenders are in the store, by trade

Run it from the repository's top folder. Python standard library only.
"""
from __future__ import annotations

import datetime as dt
import sys

from . import store


def _arg(args: list[str], name: str, default: str | None = None) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default


def _today(args: list[str]) -> dt.date:
    return dt.date.fromisoformat(_arg(args, "--today") or dt.date.today().isoformat())


def cmd_fetch(args: list[str]) -> None:
    today = _today(args)
    end = dt.date.fromisoformat(_arg(args, "--to") or today.isoformat())
    data = store.load()
    if _arg(args, "--from"):
        start = dt.date.fromisoformat(_arg(args, "--from"))
    else:
        start = end - dt.timedelta(days=int(_arg(args, "--days", "4")) - 1)
        if data["fetched_to"]:          # missed some days? Catch up from the last one fetched (three weeks at most)
            start = max(min(start, dt.date.fromisoformat(data["fetched_to"])), end - dt.timedelta(days=21))
    counts = {"new": 0, "updated": 0, "ended": 0}
    for day in (start + dt.timedelta(days=i) for i in range((end - start).days + 1)):
        for what, n in store.fetch(data, day, day).items():
            counts[what] += n
        store.save(data)            # after every day, so a long first run that's cut short loses nothing
    dropped = store.prune(data, today)
    store.save(data)
    print(f"Fetched {start} to {end}: {counts['new']} new, {counts['updated']} updated, {counts['ended']} awarded or "
          f"cancelled, {dropped} old ones dropped. {len(data['notices'])} in the store.")


def cmd_build(args: list[str]) -> None:
    from . import site
    today = _today(args)
    made = site.build(store.load(), today)
    print(f"Built {made['pages']} pages ({made['open']} open tenders, {made['indexed']} pages in the sitemap).")


def cmd_issue(args: list[str]) -> None:
    from . import issue
    today = _today(args)
    monday = dt.date.fromisoformat(_arg(args, "--date")) if _arg(args, "--date") else issue.this_monday(today)
    info = issue.build(store.load(), monday, today, force="--force" in args)
    print(f"Issue for {monday}: {info['count']} tenders. {info['note']}")


def cmd_all(args: list[str]) -> None:
    from . import issue
    cmd_fetch(args)
    today = _today(args)
    if issue.due(today):
        cmd_issue(args)
    cmd_build(args)


def cmd_status(args: list[str]) -> None:
    from collections import Counter
    from . import notices
    today = _today(args)
    data = store.load()
    by = Counter()
    for n in data["notices"].values():
        a = notices.assess(n, today)
        for t in n["trades"]:
            by[(t, "open" if a["open"] else "closed")] += 1
    print(f"{len(data['notices'])} tenders in the store, fetched up to {data['fetched_to'] or 'never'}.")
    for (trade, state), count in sorted(by.items()):
        print(f"  {trade:22} {state:7} {count}")


COMMANDS = {"all": cmd_all, "fetch": cmd_fetch, "build": cmd_build, "issue": cmd_issue, "status": cmd_status}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__.strip())
        sys.exit(0 if len(sys.argv) < 2 else 2)
    COMMANDS[sys.argv[1]](sys.argv[2:])
