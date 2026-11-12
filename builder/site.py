"""Every page of the Bid Ben site, built from the store.

    /                               home: what it is, the sign-up box, what's open now
    /tenders/                       every open tender
    /tenders/<trade>/               one trade across the UK
    /tenders/<trade>/<area>/        one trade in one county   (the pages firms find by searching)
    /areas/<area>/                  one county, all trades
    /issues/ and /issues/<date>/    the Monday issues          (written by issue.py)
    /signup/, /privacy/, 404.html, sitemap.xml, robots.txt, status.json

A county page with nothing local to show is still built, so every link works and people can sign up to be told,
but it's marked "noindex" and left out of the sitemap until it has something on it.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import notices, places, show
from .settings import COMPANY, CONTACT_EMAIL, FORM_ACTION, OFFICE, PRICE, RECENT_DAYS, SITE, TRIAL_WEEKS
from .show import E
from .trades import ORDER, TRADES

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "pages.json"


# ---- the frame every page sits in ------------------------------------------------------------

def page(path: str, title: str, description: str, body: str, *, hero: str = "", noindex: bool = False) -> str:
    robots = '<meta name="robots" content="noindex,follow">\n' if noindex else ""
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(description)}">
{robots}<link rel="canonical" href="{SITE}{path}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/site.css">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Bid Ben">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(description)}">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:image" content="{SITE}/assets/share.png">
<meta name="twitter:card" content="summary_large_image">
</head>
<body>
<a class="skip" href="#main">Skip to the content</a>
<header class="top"><div class="wrap">
  <a class="logo" href="/"><img src="/bid-ben-logo-reversed.svg" width="150" height="54" alt="Bid Ben: home"></a>
  <nav aria-label="Main">
    <a href="/tenders/">Open tenders</a>
    <a href="/issues/">The Monday issue</a>
    <a class="go" href="/signup/">Sign up free</a>
  </nav>
</div></header>
{hero}<main id="main"><div class="wrap">
{body}
</div></main>
<footer class="foot"><div class="wrap">
  <p class="brand"><b>Bid <span>Ben</span></b> · public contracts, on the dot, every Monday</p>
  <nav aria-label="Footer"><a href="/tenders/">Open tenders</a><a href="/issues/">Past issues</a><a href="/signup/">Sign up</a><a href="/privacy/">Privacy</a><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></nav>
  <p><b>Information only.</b> We summarise official notices to help you decide what's worth your time. Always read the full notice and the buyer's tender documents before bidding: they take precedence over anything here. Dates, values and contacts are copied from the official notices. "Small-firm fit" and "Our view" are worked out automatically from the value, the buyer and the procedure, so treat them as a guide.</p>
  <p>Contains public sector information licensed under the <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">Open Government Licence v3.0</a>. Sources: Contracts Finder and Find a Tender. Area names and codes: Office for National Statistics.</p>
  <p>Bid Ben is run by {COMPANY}. Registered office: {OFFICE}.</p>
</div></footer>
<script src="/assets/site.js" defer></script>
</body>
</html>
"""


