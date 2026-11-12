"""Turning an official notice into the handful of facts Bid Ben shows, and judging who it suits.

Both feeds (Contracts Finder and Find a Tender) publish in the same OCDS format, with small differences.
from_release() reads either. Everything a page shows about a tender comes from the dict it returns, so the
facts are always the official ones. The judgement ("small-firm fit", which section) is in assess().
"""
from __future__ import annotations

import datetime as dt
import html
import re

from . import places
from .trades import match_trades

DESC_LIMIT = 2400          # characters of the buyer's description kept in the store
OPEN_STAGES = ("tender", "tenderUpdate", "tenderAmendment")
END_STAGES = ("award", "awardUpdate", "contract", "contractUpdate", "tenderCancellation", "implementation")

BUYER_TYPES = (       # first match wins
    ("parish", r"\b(parish|town|community) council\b|\bparish meeting\b"),
    ("school", r"\bschools?\b|\bacadem(y|ies)\b|\bcollege\b|\bmulti.?academy\b|\b(learning|education|academies) "
               r"trust\b|\bmat\b|\bhigh school\b|\bprimary\b|\bsixth form\b"),
    ("university", r"\buniversit"),
    ("housing", r"\bhousing\b|\bhomes\b|\bliving\b|\bhabitat"),
    ("nhs", r"\bnhs\b|\bhospitals?\b|\bhealth(care)?\b|\bintegrated care\b|\bambulance\b"),
    ("council", r"\bcouncil\b|\bborough\b|\bcombined authority\b|\bcounty\b"),
    ("emergency", r"\bpolice\b|\bfire (and|&) rescue\b|\bconstabulary\b"),
)

TUPE = re.compile(r"\bTUPE\b|transfer of undertakings|\bLGPS\b|local government pension|"
                  r"staff (will )?transfer|transferring (staff|employees)", re.I)
POST = re.compile(r"\bby post\b|sealed (envelope|bid|tender)s?|hard cop(y|ies)|paper (bid|tender|submission)", re.I)
SITE_VISIT = re.compile(r"site visits?|site viewing|walk.?round", re.I)
FRAMEWORK_WORDS = re.compile(r"\bframework\b|\bdps\b|dynamic (purchasing|market)|approved (supplier|contractor)s? "
                             r"list|select list", re.I)
CALL_OFF = re.compile(r"call.?off|mini.?competition|further competition", re.I)


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v >= 100 else None      # £0 and £1 are placeholders buyers type to get past the form


