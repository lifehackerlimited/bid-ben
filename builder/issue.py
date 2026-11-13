"""The Monday issue: the week's new tenders, sorted by who they suit.

Each issue is three files in issues/<date>/:
    index.html   the page on the site
    email.html   the same thing laid out for email (the outreach autopilot sends this one to subscribers)
    issue.json   the list behind it, so the sender can put each subscriber's own areas at the top

An issue dated Monday covers notices published in the seven days before it that are still open. It's built by the
first daily run on or after that Monday, and never rebuilt unless you ask (--force), so a published issue doesn't
change under people's feet.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import notices, places, show
from .settings import COMPANY, OFFICE, SITE
from .show import E

ROOT = Path(__file__).resolve().parent.parent
NEAR_YOU = "<!-- NEAR-YOU -->"      # the sender swaps this for the subscriber's own areas

TIPS = [
    ("Start with parish and town councils.",
     "They usually skip the heavy questionnaires, often publish the full task list in the notice, and many still "
     "accept a simple priced quote by email or post. Win one or two and you have public-sector references for the "
     "bigger contracts."),
    ("Find out who has the contract now.",
     "The notice rarely says. Search the buyer's name on Contracts Finder or Find a Tender for the last award "
     "notice: it names the winner and usually the price they won at."),
    ("Price the staff before anything else.",
     "If the current contractor's staff transfer to you (TUPE), their wages, hours and pensions come with them. "
     "Ask the buyer for the staffing information early and build your price on it."),
    ("Register on the portal before you need it.",
     "Most tenders run through a portal such as ProContract, In-Tend, Delta, MyTenders, Public Contracts Scotland "
     "or Sell2Wales. Registering is free but can take a day to be approved."),
    ("Ask your questions early.",
     "Buyers set a cut-off for questions, often a week before the deadline, and send every answer to all bidders. "
     "A good question can clear up a doubt that would otherwise cost you marks."),
    ("Keep the basics in one folder.",
     "Insurance certificates, your health and safety policy, two references and your latest accounts. Almost "
     "every tender asks for them, and having them ready turns a lost evening into ten minutes."),
    ("Lots are there for firms like yours.",
     "When a contract is split into lots by area or by task, you can bid for one. Pick the lot nearest your base "
     "and say why being local makes you reliable."),
    ("Judge a framework by the work that flows through it.",
     "A place on a framework is only a place on a list. Before you spend a week on the application, look for the "
     "call-offs that list has produced in the last year."),
    ("Go to the site visit.",
     "It's often your only chance to see the job before pricing it, and some buyers won't accept a bid from a firm "
     "that didn't attend. Take photos and measurements."),
    ("Don't trust a deadline that's months away.",
     "Staged tenders have an earlier first step, such as a questionnaire, and portals sometimes show the wrong "
     "date. Open the documents and find the real one."),
    ("Ask to go on the quotes list.",
     "Many councils and schools buy small jobs by asking three firms for a quote, without advertising. A short "
     "email to the clerk or the business manager asking to be included costs nothing."),
    ("Say what you already do for the area.",
     "Most public tenders score 'social value': local jobs, apprentices, helping a local club. You probably do "
     "some of this already, so write it down with numbers."),
]


def this_monday(today: dt.date) -> dt.date:
    return today - dt.timedelta(days=today.weekday())


def folder(monday: dt.date) -> Path:
    return ROOT / "issues" / monday.isoformat()


def due(today: dt.date) -> bool:
    """Is this week's issue still to be built?"""
    return not (folder(this_monday(today)) / "issue.json").exists()


def _span(start: dt.date, end: dt.date) -> str:
    if start.month == end.month:
        return f"{start.day}–{end.day} {end:%B}"
    return f"{start.day} {start:%B} – {end.day} {end:%B}"


def pick(data: dict, monday: dt.date, today: dt.date) -> tuple[list, list]:
    """(this week's new tenders that are still open, others closing within a week), each as (notice, assessment)."""
    as_of = max(monday, today)
    start, end = monday - dt.timedelta(days=7), monday - dt.timedelta(days=1)
    everything = [(n, notices.assess(n, as_of)) for n in data["notices"].values()]
    still_open = show.unique([na for na in everything if na[1]["open"]])
    new = show.by_deadline([na for na in still_open if start <= na[1]["published"] <= end])
    closing = show.by_deadline([na for na in still_open if na not in new and na[1]["section"] in ("best", "more")
                                and na[1]["days_left"] is not None and na[1]["days_left"] <= 7])
    return new, closing