def signup_box(heading: str = "", pitch: str = "", trade: str = "", area: str = "", anchor: str = "signup") -> str:
    heading = heading or "Get the new ones every Monday"
    pitch = pitch or ("One email a week with every new tender in your trade, explained in plain English, with the "
                      "ones near you at the top.")
    options = '<option value="">Any of them</option>' + "".join(
        f'<option value="{slug}"{" selected" if slug == trade else ""}>{E(TRADES[slug]["name"])}</option>'
        for slug in ORDER)
    return f"""<section class="signup" id="{anchor}" aria-label="Sign up">
  <h2>{E(heading)}</h2>
  <p>{E(pitch)}</p>
  <form class="js-signup" action="{FORM_ACTION}" method="POST" data-fallback="{CONTACT_EMAIL}">
    <label class="full">Your email <input type="email" name="email" autocomplete="email" required placeholder="you@yourfirm.co.uk"></label>
    <label>Areas you cover <span>(optional)</span> <input type="text" name="areas" value="{E(area)}" placeholder="e.g. Kent, East Sussex"></label>
    <label>Your trade <span>(optional)</span> <select name="trade">{options}</select></label>
    <label class="full">Company <span>(optional)</span> <input type="text" name="company" autocomplete="organization"></label>
    <div class="hp" aria-hidden="true"><label>Leave this empty <input type="text" name="_gotcha" tabindex="-1" autocomplete="off"></label></div>
    <input type="hidden" name="_subject" value="Bid Ben sign-up">
    <input type="hidden" name="page" value="">
    <button type="submit">Start my {TRIAL_WEEKS} free weeks</button>
    <p class="status" role="status" aria-live="polite"></p>
    <p class="small">Free for {TRIAL_WEEKS} weeks. After that it's {PRICE}, and only if you say yes. No card needed, and you can stop any time by replying "unsubscribe". <a href="/privacy/">How we use your details</a>.</p>
  </form>
</section>
"""


def plural(n: int, one: str, many: str = "") -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def chips(links: list[tuple[str, str, int]]) -> str:
    """[(href, label, count)] -> a row of pill links. Ones with nothing in them are shown quieter."""
    out = []
    for href, label, count in links:
        quiet = "" if count else ' class="none"'
        number = f" <span>{count}</span>" if count else ""
        out.append(f'<li><a href="{href}"{quiet}>{E(label)}{number}</a></li>')
    return '<ul class="chips">' + "".join(out) + "</ul>\n"


# ---- gathering -----------------------------------------------------------------------------

class Board:
    """Every tender in the store with its assessment, and the questions the pages ask of them."""

    def __init__(self, data: dict, today: dt.date):
        self.today = today
        everything = [(n, notices.assess(n, today)) for n in data["notices"].values()]
        self.open = show.by_deadline(show.unique([na for na in everything if na[1]["open"]]))
        cutoff = today - dt.timedelta(days=RECENT_DAYS)
        closed = [na for na in everything if not na[1]["open"]
                  and (na[1]["deadline"].date() if na[1]["deadline"] else na[1]["published"]) >= cutoff]
        self.closed = sorted(show.unique(closed), key=lambda na: (
            na[1]["deadline"].date() if na[1]["deadline"] else na[1]["published"]), reverse=True)

    @staticmethod
    def _pick(items, trade: str = "", area: str = "", region: str = "", uk: bool = False):
        out = []
        for n, a in items:
            if trade and trade not in n["trades"]:
                continue
            if area and area not in n["areas"]:
                continue
            if region and region not in n["regions"]:
                continue
            if uk and not n["uk_wide"]:
                continue
            out.append((n, a))
        return out

    def open_in(self, trade: str = "", area: str = "") -> list:
        return self._pick(self.open, trade, area)

    def closed_in(self, trade: str = "", area: str = "") -> list:
        return self._pick(self.closed, trade, area)

    def wider(self, trade: str, area: str) -> list:
        """Open tenders for a whole region or the whole UK, which may include this area."""
        region = places.AREAS[area]["region"]
        return self._pick(self.open, trade, region=region) + self._pick(self.open, trade, uk=True)

    def new_this_week(self) -> list:
        week = self.today - dt.timedelta(days=7)
        return [na for na in self.open if na[1]["published"] >= week]

    def closing_soon(self, days: int = 7) -> list:
        return [na for na in self.open if na[1]["days_left"] is not None and na[1]["days_left"] <= days]


