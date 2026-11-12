"""Where a tender is: turning the area codes and postcodes in official notices into the counties on the site.

Notices give the place of work as an ONS area code such as UKJ44 (East Kent) or, on Contracts Finder, a postcode.
The site groups those into about 60 areas a contractor would recognise: English counties, plus a handful of
larger areas for Scotland, Wales and Northern Ireland. A code for a whole region (UKJ, South East) can't be pinned
to a county, so it is kept as "region-wide" and shown on every county page in that region.

Area codes and names: Office for National Statistics, licensed under the Open Government Licence v3.0.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

# region key -> name
REGIONS = {
    "north-east": "North East", "north-west": "North West", "yorkshire": "Yorkshire and the Humber",
    "east-midlands": "East Midlands", "west-midlands": "West Midlands", "east": "East of England",
    "london": "London", "south-east": "South East", "south-west": "South West",
    "wales": "Wales", "scotland": "Scotland", "northern-ireland": "Northern Ireland",
}
REGION_BY_LETTER = {"C": "north-east", "D": "north-west", "E": "yorkshire", "F": "east-midlands",
                    "G": "west-midlands", "H": "east", "I": "london", "J": "south-east", "K": "south-west",
                    "L": "wales", "M": "scotland", "N": "northern-ireland"}

# area slug -> (name, region, the ONS level-3 area names it covers)
_AREAS = {
    # North East
    "northumberland": ("Northumberland", "north-east", ["Northumberland"]),
    "tyne-and-wear": ("Tyne and Wear", "north-east", ["Tyneside", "Sunderland"]),
    "county-durham": ("County Durham", "north-east", ["Durham", "Durham CC", "Darlington"]),
    "teesside": ("Teesside", "north-east", ["Hartlepool and Stockton-on-Tees", "South Teesside"]),
    # North West
    "cumbria": ("Cumbria", "north-west", ["West Cumbria", "East Cumbria", "Cumberland", "Westmorland and Furness"]),
    "lancashire": ("Lancashire", "north-west", ["Blackburn with Darwen", "Blackpool", "Lancaster and Wyre",
                                               "Mid Lancashire", "East Lancashire", "Chorley and West Lancashire"]),
    "greater-manchester": ("Greater Manchester", "north-west", [
        "Manchester", "Greater Manchester South West", "Greater Manchester South East",
        "Greater Manchester North West", "Greater Manchester North East"]),
    "merseyside": ("Merseyside", "north-west", ["East Merseyside", "Liverpool", "Sefton", "Wirral"]),
    "cheshire": ("Cheshire", "north-west", ["Warrington", "Cheshire East", "Cheshire West and Chester"]),
    # Yorkshire and the Humber
    "north-yorkshire": ("North Yorkshire", "yorkshire", ["York", "North Yorkshire", "North Yorkshire CC"]),
    "west-yorkshire": ("West Yorkshire", "yorkshire", ["Bradford", "Leeds", "Calderdale and Kirklees", "Wakefield"]),
    "south-yorkshire": ("South Yorkshire", "yorkshire", ["Barnsley, Doncaster and Rotherham", "Sheffield",
                                                         "Barnsley", "Rotherham", "Doncaster"]),
    "east-yorkshire": ("East Yorkshire", "yorkshire", ["Kingston upon Hull, City of", "East Riding of Yorkshire"]),
    # East Midlands
    "derbyshire": ("Derbyshire", "east-midlands", ["Derby", "East Derbyshire", "South and West Derbyshire"]),
    "nottinghamshire": ("Nottinghamshire", "east-midlands", ["Nottingham", "North Nottinghamshire",
                                                             "South Nottinghamshire"]),
    "leicestershire": ("Leicestershire and Rutland", "east-midlands", ["Leicester", "Leicestershire CC and Rutland"]),
    "northamptonshire": ("Northamptonshire", "east-midlands", ["West Northamptonshire", "North Northamptonshire"]),
    "lincolnshire": ("Lincolnshire", "east-midlands", ["Lincolnshire", "Lincolnshire CC",
                                                       "North and North East Lincolnshire"]),
    # West Midlands
    "herefordshire": ("Herefordshire", "west-midlands", ["Herefordshire, County of"]),
    "worcestershire": ("Worcestershire", "west-midlands", ["Worcestershire", "Worcestershire CC"]),
    "warwickshire": ("Warwickshire", "west-midlands", ["Warwickshire", "Warwickshire CC"]),
    "shropshire": ("Shropshire", "west-midlands", ["Telford and Wrekin", "Shropshire", "Shropshire CC"]),
    "staffordshire": ("Staffordshire", "west-midlands", ["Stoke-on-Trent", "Staffordshire CC"]),
    "west-midlands": ("West Midlands", "west-midlands", ["Birmingham", "Solihull", "Coventry", "Dudley", "Sandwell",
                                                         "Walsall", "Wolverhampton"]),
    # East of England
    "cambridgeshire": ("Cambridgeshire", "east", ["Peterborough", "Cambridgeshire CC"]),
    "norfolk": ("Norfolk", "east", ["Norwich and East Norfolk", "North and West Norfolk",
                                    "Breckland and South Norfolk"]),
    "suffolk": ("Suffolk", "east", ["Suffolk", "Suffolk CC", "Babergh and Mid Suffolk", "Ipswich", "East Suffolk",
                                    "West Suffolk"]),
    "essex": ("Essex", "east", ["Southend-on-Sea", "Thurrock", "Essex Haven Gateway", "West Essex", "Heart of Essex",
                                "Essex Thames Gateway"]),
    "hertfordshire": ("Hertfordshire", "east", ["Hertfordshire", "Hertfordshire CC", "North and East Hertfordshire",
                                                "South West Hertfordshire"]),
    "bedfordshire": ("Bedfordshire", "east", ["Luton", "Bedford", "Central Bedfordshire"]),
    # London
    "london": ("London", "london", [
        "Camden and City of London", "Westminster", "Kensington & Chelsea and Hammersmith & Fulham", "Wandsworth",
        "Westminster and City of London", "Camden", "Hackney and Newham", "Tower Hamlets", "Haringey and Islington",
        "Lewisham and Southwark", "Lambeth", "Bexley and Greenwich", "Barking & Dagenham and Havering",
        "Redbridge and Waltham Forest", "Enfield", "Bromley", "Croydon", "Merton, Kingston upon Thames and Sutton",
        "Barnet", "Brent", "Ealing", "Harrow and Hillingdon", "Hounslow and Richmond upon Thames"]),
    # South East
    "kent": ("Kent", "south-east", ["Medway", "Kent Thames Gateway", "East Kent", "Mid Kent", "West Kent"]),
    "east-sussex": ("East Sussex", "south-east", ["Brighton and Hove", "East Sussex CC"]),
    "west-sussex": ("West Sussex", "south-east", ["West Sussex (South West)", "West Sussex (North East)"]),
    "surrey": ("Surrey", "south-east", ["West Surrey", "East Surrey"]),
    "hampshire": ("Hampshire", "south-east", ["Portsmouth", "Southampton", "South Hampshire", "Central Hampshire",
                                              "North Hampshire"]),
    "isle-of-wight": ("Isle of Wight", "south-east", ["Isle of Wight"]),
    "berkshire": ("Berkshire", "south-east", ["Berkshire", "Berkshire East", "Berkshire West"]),
    "buckinghamshire": ("Buckinghamshire", "south-east", ["Milton Keynes", "Buckinghamshire", "Buckinghamshire CC"]),
    "oxfordshire": ("Oxfordshire", "south-east", ["Oxfordshire", "Oxfordshire CC"]),
    # South West
    "bristol-and-bath": ("Bristol and Bath", "south-west", [
        "Bristol, City of", "Bath and North East Somerset, North Somerset and South Gloucestershire",
        "Bath & North East Somerset and South Gloucestershire"]),
    "gloucestershire": ("Gloucestershire", "south-west", ["Gloucestershire", "Gloucestershire CC"]),
    "wiltshire": ("Wiltshire", "south-west", ["Swindon", "Wiltshire"]),
    "somerset": ("Somerset", "south-west", ["Somerset", "Somerset CC", "North Somerset"]),
    "dorset": ("Dorset", "south-west", ["Bournemouth and Poole", "Bournemouth, Christchurch and Poole", "Dorset CC",
                                        "Dorset"]),
    "devon": ("Devon", "south-west", ["Plymouth", "Torbay", "Devon CC"]),
    "cornwall": ("Cornwall", "south-west", ["Cornwall and Isles of Scilly"]),
    # Wales
    "north-wales": ("North Wales", "wales", ["Isle of Anglesey", "Gwynedd", "Conwy and Denbighshire",
                                             "Flintshire and Wrexham"]),
    "mid-and-west-wales": ("Mid and West Wales", "wales", ["Powys", "Mid Wales", "South West Wales"]),
    "south-wales": ("South Wales", "wales", [
        "Swansea", "Neath Port Talbot", "Bridgend and Neath Port Talbot", "Central Valleys",
        "Central Valleys and Bridgend", "Gwent Valleys", "Monmouthshire and Newport",
        "Cardiff and Vale of Glamorgan"]),
    # Scotland
    "glasgow-and-lanarkshire": ("Glasgow and Lanarkshire", "scotland", [
        "Glasgow City", "North Lanarkshire", "South Lanarkshire",
        "East Dunbartonshire and West Dunbartonshire",
        "East Dunbartonshire, West Dunbartonshire and Helensburgh and Lomond",
        "Inverclyde, East Renfrewshire and Renfrewshire"]),
    "edinburgh-and-lothians": ("Edinburgh and the Lothians", "scotland", [
        "City of Edinburgh", "Edinburgh, City of", "East Lothian and Midlothian", "West Lothian"]),
    "tayside-fife-and-central": ("Tayside, Fife and Central Scotland", "scotland", [
        "Clackmannanshire and Fife", "Perth and Kinross and Stirling", "Angus and Dundee City", "Falkirk"]),
    "ayrshire": ("Ayrshire", "scotland", ["East Ayrshire and North Ayrshire mainland",
                                          "North Ayrshire and East Ayrshire", "South Ayrshire"]),
    "south-of-scotland": ("Borders, Dumfries and Galloway", "scotland", ["Scottish Borders", "Dumfries and Galloway"]),
    "aberdeen-and-aberdeenshire": ("Aberdeen and Aberdeenshire", "scotland", ["Aberdeen City and Aberdeenshire"]),
    "highlands-and-islands": ("Highlands and Islands", "scotland", [
        "Highlands and Islands", "Caithness and Sutherland and Ross and Cromarty",
        "Inverness and Nairn and Moray, Badenoch and Strathspey",
        "Inverness and Nairn, Moray, and Badenoch and Strathspey",
        "Lochaber, Skye and Lochalsh, Arran and Cumbrae and Argyll and Bute",
        "Eilean Siar (Western Isles)", "Na h-Eileanan Siar", "Orkney Islands", "Shetland Islands"]),
    # Northern Ireland
    "northern-ireland": ("Northern Ireland", "northern-ireland", [
        "Belfast", "Outer Belfast", "East of Northern Ireland", "North of Northern Ireland",
        "West and South of Northern Ireland", "Armagh City, Banbridge and Craigavon", "Newry, Mourne and Down",
        "Ards and North Down", "Derry City and Strabane", "Mid Ulster", "Causeway Coast and Glens",
        "Antrim and Newtownabbey", "Lisburn and Castlereagh", "Mid and East Antrim", "Fermanagh and Omagh"]),
}

AREAS = {slug: {"slug": slug, "name": name, "region": region} for slug, (name, region, _) in _AREAS.items()}


def _norm(name: str) -> str:
    """'Perth & Kinross and Stirling' and 'Perth and Kinross, and Stirling' are the same place."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", name.lower().replace("&", " and "))).strip()


