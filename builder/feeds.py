"""Fetching notices from the two official feeds, and looking up postcodes.

Contracts Finder and Find a Tender both publish every notice as open data (Open Government Licence v3.0), with no
key needed. Find a Tender allows about a dozen requests a couple of minutes, so requests to it are spaced out
and a "slow down" answer is obeyed. A normal daily run asks for the last few days and takes a few minutes.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from . import places

USER_AGENT = os.environ.get("BIDBEN_USER_AGENT") or "Mozilla/5.0 (compatible; BidBen site builder; +https://bidben.betttech.co.uk)"
CF_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
FTS_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
FTS_GAP = 12.5          # seconds between Find a Tender requests
CF_GAP = 0.5
POSTCODES_URL = "https://api.postcodes.io/postcodes"


def say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def get_json(url: str, data: bytes | None = None, tries: int = 7) -> dict:
    """GET (or POST) and parse JSON, waiting and retrying when the server is busy or says to slow down."""
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(url, data=data, headers={
            "User-Agent": USER_AGENT, "Accept": "application/json", **({"Content-Type": "application/json"} if data else {})})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries:
                raise
            wait = min(int(e.headers.get("Retry-After") or 0) or 10 * attempt, 180)
            say(f"  {urllib.parse.urlsplit(url).hostname} answered {e.code}; waiting {wait}s")
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            if attempt == tries:
                raise
            wait = 10 * attempt
            say(f"  {urllib.parse.urlsplit(url).hostname}: {e}; trying again in {wait}s")
        time.sleep(wait)
    raise RuntimeError("unreachable")


def _pages(url: str, gap: float):
    while url:
        page = get_json(url)
        yield from page.get("releases") or []
        url = (page.get("links") or {}).get("next")
        if url:
            time.sleep(gap)


def releases(start: dt.date, end: dt.date):
    """Every notice either feed published or changed from start to end (inclusive), as (source, release)."""
    for day in (start + dt.timedelta(days=i) for i in range((end - start).days + 1)):
        s = day.isoformat()
        counts = {}
        for src, base, params, gap in (
                ("cf", CF_URL, {"publishedFrom": s + "T00:00:00", "publishedTo": s + "T23:59:59", "limit": 100}, CF_GAP),
                ("fts", FTS_URL, {"updatedFrom": s + "T00:00:00", "updatedTo": s + "T23:59:59", "limit": 100}, FTS_GAP)):
            n = 0
            for rel in _pages(base + "?" + urllib.parse.urlencode(params), gap):
                n += 1
                yield src, rel
            counts[src] = n
            time.sleep(gap)
        say(f"{s}: {counts['cf']} Contracts Finder, {counts['fts']} Find a Tender")


def lookup_postcodes(postcodes: set[str], cache: dict[str, str]) -> None:
    """Add any postcodes not yet in the cache: postcode -> area slug, or '' if it isn't a real postcode."""
    todo = sorted(p for p in postcodes if p and p not in cache)
    for i in range(0, len(todo), 100):
        batch = todo[i:i + 100]
        try:
            answer = get_json(POSTCODES_URL, json.dumps({"postcodes": batch}).encode())
        except Exception as e:      # the site still builds; those tenders fall back to the buyer's region
            say(f"  postcode lookup failed ({e}); carrying on without")
            return
        for item in answer.get("result") or []:
            res = item.get("result") or {}
            area = places.area_for_name(res.get("nuts") or "")
            if not area:
                found, _, _ = places.locate_code((res.get("codes") or {}).get("nuts") or "")
                area = sorted(found)[0] if len(found) == 1 else ""
            cache[item.get("query") or ""] = area or ""
        time.sleep(0.3)