def cards_then_table(items: list, today: dt.date, max_cards: int = 8) -> str:
    """The small-firm ones as full cards, the rest as a compact table, each kind under its own heading."""
    out = []
    for key in show.SECTION_ORDER:
        group = [na for na in items if na[1]["section"] == key]
        if not group:
            continue
        heading, lede = show.SECTIONS[key]
        out.append(f"<h2>{E(heading)}</h2>\n<p class=\"lede\">{E(lede)}</p>\n")
        if key == "best":
            out.append("".join(show.card(n, a, today) for n, a in group[:max_cards]))
            group = group[max_cards:]
        if group:
            out.append(show.table("".join(show.row(n, a, today) for n, a in group),
                                  "Framework" if key == "framework" else "Tender"))
    return "".join(out)


# ---- the pages -----------------------------------------------------------------------------

def home(board: Board, latest_issue: dict | None) -> str:
    today = board.today
    best = [na for na in board.open if na[1]["section"] == "best" and (na[1]["days_left"] or 99) >= 3][:4]
    hero = f"""<section class="hero"><div class="wrap">
  <div>
    <p class="kicker">Cleaning · grounds · trees · pest control</p>
    <h1>Public contracts a small firm can actually win</h1>
    <p>Bid Ben reads every new council, school and housing association tender in your trade, and tells you in plain English which are worth your time.</p>
    <ul>
      <li>The real deadline, even when the official notice gets it wrong</li>
      <li>What would change your price, such as staff transferring to you</li>
      <li>Which ones suit a small firm, and which to leave alone</li>
    </ul>
  </div>
  {signup_box("One email, every Monday", "Every new tender in your trade, with the ones near you at the top. The first " + TRIAL_WEEKS + " weeks are free.")}
</div></section>
"""
    trades = "".join(
        f'<a href="/tenders/{slug}/"><b>{E(TRADES[slug]["name"])}</b>'
        f'<span>{plural(len(board.open_in(slug)), "open tender")} · {E(TRADES[slug]["blurb"])}</span></a>'
        for slug in ORDER)
    issue_line = ""
    if latest_issue:
        issue_line = (f'<h2>This week\'s issue</h2>\n<p class="lede">Out {E(latest_issue["day_text"])}. '
                      f'<a href="/issues/{latest_issue["date"]}/">{E(latest_issue["title"])}</a>: every one sorted by '
                      f'who it suits. <a href="/issues/">Past issues</a>.</p>\n')
    body = f"""<div class="stats">
  <div class="stat"><b>{len(board.open)}</b><span>tenders open right now</span></div>
  <div class="stat"><b>{len(board.new_this_week())}</b><span>new in the last 7 days</span></div>
  <div class="stat"><b>{len(board.closing_soon())}</b><span>closing in the next 7 days</span></div>
</div>
<p class="lede">Checked every day against Contracts Finder and Find a Tender, the two official sources. <span data-checked></span></p>
{issue_line}<h2>Open tenders by trade</h2>
<div class="trades">{trades}</div>
<h2>Open tenders by county</h2>
{area_columns(board)}
<h2>Good ones for a small firm, open now</h2>
<p class="lede">A few of the {len([1 for _, a in board.open if a["section"] == "best"])} open tenders we rate a high fit for a small firm. <a href="/tenders/">See all {len(board.open)}</a>.</p>
{"".join(show.card(n, a, today) for n, a in best) or '<p class="empty">Nothing in this group today. New notices appear most weekdays.</p>'}
<h2>How it works</h2>
<ul class="steps">
  <li><b>1. We read every notice</b>Councils, schools, housing associations and the NHS must publish their contracts. We check both official sites every day.</li>
  <li><b>2. We sort and explain</b>Each tender gets the value, the real deadline, who it suits, and anything that changes your price.</li>
  <li><b>3. You get one email on Monday</b>The week's new tenders, with your areas first. {TRIAL_WEEKS.capitalize()} weeks free, then {PRICE} if you want to keep it.</li>
</ul>
"""
    return page("/", "Bid Ben: public cleaning and grounds contracts small firms can win",
                "Open council, school and housing association tenders for cleaning, window cleaning, grounds "
                "maintenance, tree work and pest control, explained in plain English. Free weekly email.",
                body, hero=hero)


