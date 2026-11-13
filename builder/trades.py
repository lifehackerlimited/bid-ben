"""The trades Bid Ben covers, and how a notice is matched to them.

To add a trade, add an entry to TRADES: a name, the CPV codes buyers file that work under (a code matches by its
leading digits), and the words that give it away in a title. Then run the builder: its pages appear by themselves.

CPV is the buyers' own classification. It's loose: a big repairs framework can list fifty codes, cleaning among
them. So a notice counts for a trade only if its title says so, or it carries one of the trade's codes and at
most MAX_CODES codes in all.
"""
from __future__ import annotations

import re

MAX_CODES = 3

TRADES = {
    "cleaning": {
        "name": "Cleaning",
        "noun": "cleaning",
        "blurb": "Office, school, communal-area and specialist cleaning for councils, schools, housing "
                 "associations and the NHS.",
        "cpv": ("90910", "90911", "90919", "90690", "90914", "90918", "9834113", "9834114"),
        "not_cpv": ("909113",),         # window cleaning has its own page
        "title": r"\bclean(ing|ers?|sing)?\b|\bjanitorial\b|\bcaretaking\b|\bgraffiti removal\b|\bdeep clean",
        "not_title": r"\bstreet clean|\bstreet sweep|\bsewer|\bdrain|\btank clean|\bduct|"
                     r"\bclean(ing)? (products|materials|chemicals|supplies|equipment|consumables)|\bclean air|"
                     r"\bclean energy|\bclean heat|\bclean room|\bcleanroom|\bclean growth|\blaundry|\bdata clean",
    },
    "window-cleaning": {
        "name": "Window cleaning",
        "noun": "window cleaning",
        "blurb": "Window, cladding and high-level glass cleaning, often let separately from the daily clean.",
        "cpv": ("909113",),
        "not_cpv": (),
        "title": r"\bwindow clean",
        "not_title": r"",
    },
    "grounds-maintenance": {
        "name": "Grounds maintenance",
        "noun": "grounds maintenance",
        "blurb": "Grass cutting, hedges, planting, sports pitches, cemeteries, verges and winter gritting.",
        "cpv": ("7731", "7732", "7733", "77300", "71421", "9062", "9063"),
        "not_cpv": (),
        "title": r"\bgrounds? maintenance\b|\bgrounds? (and|&) |\bgrass cutting\b|\bgrasscutting\b|\bmowing\b|"
                 r"\bhedge|\blandscape maintenance\b|\blandscaping maintenance\b|\bsoft landscap|\bhorticultur|"
                 r"\bgardening (services|contract)|\bgarden (maintenance|clearance)|\bplanting\b|\bverge|\bsports? pitch|"
                 r"\bweed (control|spraying|treatment)|\blitter pick|\bgritting\b|\bbowls green\b|"
                 r"\bcemetery maintenance\b|\bopen spaces? maintenance\b|\bgreen spaces? maintenance\b",
        "not_title": r"\bplayground (equipment|refurb|install)|\bartificial|\b3g\b|\bresurfac",
    },
    "tree-work": {
        "name": "Tree work",
        "noun": "tree work",
        "blurb": "Tree surgery, felling, pruning, stump removal and tree safety surveys.",
        "cpv": ("772113", "772114", "772115", "7734"),
        "not_cpv": (),
        "title": r"\barboricultur|\btree (work|surgery|felling|maintenance|safety|surve|management|removal|"
                 r"pruning|planting|inspection|services|and stump)|\btrees?\s+(\w+\s+){0,2}(works?|maintenance)\b|\bstump",
        "not_title": r"\bdecision tree|\btree house|\bchristmas tree",
    },
    "pest-control": {
        "name": "Pest control",
        "noun": "pest control",
        "blurb": "Rodent, insect and bird control contracts for councils, housing providers and public buildings.",
        "cpv": ("90922", "90923", "909210"),
        "not_cpv": (),
        "title": r"\bpest control\b|\bpest management\b|\bvermin\b|\brodent",
        "not_title": r"",
    },
}

ORDER = list(TRADES)


def match_trades(title: str, cpv_codes: list[str], category: str = "") -> list[str]:
    """The trades a notice belongs to, most relevant first. An empty list means it isn't for us."""
    if category == "goods":             # buying mowers or cleaning chemicals, not hiring a contractor
        return []
    title_l = (title or "").lower()
    codes = sorted(set(cpv_codes))
    found = []
    for slug in ORDER:
        t = TRADES[slug]
        text = title_l
        if slug == "cleaning" and "window clean" in text:
            text = re.sub(r"window clean\w*", " ", text)       # that part belongs on the window-cleaning page
            if not re.search(t["title"], text):
                continue
        if t["not_title"] and re.search(t["not_title"], text):
            continue
        in_title = bool(re.search(t["title"], text))
        own = [c for c in codes if c.startswith(t["cpv"]) and not (t["not_cpv"] and c.startswith(t["not_cpv"]))]
        if in_title or (own and len(codes) <= MAX_CODES):
            found.append((0 if in_title else 1, ORDER.index(slug), slug))
    return [slug for _, _, slug in sorted(found)]