_BY_NAME = {_norm(n): slug for slug, (_, _, names) in _AREAS.items() for n in names}
_CODE_NAMES: dict[str, str] = json.loads((HERE / "area_codes.json").read_text(encoding="utf-8"))
_BY_CODE = {code: _BY_NAME[_norm(name)] for code, name in _CODE_NAMES.items()
            if len(code) == 5 and _norm(name) in _BY_NAME}


# Contracts Finder writes regions as words, not codes.
_REGION_WORDS = {"north east": "UKC", "north west": "UKD", "yorkshire and the humber": "UKE", "east midlands": "UKF",
                 "west midlands": "UKG", "east of england": "UKH", "london": "UKI", "south east": "UKJ",
                 "south west": "UKK", "wales": "UKL", "scotland": "UKM", "northern ireland": "UKN",
                 "united kingdom": "UK", "england": "UK", "any region": "UK"}

# Places a title might name, for when the buyer left the location box vague. Values are area slugs, or
# "region:<key>" for a whole region.
_TITLE_PLACES = {**{_norm(a["name"]): slug for slug, a in AREAS.items()}, **{
    "yorkshire": "region:yorkshire", "durham": "county-durham", "tyneside": "tyne-and-wear",
    "newcastle upon tyne": "tyne-and-wear", "sunderland": "tyne-and-wear", "manchester": "greater-manchester",
    "liverpool": "merseyside", "birmingham": "west-midlands", "coventry": "west-midlands", "leeds": "west-yorkshire",
    "bradford": "west-yorkshire", "sheffield": "south-yorkshire", "nottingham": "nottinghamshire",
    "leicester": "leicestershire", "bristol": "bristol-and-bath", "sussex": "region:south-east",
    "glasgow": "glasgow-and-lanarkshire", "lanarkshire": "glasgow-and-lanarkshire",
    "edinburgh": "edinburgh-and-lothians", "lothian": "edinburgh-and-lothians", "fife": "tayside-fife-and-central",
    "dundee": "tayside-fife-and-central", "aberdeen": "aberdeen-and-aberdeenshire",
    "aberdeenshire": "aberdeen-and-aberdeenshire", "highland": "highlands-and-islands",
    "cardiff": "south-wales", "swansea": "south-wales", "belfast": "northern-ireland",
    "scotland": "region:scotland", "wales": "region:wales"}}