def area_columns(board: Board, trade: str = "") -> str:
    """Every county, grouped by region, with how many tenders are open there."""
    out = []
    for region, region_name in places.REGIONS.items():
        slugs = places.areas_in_region(region)
        items = []
        for slug in sorted(slugs, key=lambda s: places.AREAS[s]["name"]):
            count = len(board.open_in(trade, slug))
            href = f"/tenders/{trade}/{slug}/" if trade else f"/areas/{slug}/"
            items.append(f'<li><a href="{href}">{E(places.AREAS[slug]["name"])}</a>'
                         + (f" <span>{count}</span>" if count else "") + "</li>")
        out.append(f'<p class="region">{E(region_name)}</p>\n<ul class="cols">{"".join(items)}</ul>\n')
    return "".join(out)


def tenders_index(board: Board) -> str:
    today = board.today
    rows = "".join(show.row(n, a, today) for n, a in board.open)
    trades = [(f"/tenders/{slug}/", TRADES[slug]["name"], len(board.open_in(slug))) for slug in ORDER]
    body = f"""<p class="crumbs"><a href="/">Bid Ben</a> › Open tenders</p>
<h1>Open public tenders for cleaning and grounds firms</h1>
<p class="lede">{plural(len(board.open), "tender")} open across the UK, soonest deadline first. Each links to the official notice. <span data-checked></span></p>
{chips(trades)}
<h2>Every open tender</h2>
{show.table(rows) if rows else '<p class="empty">Nothing open today.</p>'}
<h2>By county</h2>
{area_columns(board)}
{signup_box()}"""
    return page("/tenders/", "Open public tenders for cleaning and grounds firms | Bid Ben",
                f"All {len(board.open)} open public-sector tenders for cleaning, window cleaning, grounds "
                "maintenance, tree work and pest control across the UK, updated daily.", body)


def trade_page(board: Board, trade: str) -> str:
    t = TRADES[trade]
    items = board.open_in(trade)
    body = f"""<p class="crumbs"><a href="/">Bid Ben</a> › <a href="/tenders/">Open tenders</a> › {E(t["name"])}</p>
<h1>{E(t["name"])} tenders</h1>
<p class="lede">{plural(len(items), "open public contract")} across the UK for {E(t["noun"])} firms. {E(t["blurb"])} <span data-checked></span></p>
{cards_then_table(items, board.today, max_cards=6) or f'<p class="empty">No open {E(t["noun"])} tenders today. New notices appear most weekdays.</p>'}
<h2>{E(t["name"])} tenders by county</h2>
{area_columns(board, trade)}
{signup_box(f"Get new {t['noun']} tenders every Monday", trade=trade)}"""
    return page(f"/tenders/{trade}/", f"{t['name']} tenders: open public contracts across the UK | Bid Ben",
                f"{plural(len(items), 'open public-sector ' + t['noun'] + ' tender')} from councils, schools and "
                "housing associations, sorted by which suit a small firm. Updated daily.", body)