def _sections(new: list, as_of: dt.date, static: bool, table_class: str) -> str:
    out = []
    for key in show.SECTION_ORDER:
        group = [na for na in new if na[1]["section"] == key]
        if not group:
            continue
        heading, lede = show.SECTIONS[key]
        out.append(f'<h2>{E(heading)}</h2>\n<p class="lede">{E(lede)}</p>\n')
        if key == "best":
            out.append("".join(show.card(n, a, as_of, static=static) for n, a in group))
        elif key == "large":
            flagged = [na for na in group if "tupe" in na[1]["flags"]][:2]
            out.append("".join(show.card(n, a, as_of, static=static) for n, a in flagged))
            rest = [na for na in group if na not in flagged]
            if rest:
                out.append(show.table("".join(show.row(n, a, as_of, static=static) for n, a in rest), cls=table_class))
        else:
            out.append(show.table("".join(show.row(n, a, as_of, static=static) for n, a in group),
                                  "Framework" if key == "framework" else "Tender", cls=table_class))
    return "".join(out)


def _body(new: list, closing: list, monday: dt.date, as_of: dt.date, static: bool, table_class: str) -> str:
    best = sum(1 for _, a in new if a["section"] == "best")
    parish = sum(1 for _, a in new if a["buyer_type"] == "parish")
    stats = [f'<div class="stat"><b>{len(new)}</b><span>new tenders across the UK</span></div>',
             f'<div class="stat"><b>{best}</b><span>a good fit for a small firm</span></div>']
    if parish:
        stats.append(f'<div class="stat"><b>{parish}</b><span>from parish and town councils, the easiest first '
                     f'bids</span></div>')
    alert = ""
    soon = [na for na in new if na[1]["days_left"] is not None and na[1]["days_left"] <= 7
            and na[1]["section"] not in ("framework", "list-only")][:5] + closing[:5]
    if soon:
        lines = "".join(
            f'<li><a href="{E(n["url"])}">{E(n["title"])}</a>, {E(n["buyer"])}: '
            f'{show.deadline_html(n, a, as_of, label=False, static=static)}</li>' for n, a in soon)
        alert = f'<div class="alert"><b>Closing in the next 7 days</b><ul>{lines}</ul></div>\n'
    tip_title, tip_text = TIPS[monday.isocalendar()[1] % len(TIPS)]
    return (f'<div class="stats">{"".join(stats)}</div>\n{NEAR_YOU if static else ""}\n{alert}'
            + (_sections(new, as_of, static, table_class) or
               '<p class="lede">No new tenders in these trades were published this week.</p>')
            + f'<div class="tip"><b>Tip of the week: {E(tip_title)}</b> {E(tip_text)}</div>\n')