def _date(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _clean(text: str | None) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\s*\n\s*", "\n", text)).strip()


def tidy_title(title: str) -> str:
    """'PRO0663 - GROUNDS MAINTENANCE SERVICES' -> 'Grounds Maintenance Services'."""
    t = _clean(title).replace("\n", " ")
    t = re.sub(r"^(?:[A-Za-z]{2,6}\s)?(?=\S*\d)[A-Za-z0-9/_.\-]{2,18}\s*[-–—:~|]\s+", "", t)   # "PRO0663 - ", "ITT 62/2026 - "
    t = re.sub(r"^[A-Z]{2,6}[ -]?\d{4,6}\s+(?=[A-Z])", "", t)                                      # "HBC 1026 Provision..."
    t = re.sub(r"^(itt|rfq|rft|tender|contract|provision|the provision)\s+(for|of)\s+(the\s+)?", "", t, flags=re.I)
    t = re.sub(r"\s*[-–—~|]\s*$", "", t).strip()
    if t and t == t.upper() and len(t) > 6:
        t = t.title()
        t = re.sub(r"\b(Nhs|Uk|Dps|Ha|Mat|Cofe|Ce|Rc|Fm)\b", lambda m: m.group(1).upper(), t)
    return t[:1].upper() + t[1:] if t else _clean(title)


def _cpv(tender: dict) -> list[str]:
    out = []
    c = tender.get("classification") or {}
    if c.get("id"):
        out.append(str(c["id"]))
    for item in tender.get("items") or []:
        c = item.get("classification") or {}
        if c.get("id"):
            out.append(str(c["id"]))
        out += [str(a["id"]) for a in item.get("additionalClassifications") or [] if a.get("id")]
    return sorted(set(out))


def _buyer(release: dict) -> dict:
    buyer_id = (release.get("buyer") or {}).get("id")
    parties = release.get("parties") or []
    for p in parties:
        if p.get("id") == buyer_id or "buyer" in (p.get("roles") or []):
            return p
    return parties[0] if parties else {}


def buyer_type(name: str) -> str:
    low = (name or "").lower()
    for kind, pattern in BUYER_TYPES:
        if re.search(pattern, low):
            return kind
    return "other"


def from_release(src: str, release: dict) -> dict | None:
    """One feed entry -> a notice dict, or a {'id', 'ended'} marker when it says a tender was awarded or
    cancelled, or None when it isn't something we list."""
    tags = release.get("tag") or []
    tender = release.get("tender") or {}
    ocid = release.get("ocid") or release.get("id")
    if not ocid:
        return None
    nid = f"{src}:{ocid}"
    when = release.get("date") or ""
    if any(t in END_STAGES for t in tags) or tender.get("status") in ("cancelled", "withdrawn", "unsuccessful",
                                                                       "complete"):
        return {"id": nid, "ended": "cancelled" if "tenderCancellation" in tags or tender.get("status") in (
            "cancelled", "withdrawn") else "awarded", "updated": when}
    if not any(t in OPEN_STAGES for t in tags) or tender.get("status") not in (None, "active"):
        return None

    title = tidy_title(tender.get("title") or "")
    cpv = _cpv(tender)
    trades = match_trades(tender.get("title") or "", cpv, tender.get("mainProcurementCategory") or "")
    if not trades:
        return None

    # Where the work is.
    codes, postcodes, countries = [], [], set()
    for item in tender.get("items") or []:
        for a in item.get("deliveryAddresses") or []:
            if a.get("region"):
                codes.append(str(a["region"]).strip())
            if a.get("postalCode"):
                postcodes.append(str(a["postalCode"]).strip().upper())
            if a.get("country"):
                countries.add(str(a["country"]).upper())
    if countries and not countries & {"GB", "UK"}:
        return None                     # work abroad (a base in Germany, say)

    buyer = _buyer(release)
    addr = buyer.get("address") or {}
    contact = buyer.get("contactPoint") or {}
    desc = _clean(tender.get("description"))
    lots = []
    for lot in tender.get("lots") or []:
        lots.append({"title": _clean(lot.get("title"))[:120],
                     "value": _num((lot.get("value") or {}).get("amount")) or _num((lot.get("value") or {}).get("amountGross")),
                     "start": ((lot.get("contractPeriod") or {}).get("startDate") or "")[:10],
                     "end": ((lot.get("contractPeriod") or {}).get("endDate") or "")[:10],
                     "max_end": ((lot.get("contractPeriod") or {}).get("maxExtentDate") or "")[:10],
                     "sme": str((lot.get("suitability") or {}).get("sme", "")).lower() == "true"})
    period = tender.get("contractPeriod") or {}
    start = (period.get("startDate") or (lots[0]["start"] if lots else ""))[:10]
    end = (period.get("endDate") or (lots[0]["end"] if lots else ""))[:10]
    max_end = (period.get("maxExtentDate") or (lots[0]["max_end"] if lots else ""))[:10]

    docs = [d for d in tender.get("documents") or [] if d.get("documentType") == "tenderNotice" and d.get("url")]
    docs.sort(key=lambda d: d.get("datePublished") or "")
    if docs:
        url, published = docs[-1]["url"], (docs[0].get("datePublished") or when)
    elif src == "cf":
        url, published = "https://www.contractsfinder.service.gov.uk/Notice/" + str(release.get("id"))[:36], when
    else:
        url, published = "https://www.find-tender.service.gov.uk/Notice/" + str(release.get("id")), when
    published = tender.get("datePublished") or published

    bid_by = (tender.get("tenderPeriod") or {}).get("endDate")
    interest_by = tender.get("expressionOfInterestDeadline")     # staged tenders: the date to ask to take part
    method_text = _clean(tender.get("procurementMethodDetails"))
    techniques = tender.get("techniques") or {}
    is_calloff = bool(CALL_OFF.search(method_text))
    is_framework = (not is_calloff) and bool(
        str(techniques.get("hasFrameworkAgreement", "")).lower() == "true"
        or str(techniques.get("hasDynamicPurchasingSystem", "")).lower() == "true"
        or "dynamic market" in method_text.lower() or FRAMEWORK_WORDS.search(title))
    suit = tender.get("suitability") or {}
    portal = _clean(tender.get("submissionMethodDetails"))
    portal_url = re.search(r"https?://[^\s<>\"']+", portal)

    return {
        "id": nid, "src": src, "url": url, "title": title, "raw_title": _clean(tender.get("title"))[:300],
        "desc": desc[:DESC_LIMIT], "trades": trades, "cpv": cpv[:12],
        "buyer": _clean(buyer.get("name") or (release.get("buyer") or {}).get("name")),
        "buyer_town": _clean(addr.get("locality")).title() if _clean(addr.get("locality")).isupper()
        else _clean(addr.get("locality")),
        "buyer_postcode": _clean(addr.get("postalCode")).upper(), "buyer_code": _clean(addr.get("region")).upper(),
        "codes": sorted(set(codes)), "postcodes": sorted(set(postcodes))[:6],
        "areas": [], "regions": [], "uk_wide": False,       # filled in by locate()
        "value": _num((tender.get("value") or {}).get("amount")) or _num((tender.get("value") or {}).get("amountGross")),
        "lots": lots[:10],
        "published": published[:10], "updated": when, "first_seen": "",
        "deadline": bid_by or interest_by or "", "deadline_kind": "bid" if bid_by else "interest" if interest_by else "",
        "start": start, "end": end, "max_end": max_end,
        "sme": str(suit.get("sme", "")).lower() == "true" or any(lot["sme"] for lot in lots),
        "method": tender.get("procurementMethod") or "", "method_text": method_text,
        "framework": is_framework, "calloff": is_calloff,
        "contact": {k: _clean(contact.get(k)) for k in ("name", "email", "telephone") if contact.get(k)},
        "portal": portal_url.group(0).rstrip(".,)") if portal_url else "",
        "status": "open",
    }


LOCAL_BUYERS = ("parish", "council", "school", "university", "housing", "nhs", "emergency")


def locate(n: dict, postcode_areas: dict[str, str]) -> None:
    """Fill in areas / regions / uk_wide. postcode_areas maps a postcode to an area slug ('' if unknown).

    In order of trust: a specific place of work in the notice; a place named in the title; where the buyer is
    (for local bodies such as councils and schools); then a whole region; then "anywhere in the UK".
    Buyers often tick every region, or leave it at "UK", on a parish hedge-cutting contract, so a vague answer
    is treated as no answer.
    """
    areas, regions, uk = set(), set(), False
    for code in n["codes"]:
        a, r, u = places.locate_code(code)
        areas |= a
        regions |= r
        uk = uk or u
    letters = {c.strip().upper()[2:3] for c in n["codes"] if c.strip().upper().startswith("UK") and len(c.strip()) > 2}
    if len(letters) >= 4 or len(areas) > 6:      # ticked half the country
        areas, regions, uk = set(), set(), True
    for pc in n["postcodes"]:
        if postcode_areas.get(pc):
            areas.add(postcode_areas[pc])

    local = buyer_type(n["buyer"]) in LOCAL_BUYERS
    home, home_region, _ = places.locate_code(n["buyer_code"])
    if postcode_areas.get(n["buyer_postcode"]):
        home = {postcode_areas[n["buyer_postcode"]]}
    if len(home) != 1:
        home = set()
    title_areas, title_regions = places.places_in_title(n.get("raw_title") or n["title"])

    if areas:
        if local and home and len(areas) > 1 and home <= areas:
            areas = set(home)               # "Herefordshire, Worcestershire and Warwickshire" for one primary school
        regions, uk = set(), False
    elif title_areas or title_regions:
        areas, regions, uk = title_areas, (title_regions if not title_areas else set()), False
    elif local and home:
        areas, regions, uk = set(home), set(), False
    elif regions:
        uk = False
    elif not uk and (home or home_region):
        areas, regions = set(home), (home_region if not home else set())
    else:
        uk = True
    n["areas"], n["regions"], n["uk_wide"] = sorted(areas), sorted(regions), uk and not areas and not regions


# ---- judgement ---------------------------------------------------------------------------

def years(n: dict) -> float | None:
    a, b = _date(n.get("start")), _date(n.get("end"))
    if a and b and b > a:
        y = (b - a).days / 365.25
        return y if y >= 0.08 else None
    return None


def assess(n: dict, today: dt.date) -> dict:
    """The judgement calls, worked out fresh each build: who it suits, which section, and what to watch for."""
    text = n["title"] + "\n" + n["desc"]
    kind = buyer_type(n["buyer"])
    yrs = years(n)
    lot_values = [lot["value"] for lot in n["lots"] if lot["value"]]
    split = len(n["lots"]) > 1
    # What one firm would actually take on: the smallest lot if it's split, otherwise the whole thing.
    size = min(lot_values) if split and lot_values else n["value"]
    yearly = size / yrs if size and yrs and yrs >= 1 else None
    deadline = _date(n["deadline"])
    days_left = (deadline.date() - today).days if deadline else None
    start = _date(n.get("start"))
    published = _date(n.get("published")) or dt.datetime.combine(today, dt.time(), dt.timezone.utc)

    flags = []
    if TUPE.search(text):
        flags.append("tupe")
    if POST.search(text):
        flags.append("post")
    if SITE_VISIT.search(text):
        flags.append("site-visit")
    if deadline and start and deadline.date() > start.date():
        flags.append("deadline-after-start")
    elif deadline and (deadline - published).days > 150:
        flags.append("deadline-far")
    if not deadline:
        flags.append("no-deadline")

    if n["calloff"] or n["method"] == "limited":
        section, fit = "list-only", "low"
    elif n["framework"]:
        section, fit = "framework", "medium"
    elif "tupe" in flags or (yearly and yearly > 250_000) or (not yearly and size and size > 750_000):
        section, fit = "large", "low"
    elif (n["value"] or 0) <= 1_500_000 and (
            (kind == "parish" and (size is None or size <= 150_000)) or (yearly and yearly <= 75_000) or (
                not yearly and size and size <= 150_000)):
        section, fit = "best", "high"
    else:
        section, fit = "more", "medium"

    is_open = n["status"] == "open" and (days_left is None or days_left >= 0)
    if days_left is None and (today - published.date()).days > 60:
        is_open = False                 # no deadline given and two months old: assume it has gone
    return {"buyer_type": kind, "years": yrs, "size": size, "yearly": yearly, "split": split, "flags": flags,
            "section": section, "fit": fit, "days_left": days_left, "open": is_open,
            "deadline": deadline, "published": published.date()}