def trade_area_page(board: Board, trade: str, area: str) -> tuple[str, bool]:
    """Returns (html, has_content). has_content is whether there's anything local, open or recently closed."""
    t, place = TRADES[trade], places.AREAS[area]
    today = board.today
    local = board.open_in(trade, area)
    closed = board.closed_in(trade, area)[:8]
    wider = [na for na in board.wider(trade, area) if na not in local]
    region_name = places.REGIONS[place["region"]]
    parts = [f'<p class="crumbs"><a href="/">Bid Ben</a> › <a href="/tenders/">Open tenders</a> › '
             f'<a href="/tenders/{trade}/">{E(t["name"])}</a> › {E(place["name"])}</p>\n'
             f'<h1>{E(t["name"])} tenders in {E(place["name"])}</h1>\n']
    if local:
        parts.append(f'<p class="lede">{plural(len(local), "public contract")} open now for {E(t["noun"])} firms in '
                     f'{E(place["name"])}. Each links to the official notice. <span data-checked></span></p>\n')
        parts.append(cards_then_table(local, today))
    else:
        last = ""
        if closed:
            n, a = closed[0]
            when = a["deadline"].date() if a["deadline"] else a["published"]
            last = f" The most recent one, from {E(n['buyer'])}, closed on {show.day_text(when)}."
        parts.append(f'<p class="empty">No {E(t["noun"])} tenders are open in {E(place["name"])} today.{last} '
                     f'We check both official sites every day: leave your email below and the next one comes to you. '
                     f'<span data-checked></span></p>\n')
    parts.append(signup_box(f"Get {place['name']} {t['noun']} tenders by email",
                            f"Every new {t['noun']} tender in {place['name']} and nearby, each Monday, in plain English.",
                            trade=trade, area=place["name"]))
    if wider:
        parts.append(f'<h2>Wider contracts that may include {E(place["name"])}</h2>\n<p class="lede">The buyer gave '
                     f'only a region ({E(region_name)}) or the whole UK as the place of work.</p>\n'
                     + show.table("".join(show.row(n, a, today) for n, a in wider[:12])))
    if closed:
        parts.append(f'<h2>Recently closed in {E(place["name"])}</h2>\n<p class="lede">Too late for these, but they '
                     f'show who buys {E(t["noun"])} here and what they pay. Contracts like these come round again.</p>\n'
                     + show.table("".join(show.row(n, a, today, note=False) for n, a in closed)))
    nearby = [(f"/tenders/{trade}/{slug}/", places.AREAS[slug]["name"], len(board.open_in(trade, slug)))
              for slug in sorted(places.areas_in_region(place["region"])) if slug != area]
    if nearby:
        parts.append(f'<h2>{E(t["name"])} tenders nearby</h2>\n' + chips(nearby))
    others = [(f"/tenders/{slug}/{area}/", TRADES[slug]["name"], len(board.open_in(slug, area)))
              for slug in ORDER if slug != trade]
    parts.append(f'<h2>Other trades in {E(place["name"])}</h2>\n' + chips(others))
    has_content = bool(local or closed)
    title = f"{t['name']} tenders in {place['name']} | Bid Ben"
    desc = (f"{plural(len(local), 'open public-sector ' + t['noun'] + ' tender')} in {place['name']}, with values, "
            "real deadlines and which suit a small firm. Checked daily against the official notices."
            if local else f"Public-sector {t['noun']} tenders in {place['name']}: recent contracts, who buys, and a "
                          "free email when the next one is published.")
    return page(f"/tenders/{trade}/{area}/", title, desc, "".join(parts), noindex=not has_content), has_content


def area_page(board: Board, area: str) -> tuple[str, bool]:
    place = places.AREAS[area]
    today = board.today
    local = board.open_in(area=area)
    closed = board.closed_in(area=area)[:10]
    parts = [f'<p class="crumbs"><a href="/">Bid Ben</a> › <a href="/tenders/">Open tenders</a> › {E(place["name"])}</p>\n'
             f'<h1>Public tenders in {E(place["name"])} for cleaning and grounds firms</h1>\n']
    trades = [(f"/tenders/{slug}/{area}/", TRADES[slug]["name"], len(board.open_in(slug, area))) for slug in ORDER]
    if local:
        parts.append(f'<p class="lede">{plural(len(local), "public contract")} open now in {E(place["name"])}. '
                     f'<span data-checked></span></p>\n' + chips(trades) + cards_then_table(local, today))
    else:
        parts.append(f'<p class="empty">Nothing is open in {E(place["name"])} today in the trades we cover. We check '
                     f'both official sites every day: leave your email below and the next one comes to you. '
                     f'<span data-checked></span></p>\n' + chips(trades))
    parts.append(signup_box(f"Get {place['name']} tenders by email",
                            f"Every new tender in {place['name']} and nearby, each Monday, in plain English.",
                            area=place["name"]))
    if closed:
        parts.append(f'<h2>Recently closed in {E(place["name"])}</h2>\n<p class="lede">Too late for these, but they '
                     'show who buys here and what they pay.</p>\n'
                     + show.table("".join(show.row(n, a, today, note=False) for n, a in closed)))
    nearby = [(f"/areas/{slug}/", places.AREAS[slug]["name"], len(board.open_in(area=slug)))
              for slug in sorted(places.areas_in_region(place["region"])) if slug != area]
    if nearby:
        parts.append("<h2>Nearby</h2>\n" + chips(nearby))
    has_content = bool(local or closed)
    desc = (f"{plural(len(local), 'open public-sector tender')} in {place['name']} for cleaning, grounds, tree and "
            "pest control firms, with values and real deadlines. Checked daily.")
    return page(f"/areas/{area}/", f"Public tenders in {place['name']} for cleaning and grounds firms | Bid Ben",
                desc, "".join(parts), noindex=not has_content), has_content