_TITLE_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in _TITLE_PLACES), key=len, reverse=True)) + r")\b")


def places_in_title(title: str) -> tuple[set[str], set[str]]:
    """('Grounds maintenance Yorkshire') -> (set(), {'yorkshire'}): the areas and regions a title names."""
    areas, regions = set(), set()
    for word in _TITLE_RE.findall(_norm(title or "")):
        hit = _TITLE_PLACES[word]
        (regions if hit.startswith("region:") else areas).add(hit.removeprefix("region:"))
    return areas, regions


def area_for_name(name: str) -> str | None:
    """The area for an ONS level-3 name, as postcodes.io returns it ('Medway' -> 'kent')."""
    return _BY_NAME.get(_norm(name or ""))


def areas_in_region(region: str) -> list[str]:
    return [slug for slug, a in AREAS.items() if a["region"] == region]


def locate_code(code: str) -> tuple[set[str], set[str], bool]:
    """An area code from a notice -> (areas, region-wide regions, covers the whole UK).

    UKJ44 gives ({'kent'}, set(), False). UKJ4 gives every area under it. UKJ gives the South East as a
    region. 'UK' on its own means anywhere in the country. Anything else (DE, a typo) gives nothing.
    """
    code = _REGION_WORDS.get(_norm(code or ""), (code or "").strip().upper())
    if code.startswith("TL"):       # the ONS writes ITL codes as TLJ44; the feeds use the older UKJ44 spelling
        code = "UK" + code[2:]
    if code in ("UK", "GB"):
        return set(), set(), True
    if not re.fullmatch(r"UK[C-N][0-9A-Z]{0,2}", code):
        return set(), set(), False
    region = REGION_BY_LETTER[code[2]]
    if region in ("london", "northern-ireland"):        # one area each, whatever the level
        return {region}, set(), False
    if len(code) == 5 and code in _BY_CODE:
        return {_BY_CODE[code]}, set(), False
    if len(code) >= 4:
        under = {a for c, a in _BY_CODE.items() if c.startswith(code[:4])}
        if under:
            return under, set(), False
    return set(), {region}, False


def all_level3_codes() -> list[str]:
    return [c for c in _CODE_NAMES if len(c) == 5]


def unmapped_codes() -> list[str]:
    """Level-3 codes with no area. Should be empty: the tests check it."""
    return [c for c in all_level3_codes() if c not in _BY_CODE]
