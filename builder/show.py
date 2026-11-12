"""Showing one tender: the wording and HTML shared by the site's pages and the weekly issue.

Facts (dates, values, names, links) are copied from the official notice. "Small-firm fit" and "Our view" are
worked out by notices.assess() from the value, the buyer and the procedure, and say so in the footer.
"""
from __future__ import annotations

import datetime as dt
import html
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from . import places

LONDON = ZoneInfo("Europe/London")
E = html.escape

FIT_LABEL = {"high": "Small-firm fit: high", "medium": "Small-firm fit: medium", "low": "Small-firm fit: low"}
SECTIONS = {       # key -> (heading, the line under it)
    "best": ("Best for small firms",
             "Modest value, open to any firm, and buyers who usually just want a reliable local contractor."),
    "more": ("Worth a look if you have a bit more capacity",
             "Bigger, spread over several sites, or the value isn't stated. Still within reach of a well-run firm."),
    "large": ("Large contracts: expect TUPE and pension costs",
              "Worth it if you've run contracts this size before. Price any inherited staff carefully: it's where "
              "most bids go wrong."),
    "framework": ("Frameworks and supplier lists",
                  "A framework doesn't guarantee any work. Joining puts you on a shortlist the buyer calls on for "
                  "several years."),
    "list-only": ("Only for firms already on a supplier list",
                  "Call-offs open only to firms already approved. Listed so you can see how much work flows "
                  "through each list."),
}
SECTION_ORDER = list(SECTIONS)


def money(v: float) -> str:
    if v >= 1_000_000:
        return "£" + f"{v / 1_000_000:.2f}".rstrip("0").rstrip(".") + "m"
    return f"£{v:,.0f}"


def rough(v: float) -> str:
    return money(v) if v >= 1_000_000 else f"£{max(1, round(v / 1000)):,}k"


def years_text(y: float) -> str:
    if y < 0.95:
        months = max(1, round(y * 12))
        return f"{months} month{'s' if months != 1 else ''}"
    halves = round(y * 2)
    whole, half = divmod(halves, 2)
    return f"{whole}½ years" if half else f"{whole} year{'s' if whole != 1 else ''}"


def value_text(n: dict, a: dict) -> str:
    lot_values = sorted(lot["value"] for lot in n["lots"] if lot["value"])
    if a["split"] and len(lot_values) >= 2:
        text = (f"{len(n['lots'])} lots of {money(lot_values[0])} each" if lot_values[0] == lot_values[-1]
                else f"{len(n['lots'])} lots, from {money(lot_values[0])} to {money(lot_values[-1])}")
        per_year = "smallest lot about {} a year"
    elif n["value"]:
        text, per_year = money(n["value"]), "about {} a year"
    else:
        return "not stated"
    if a["years"]:
        text += f" over {years_text(a['years'])}"
        if a["yearly"] and a["years"] >= 1.5:
            text += f" ({per_year.format(rough(a['yearly']))})"
    return text


def when_text(d: dt.datetime, today: dt.date) -> str:
    local = d.astimezone(LONDON)
    year = f" {local.year}" if local.year != today.year and abs((local.date() - today).days) > 180 else ""
    clock = "" if (local.hour, local.minute) in ((0, 0), (23, 59)) else f", {local:%H:%M}"
    return f"{local:%a} {local.day} {local:%b}{year}{clock}"