def signup_page() -> str:
    body = f"""<p class="crumbs"><a href="/">Bid Ben</a> › Sign up</p>
<h1>Get Bid Ben every Monday</h1>
<p class="lede">One email a week with every new public tender in your trade, explained in plain English.</p>
{signup_box("Start your free weeks", "Tell us where you work and we'll put those tenders at the top.")}
<h2>What you get</h2>
<ul class="steps">
  <li><b>Every relevant tender</b>From Contracts Finder and Find a Tender, the two official sites, so you don't have to search either.</li>
  <li><b>Plain English</b>The value, how long it runs, the real deadline, and how to bid.</li>
  <li><b>What changes your price</b>Staff who would transfer to you, pension costs, paper-only bids, site visits.</li>
</ul>
<h2>What it costs</h2>
<p>The first {TRIAL_WEEKS} weeks are free, with no card. Then we ask whether it was worth it. If you want to keep it, it's {PRICE}. If you don't, you owe nothing and the emails stop.</p>
<p>See what it looks like: <a href="/issues/">past issues</a>.</p>"""
    return page("/signup/", "Sign up to Bid Ben: public tenders for small firms, every Monday",
                "A free weekly email of public-sector cleaning, grounds, tree work and pest control tenders, "
                "explained in plain English. Four weeks free, no card.", body)


def privacy_page() -> str:
    body = f"""<p class="crumbs"><a href="/">Bid Ben</a> › Privacy</p>
<h1>How we use your details</h1>
<p class="lede">The short version: we use your email to send you Bid Ben, and for nothing else.</p>
<h2>Who we are</h2>
<p>Bid Ben is run by {COMPANY}, registered office {OFFICE}. We are the controller of the information described here. Contact us at <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
<h2>What we collect, and why</h2>
<p>When you sign up we collect your email address and, if you give them, your company name, your trade and the areas you cover. We use them to send you the weekly email and to put the tenders nearest you first. Our lawful basis is your consent, which you give by signing up and can withdraw at any time.</p>
<p>Our form provider, Formspree, processes the sign-up form and passes it to us by email. The weekly emails are sent from our own mailbox.</p>
<h2>What we don't do</h2>
<p>We don't sell or share your details, and we don't add you to any other list. This site sets no cookies and has no advertising or tracking scripts.</p>
<h2>Stopping, and your rights</h2>
<p>Reply "unsubscribe" to any email, or write to <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>, and we'll stop and delete your details. Otherwise we keep them for as long as you're subscribed, and for up to a year after a free trial ends in case you come back. You can ask to see, correct or delete what we hold at any time, and you can complain to the Information Commissioner's Office at <a href="https://ico.org.uk/make-a-complaint/">ico.org.uk</a>.</p>
<h2>The tender information</h2>
<p>Names and contact details of buyers' staff on these pages come from the official notices, which buyers publish so that firms can bid. If you're named and would like it removed here, email us.</p>"""
    return page("/privacy/", "Privacy | Bid Ben", "How Bid Ben uses the details you give when you sign up.", body)


