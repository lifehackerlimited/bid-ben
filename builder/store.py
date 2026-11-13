"""The notices Bid Ben knows about, kept in data/notices.json between runs.

Each run adds what the feeds published since last time, marks tenders that were awarded or cancelled, and drops
ones that closed more than KEEP_DAYS ago. The pages are built from this file alone, so `build` needs no internet.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import feeds, notices

ROOT = Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices.json"
POSTCODES = ROOT / "data" / "postcodes.json"
KEEP_DAYS = 120         # how long a closed tender stays, for the "recently closed" lists


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def load() -> dict:
    data = _read(NOTICES, {})
    data.setdefault("notices", {})
    data.setdefault("fetched_to", "")
    data["notices"] = {nid: n for nid, n in data["notices"].items() if notices.retidy(n)}
    return data


def save(data: dict) -> None:
    _write(NOTICES, data)


def add(data: dict, item: dict, seen: str) -> str:
    """Put one from_release() result into the store. Returns 'new', 'updated', 'ended' or ''."""
    known = data["notices"].get(item["id"])
    if "ended" in item:
        if known and known["status"] == "open" and item["updated"] >= known["updated"]:
            known["status"], known["ended_on"] = item["ended"], seen
            return "ended"
        return ""
    if known and known["updated"] > item["updated"]:
        return ""
    item["first_seen"] = known["first_seen"] if known else seen
    if known and known["status"] != "open" and known.get("ended_on", "") >= item["updated"][:10]:
        item["status"], item["ended_on"] = known["status"], known["ended_on"]
    data["notices"][item["id"]] = item
    return "updated" if known else "new"


def fetch(data: dict, start: dt.date, end: dt.date) -> dict:
    """Pull start..end from both feeds into the store, then work out where each new tender is."""
    counts = {"new": 0, "updated": 0, "ended": 0}
    for src, release in feeds.releases(start, end):
        item = notices.from_release(src, release)
        if item:
            what = add(data, item, (release.get("date") or end.isoformat())[:10])
            if what:
                counts[what] += 1
    cache = _read(POSTCODES, {})
    wanted = {pc for n in data["notices"].values() for pc in n["postcodes"] + [n["buyer_postcode"]]}
    feeds.lookup_postcodes(wanted, cache)
    _write(POSTCODES, cache)
    for n in data["notices"].values():
        notices.locate(n, cache)
    data["fetched_to"] = max(data["fetched_to"], end.isoformat())
    return counts


def prune(data: dict, today: dt.date) -> int:
    """Forget tenders that closed long ago."""
    gone = []
    for nid, n in data["notices"].items():
        a = notices.assess(n, today)
        closed_on = a["deadline"].date() if a["deadline"] else a["published"]
        if not a["open"] and (today - closed_on).days > KEEP_DAYS:
            gone.append(nid)
    for nid in gone:
        del data["notices"][nid]
    return len(gone)