def day_text(d: dt.date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def deadline_html(n: dict, a: dict, today: dt.date, tag: str = "span", label: bool = True, static: bool = False) -> str:
    """The deadline, with a hook for the page's script to add "(5 days left)". static=True writes the days in,
    for email, where scripts don't run."""
    d = a["deadline"]
    name = "Ask to take part by" if n.get("deadline_kind") == "interest" else "Deadline"
    lead = f"<b>{name}:</b> " if label else ("Ask to take part by " if n.get("deadline_kind") == "interest" else "")
    if not d:
        return f"<{tag}>{lead}not given: check the notice</{tag}>"
    left = ""
    if static and a["days_left"] is not None:
        days = a["days_left"]
        left = " (closed)" if days < 0 else " (today)" if days == 0 else " (tomorrow)" if days == 1 else f" ({days} days)"
    return (f'<{tag} data-deadline="{E(d.isoformat())}">{lead}{E(when_text(d, today))}'
            f'<span class="left">{left}</span></{tag}>')


def place_text(n: dict, a: dict) -> str:
    names = [places.AREAS[s]["name"] for s in n["areas"]]
    if names:
        place = ", ".join(names[:3]) + (" and more" if len(names) > 3 else "")
    elif n["regions"]:
        place = " and ".join(places.REGIONS[r] for r in n["regions"])
    else:
        return "UK-wide, or the place isn't stated"
    town = n["buyer_town"]
    if town and len(names) == 1 and a["buyer_type"] != "other" and town.lower() not in place.lower() \
            and place.lower() not in town.lower():
        place = f"{town}, {place}"
    return place


def excerpt(text: str, limit: int = 320) -> str:
    """The first sentence or two of the buyer's description."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("; "))
    return (cut[:stop + 1] if stop > limit * 0.45 else cut.rsplit(" ", 1)[0] + "…").strip()


def view(n: dict, a: dict) -> tuple[str, str]:
    """('Our view' or 'Watch out', the sentence or two). Automatic, and worded to say only what the data shows."""
    said = []
    warn = False
    section = a["section"]
    if section == "list-only":
        said.append("Only firms already on this buyer's supplier list can bid.")
    elif section == "framework":
        said.append("This sets up a framework or supplier list. A place on it doesn't guarantee work, but it's how "
                    "this buyer will hand out jobs for the next few years.")
    elif section == "best":
        if a["buyer_type"] == "parish":
            said.append("A parish or town council job of modest size. These usually skip the long questionnaires, "
                        "which makes them a good first public contract.")
        elif a["split"]:
            said.append("Split into lots, so you can bid for one area or one part of the work.")
        else:
            said.append("Modest value and open to any firm.")
    elif section == "more":
        said.append("The value isn't stated, so ask before you spend time on it." if not a["size"] else
                    "A mid-sized contract, within reach of a well-run firm with the staff to cover it.")
    else:
        said.append("A large contract. Expect a full tender pack with scored written answers.")
    flags = a["flags"]
    if "tupe" in flags:
        warn = True
        said.append("The notice mentions staff transferring to the winner (TUPE) or a pension scheme, so price the "
                    "inherited wages and pension costs before anything else.")
    if "deadline-after-start" in flags:
        warn = True
        said.append("The listed deadline is after the contract's start date, so one of them is probably wrong. "
                    "Check the portal for the real date.")
    elif "deadline-far" in flags:
        warn = True
        said.append("The listed deadline is months away. Staged tenders often have an earlier first step, so check "
                    "the portal.")
    if "post" in flags:
        said.append("Bids may have to arrive on paper, so leave time for the post.")
    if "site-visit" in flags:
        said.append("The notice mentions a site visit: check the date.")
    low = n["method_text"].lower()
    if section in ("best", "more", "large") and ("competitive flexible" in low or n["method"] == "selective"):
        said.append("It's a staged process, usually starting with a short questionnaire.")
    return ("Watch out" if warn else "Our view"), " ".join(said)


def how(n: dict) -> str:
    bits = []
    if n["portal"]:
        host = (urlsplit(n["portal"]).hostname or "the buyer's portal").removeprefix("www.")
        bits.append(f'through <a href="{E(n["portal"])}" rel="nofollow noopener">{E(host)}</a>')
    c = n["contact"]
    who = [E(c["name"])] if c.get("name") else []
    if c.get("email"):
        who.append(f'<a href="mailto:{E(c["email"])}">{E(c["email"])}</a>')
    if c.get("telephone"):
        who.append(E(c["telephone"]))
    if who:
        bits.append("contact " + ", ".join(who))
    return "How to bid: " + ("; ".join(bits) if bits else "see the official notice") + "."


def fit_badge(a: dict) -> str:
    if not a["open"]:
        return '<span class="fit closed">Closed</span>'
    return f'<span class="fit {a["fit"]}">{FIT_LABEL[a["fit"]]}</span>'


def card(n: dict, a: dict, today: dt.date, static: bool = False) -> str:
    label, said = view(n, a)
    facts = [f"<span><b>Value:</b> {E(value_text(n, a))}</span>", deadline_html(n, a, today, static=static)]
    if n["sme"]:
        facts.append("<span><b>Marked suitable for small firms</b></span>")
    text = excerpt(n["desc"])
    return (f'<div class="card{"" if a["open"] else " shut"}">\n'
            f'  <h3><a href="{E(n["url"])}" rel="noopener">{E(n["title"])}</a> {fit_badge(a)}</h3>\n'
            f'  <p class="who">{E(n["buyer"])} · {E(place_text(n, a))}</p>\n'
            f'  <div class="facts">{"".join(facts)}</div>\n'
            + (f"  <p>{E(text)}</p>\n" if text else "")
            + f'  <div class="view"><b>{label}:</b> {E(said)}</div>\n'
            f'  <p class="how">{how(n)}</p>\n</div>\n')


def row(n: dict, a: dict, today: dt.date, static: bool = False, note: bool = True) -> str:
    """One line of a compact table: tender, value, deadline."""
    label, said = view(n, a)
    small = f"{E(n['buyer'])} · {E(place_text(n, a))}"
    if note and (label == "Watch out" or a["section"] in ("framework", "list-only")):
        small += f" · {E(said)}"
    shut = "" if a["open"] else ' class="shut"'
    return (f'<tr{shut}><td><a href="{E(n["url"])}" rel="noopener">{E(n["title"])}</a>'
            f'<br><small>{small}</small></td><td>{E(value_text(n, a))}</td>'
            f'{deadline_html(n, a, today, tag="td", label=False, static=static)}</tr>\n')


def table(rows: str, first: str = "Tender", cls: str = "list") -> str:
    cls_attr = f' class="{cls}"' if cls else ""
    return f"<table{cls_attr}>\n<tr><th>{first}</th><th>Value</th><th>Deadline</th></tr>\n{rows}</table>\n"


def by_deadline(items: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
    """Soonest deadline first; ones with no date last."""
    far = dt.datetime.max.replace(tzinfo=dt.timezone.utc)
    return sorted(items, key=lambda na: (na[1]["deadline"] or far, na[0]["title"]))


def unique(items: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
    """The same tender is often on both feeds, or re-published. Keep one: the latest, preferring Find a Tender."""
    best: dict[tuple, tuple[dict, dict]] = {}
    for n, a in items:
        key = (re.sub(r"\W+", " ", n["title"].lower()).strip(), re.sub(r"\W+", " ", n["buyer"].lower()).strip())
        old = best.get(key)
        if not old or (n["src"] == "fts", n["updated"]) > (old[0]["src"] == "fts", old[0]["updated"]):
            best[key] = (n, a)
    return list(best.values())