EMAIL_STYLE = """
  body { margin: 0; background: #f4f2ec; font-family: "Avenir Next", -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1c2236; line-height: 1.5; }
  .wrap { max-width: 680px; margin: 0 auto; background: #fff; }
  header { background: #17264a; color: #fbf6ea; padding: 22px 28px 24px; border-bottom: 4px solid #e3a93b; }
  header .logo { display: block; width: 214px; height: auto; margin: 0 0 18px -8px; border: 0; }
  header .kicker { font-size: 12px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: #e3a93b; margin: 0 0 6px; }
  header h1 { font-size: 26px; margin: 0 0 6px; line-height: 1.2; color: #fbf6ea; }
  header p { margin: 0; color: #c9cede; font-size: 15px; }
  main { padding: 8px 28px 28px; }
  h2 { font-size: 19px; margin: 32px 0 4px; color: #17264a; padding-left: 12px; border-left: 4px solid #e3a93b; line-height: 1.25; }
  .lede { margin: 0 0 14px; color: #5d6478; font-size: 14px; }
  .stats { display: flex; gap: 10px; margin: 22px 0 6px; flex-wrap: wrap; }
  .stat { flex: 1 1 130px; background: #fbf6ea; border-top: 3px solid #e3a93b; border-radius: 8px; padding: 12px 14px; }
  .stat b { display: block; font-size: 24px; color: #17264a; line-height: 1.1; }
  .stat span { font-size: 13px; color: #4b5268; }
  .near { background: #eef3fb; border-left: 4px solid #17264a; border-radius: 0 8px 8px 0; padding: 12px 16px; margin: 18px 0 0; font-size: 15px; }
  .near ul { margin: 6px 0 0; padding-left: 18px; }
  .note { background: #fbefd2; color: #6e4f0c; border-radius: 8px; padding: 12px 16px; margin: 18px 0 0; font-size: 15px; }
  .alert { background: #fdecea; border-left: 4px solid #c0392b; padding: 12px 16px; border-radius: 0 6px 6px 0; margin: 18px 0 0; font-size: 15px; }
  .alert ul { margin: 6px 0 0; padding-left: 18px; }
  .card { border: 1px solid #e3e5ec; border-radius: 10px; padding: 16px 18px; margin: 0 0 14px; }
  .card h3 { font-size: 17px; margin: 0 0 2px; line-height: 1.3; }
  .card h3 a, td a { color: #17264a; }
  .card .who { color: #5d6478; font-size: 14px; margin: 0 0 10px; }
  .facts { font-size: 14px; margin: 0 0 10px; }
  .facts span { display: inline-block; margin: 0 16px 4px 0; }
  .fit { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 99px; margin-left: 6px; }
  .fit.high { background: #d6f0df; color: #17603a; }
  .fit.medium { background: #fff1c7; color: #7a5a00; }
  .fit.low { background: #f1e3e1; color: #8a3027; }
  .card p { margin: 0 0 8px; font-size: 15px; }
  .card .view { background: #f6f7fa; border-radius: 6px; padding: 8px 12px; font-size: 14px; }
  .card .how { font-size: 13px; color: #4b5268; margin: 8px 0 0; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; margin: 0 0 8px; }
  th { text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #5d6478; border-bottom: 2px solid #e3e5ec; padding: 6px 8px 6px 0; }
  td { border-bottom: 1px solid #eef0f4; padding: 8px 8px 8px 0; vertical-align: top; }
  td small { color: #5d6478; }
  .tip { background: #fbf6ea; border-left: 4px solid #e3a93b; border-radius: 0 10px 10px 0; padding: 14px 18px; margin: 28px 0 0; font-size: 15px; }
  footer { border-top: 1px solid #e3e5ec; padding: 20px 28px 32px; font-size: 12px; color: #6b7186; }
  footer p { margin: 0 0 8px; }
  footer .brand { font-size: 14px; color: #17264a; margin: 0 0 12px; }
  footer a { color: #6b7186; }
  @media (max-width: 520px) { main, header, footer { padding-left: 18px; padding-right: 18px; } }
"""


def email_html(title: str, monday: dt.date, inner: str) -> str:
    start, end = monday - dt.timedelta(days=7), monday - dt.timedelta(days=1)
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Bid Ben · {E(title)}</title>
<style>{EMAIL_STYLE}</style>
</head>
<body>
<div class="wrap">
<header>
  <img class="logo" src="{SITE}/assets/bid-ben-logo-reversed.png" width="214" height="78" alt="Bid Ben">
  <p class="kicker">Cleaning &amp; grounds · Monday edition</p>
  <h1>{E(title)}</h1>
  <p>Monday {monday.day} {monday:%B %Y} · notices published {_span(start, end)}, sorted and explained in plain English</p>
</header>
<main>
{inner}
</main>
<footer>
  <p class="brand"><b>Bid <span style="color:#c48a1f">Ben</span></b> · public contracts, on the dot, every Monday</p>
  <p><b>Information only.</b> We summarise official notices to help you decide what's worth your time. Always read the full notice and the buyer's tender documents before bidding: they take precedence over anything here. Dates, values and contacts are copied from the official notices. "Small-firm fit" and "Our view" are worked out automatically from the value, the buyer and the procedure, so treat them as a guide.</p>
  <p>Contains public sector information licensed under the <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">Open Government Licence v3.0</a>. Sources: Contracts Finder and Find a Tender.</p>
  <p>Bid Ben is run by {COMPANY}, {OFFICE}. You're getting this because you signed up for Bid Ben. To stop, reply with the word <b>unsubscribe</b>. See every tender open now at <a href="{SITE}/tenders/">bidben.betttech.co.uk</a>.</p>