def not_found_page() -> str:
    body = """<h1>That page isn't here</h1>
<p class="lede">It may have moved. Try <a href="/tenders/">the open tenders</a>, <a href="/issues/">the Monday issues</a>, or <a href="/">the home page</a>.</p>"""
    return page("/404.html", "Page not found | Bid Ben", "That page isn't here.", body, noindex=True)


def issues_index(issues: list[dict]) -> str:
    items = "".join(
        f'<li><a href="/issues/{i["date"]}/"><b>{E(i["day_text"])}</b></a><span>{E(i["title"])}'
        + (f' · {i["best"]} good for small firms' if i.get("best") else "") + "</span></li>" for i in issues)
    body = f"""<p class="crumbs"><a href="/">Bid Ben</a> › The Monday issue</p>
<h1>The Monday issue</h1>
<p class="lede">Every Monday morning: the week's new public tenders for cleaning and grounds firms, sorted by who they suit. Subscribers get it by email, with their own areas at the top.</p>
<ul class="issuelist">{items}</ul>
{signup_box("Get the next one by email")}"""
    return page("/issues/", "The Monday issue: this week's public tenders for small firms | Bid Ben",
                "Every week's new public-sector cleaning, grounds, tree and pest control tenders, sorted by which "
                "suit a small firm.", body)


# ---- writing it all out ----------------------------------------------------------------------

def _write(rel: str, text: str, written: set[str]) -> None:
    path = ROOT / rel
    written.add(rel)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def list_issues() -> list[dict]:
    """Every issue on disk, newest first, from the small issue.json each one has."""
    out = []
    for meta in sorted((ROOT / "issues").glob("*/issue.json"), reverse=True):
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
        except ValueError:
            continue
        day = dt.date.fromisoformat(info["date"])
        info["day_text"] = f"Monday {day.day} {day:%B %Y}"
        out.append(info)
    return out


def build(data: dict, today: dt.date) -> dict:
    board = Board(data, today)
    issues = list_issues()
    written: set[str] = set()
    indexed = ["/", "/tenders/", "/issues/", "/signup/", "/privacy/"] + [f"/issues/{i['date']}/" for i in issues]

    _write("index.html", home(board, issues[0] if issues else None), written)
    _write("tenders/index.html", tenders_index(board), written)
    _write("issues/index.html", issues_index(issues), written)
    _write("signup/index.html", signup_page(), written)
    _write("privacy/index.html", privacy_page(), written)
    _write("404.html", not_found_page(), written)
    for trade in ORDER:
        _write(f"tenders/{trade}/index.html", trade_page(board, trade), written)
        indexed.append(f"/tenders/{trade}/")
        for area in places.AREAS:
            text, has_content = trade_area_page(board, trade, area)
            _write(f"tenders/{trade}/{area}/index.html", text, written)
            if has_content:
                indexed.append(f"/tenders/{trade}/{area}/")
    for area in places.AREAS:
        text, has_content = area_page(board, area)
        _write(f"areas/{area}/index.html", text, written)
        if has_content:
            indexed.append(f"/areas/{area}/")

    _write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"<url><loc>{SITE}{p}</loc></url>\n" for p in indexed) + "</urlset>\n", written)
    _write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", written)
    _write("status.json", json.dumps({"checked": today.isoformat(), "open": len(board.open)}) + "\n", written)
    _write(".nojekyll", "", written)

    # Remove pages an earlier build made that this one didn't (a trade that was taken out, say).
    try:
        before = set(json.loads(MANIFEST.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        before = set()
    for rel in before - written:
        old = ROOT / rel
        if old.is_file():
            old.unlink()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(sorted(written), indent=0) + "\n", encoding="utf-8")
    return {"pages": len(written), "open": len(board.open), "indexed": len(indexed)}