</footer>
</div>
</body>
</html>
"""


def web_html(title: str, monday: dt.date, inner: str, count: int) -> str:
    from . import site      # here, not at the top: site.py reads the issues this module writes
    start, end = monday - dt.timedelta(days=7), monday - dt.timedelta(days=1)
    body = f"""<p class="crumbs"><a href="/">Bid Ben</a> › <a href="/issues/">The Monday issue</a> › {monday.day} {monday:%B %Y}</p>
<div class="issue">
  <div class="ihead">
    <p class="kicker">Cleaning &amp; grounds · Monday edition</p>
    <h1>{E(title)}</h1>
    <p>Monday {monday.day} {monday:%B %Y} · notices published {_span(start, end)}, sorted and explained in plain English</p>
  </div>
  <div class="ibody">
{inner}
  </div>
</div>
{site.signup_box("Get this in your inbox every Monday", "The same issue by email, with the tenders nearest you at the top. The first four weeks are free.")}
<p class="lede" style="margin-top:18px">Deadlines pass quickly. For what's open today, see <a href="/tenders/">all open tenders</a>.</p>"""
    return site.page(f"/issues/{monday.isoformat()}/", f"Bid Ben, {monday.day} {monday:%B %Y}: {title}",
                     f"The {monday.day} {monday:%B %Y} issue of Bid Ben: {count} new public-sector cleaning, grounds, "
                     "tree work and pest control tenders, sorted by which suit a small firm.", body)


def build(data: dict, monday: dt.date, today: dt.date, force: bool = False) -> dict:
    out = folder(monday)
    meta_path = out / "issue.json"
    if meta_path.exists() and not force:
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        return {"count": old.get("count", 0), "note": "Already published, so left alone (--force rebuilds it)."}
    as_of = max(monday, today)
    new, closing = pick(data, monday, today)
    title = f"{len(new)} new public tender{'s' if len(new) != 1 else ''} this week"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(
        web_html(title, monday, _body(new, closing, monday, as_of, False, "list"), len(new)), encoding="utf-8")
    (out / "email.html").write_text(
        email_html(title, monday, _body(new, closing, monday, as_of, True, "")), encoding="utf-8")
    entries = [{"title": n["title"], "buyer": n["buyer"], "url": n["url"], "areas": n["areas"],
                "regions": n["regions"], "uk_wide": n["uk_wide"], "trades": n["trades"], "section": a["section"],
                "fit": a["fit"], "value": show.value_text(n, a),
                "deadline": show.when_text(a["deadline"], as_of) if a["deadline"] else ""} for n, a in new]
    meta = {"date": monday.isoformat(), "title": title, "count": len(new),
            "best": sum(1 for _, a in new if a["section"] == "best"),
            "parish": sum(1 for _, a in new if a["buyer_type"] == "parish"),
            "built": as_of.isoformat(), "entries": entries,
            "areas": {slug: a["name"] for slug, a in places.AREAS.items()}}
    meta_path.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    latest = ROOT / "issues" / "latest.json"
    try:
        newer_exists = json.loads(latest.read_text(encoding="utf-8"))["date"] > meta["date"]
    except (OSError, ValueError, KeyError):
        newer_exists = False
    if newer_exists:        # rebuilding an old issue mustn't make it "the latest"
        return {"count": len(new), "note": f"Written to issues/{monday.isoformat()}/."}
    latest.write_text(json.dumps(
        {"date": meta["date"], "title": title, "count": len(new), "email": f"{SITE}/issues/{meta['date']}/email.html",
         "data": f"{SITE}/issues/{meta['date']}/issue.json"}, indent=1) + "\n", encoding="utf-8")
    return {"count": len(new), "note": f"Written to issues/{monday.isoformat()}/."}
