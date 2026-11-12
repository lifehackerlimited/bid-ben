"""Checks that the builder still does the right thing. The daily job runs these before it touches the site.

    python -m unittest discover -s tests
"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from builder import issue, notices, places, show, site, store  # noqa: E402
from builder.trades import match_trades  # noqa: E402

TODAY = dt.date(2026, 11, 12)


def fts(title, buyer="Halstead Parish Council", cpv=("77314000",), value=28000, deadline="2026-11-20T17:00:00Z",
        regions=("UKJ46",), buyer_region="UKJ46", tag="tender", status="active", method="Open procedure", desc="",
        published="2026-11-03T09:00:00Z", ocid="ocds-h6vhtk-000001", lots=None, postcode="TN14 7EA", **extra):
    """A cut-down Find a Tender notice."""
    tender = {
        "title": title, "description": desc, "status": status, "mainProcurementCategory": "services",
        "items": [{"id": "1", "additionalClassifications": [{"scheme": "CPV", "id": c} for c in cpv],
                   "deliveryAddresses": [{"region": r, "country": "GB"} for r in regions]}],
        "value": {"amount": value} if value else {},
        "procurementMethod": "open", "procurementMethodDetails": method,
        "tenderPeriod": {"endDate": deadline} if deadline else {},
        "lots": lots or [{"id": "1", "value": {"amount": value} if value else {},
                          "contractPeriod": {"startDate": "2027-01-01T00:00:00Z", "endDate": "2029-12-31T23:59:59Z"}}],
        "documents": [{"documentType": "tenderNotice", "url": "https://www.find-tender.service.gov.uk/Notice/1-2026",
                       "datePublished": published}],
        **extra}
    return {"ocid": ocid, "id": "1-2026", "date": published, "tag": [tag], "tender": tender,
            "buyer": {"id": "B1", "name": buyer},
            "parties": [{"id": "B1", "name": buyer, "roles": ["buyer"],
                         "address": {"locality": "Halstead", "postalCode": postcode, "region": buyer_region},
                         "contactPoint": {"name": "Pip Nott", "email": "clerk@example.gov.uk"}}]}


def notice(*args, postcodes=None, **kw):
    n = notices.from_release("fts", fts(*args, **kw))
    notices.locate(n, postcodes or {})
    return n


class Places(unittest.TestCase):
    def test_every_official_code_has_a_county(self):
        self.assertEqual(places.unmapped_codes(), [])
        self.assertGreater(len(places.all_level3_codes()), 150)

    def test_codes(self):
        self.assertEqual(places.locate_code("UKJ44"), ({"kent"}, set(), False))
        self.assertEqual(places.locate_code("TLJ41"), ({"kent"}, set(), False))
        self.assertEqual(places.locate_code("UKJ1")[0], {"berkshire", "buckinghamshire", "oxfordshire"})
        self.assertEqual(places.locate_code("UKJ"), (set(), {"south-east"}, False))
        self.assertEqual(places.locate_code("UK"), (set(), set(), True))
        self.assertEqual(places.locate_code("UKI"), ({"london"}, set(), False))
        self.assertEqual(places.locate_code("London"), ({"london"}, set(), False))
        self.assertEqual(places.locate_code("DE"), (set(), set(), False))

    def test_every_area_has_a_region(self):
        for slug, area in places.AREAS.items():
            self.assertIn(area["region"], places.REGIONS, slug)

    def test_places_named_in_a_title(self):
        self.assertEqual(places.places_in_title("Grounds Maintenance Services Yorkshire"), (set(), {"yorkshire"}))
        self.assertEqual(places.places_in_title("Cleaning, Kent schools")[0], {"kent"})
        self.assertEqual(places.places_in_title("Playgrounds refurbishment"), (set(), set()))


class Trades(unittest.TestCase):
    CASES = [
        ("Window cleaning, Nottingham Trent University", ["90911300"], ["window-cleaning"]),
        ("Office cleaning and window cleaning services", ["90919200", "90911300"], ["cleaning", "window-cleaning"]),
        ("Arboricultural Services for Peterborough", ["77211400", "77211500", "77340000"], ["tree-work"]),
        ("Griffin Park Bowls Green", ["77320000"], ["grounds-maintenance"]),
        ("Graffiti removal", ["90690000"], ["cleaning"]),
        ("Provision of Pest Control and Prevention Services", ["90922000"], ["pest-control"]),
        ("St Edmunds College Water Hygiene Services", ["90910000"] + list("1234567"), []),
        ("Repairs & Maintenance Framework", ["90910000", "90922000"] + [str(i) for i in range(22)], []),
        ("Haslemere Playgrounds - Lion Green", ["37535200", "45112723"], []),
        ("Christmas Light Trail for Sir Harold Hillier Gardens", ["92000000"], []),
        ("Street Cleansing Services", ["90610000"], []),
        ("Clean Air Zone signage", ["34992200"], []),
    ]

    def test_real_titles(self):
        for title, cpv, want in self.CASES:
            self.assertEqual(match_trades(title, cpv, "services"), want, title)

    def test_buying_goods_is_not_a_contract_for_a_contractor(self):
        self.assertEqual(match_trades("Supply of Cleaning Materials", ["39830000"], "goods"), [])


class Notices(unittest.TestCase):
    def test_reads_the_facts(self):
        n = notice("PRO0663 - GROUNDS AND HEDGE MAINTENANCE")
        self.assertEqual(n["title"], "Grounds And Hedge Maintenance")
        self.assertEqual(n["trades"], ["grounds-maintenance"])
        self.assertEqual(n["areas"], ["kent"])
        self.assertEqual(n["value"], 28000)
        self.assertEqual(n["url"], "https://www.find-tender.service.gov.uk/Notice/1-2026")
        self.assertEqual(n["contact"]["email"], "clerk@example.gov.uk")
        self.assertEqual(n["published"], "2026-11-03")

    def test_placeholder_values_are_not_values(self):
        self.assertIsNone(notice("Grass cutting", value=1)["value"])

    def test_things_we_do_not_list(self):
        self.assertIsNone(notices.from_release("fts", fts("IT support services", cpv=("72000000",))))
        self.assertIsNone(notices.from_release("fts", fts("Grass cutting", tag="planning", status="planning")))
        abroad = fts("Cleaning services")
        abroad["tender"]["items"][0]["deliveryAddresses"] = [{"region": "DE", "country": "DE"}]
        self.assertIsNone(notices.from_release("fts", abroad))

    def test_award_and_cancellation_end_a_tender(self):
        self.assertEqual(notices.from_release("fts", fts("Grass cutting", tag="award", status="complete"))["ended"],
                         "awarded")
        self.assertEqual(notices.from_release("fts", fts("Grass cutting", tag="tenderCancellation"))["ended"],
                         "cancelled")

    def test_a_parish_that_ticked_every_region_is_where_the_parish_is(self):
        n = notice("Grass Cutting Contract", buyer="Kemble & Ewen Parish Council", buyer_region="UKK13",
                   regions=("UKC", "UKD", "UKE", "UKF", "UKG", "UKH", "UKI", "UKJ", "UKK"))
        self.assertEqual(n["areas"], ["gloucestershire"])

    def test_a_title_can_name_the_place(self):
        n = notice("Grounds Maintenance Services Yorkshire", buyer="Your Housing Group", buyer_region="UKD61",
                   regions=("UKD",))
        self.assertEqual((n["areas"], n["regions"]), ([], ["yorkshire"]))

    def test_a_national_body_with_no_place_is_uk_wide(self):
        n = notice("Scrub and tree clearing", buyer="Forestry Commission", buyer_region="UKK11", regions=("UK",),
                   cpv=("77211300",))
        self.assertTrue(n["uk_wide"])

    def test_one_school_in_a_three_county_code_is_in_its_own_county(self):
        n = notice("Cleaning Tender", buyer="St Catherine's Primary School", cpv=("90919300",),
                   regions=("UKG1",), buyer_region="UKG12")
        self.assertEqual(n["areas"], ["worcestershire"])

    def test_postcodes_place_contracts_finder_notices(self):
        n = notice("Grass cutting", regions=(), buyer_region="", postcodes={"TN14 7EA": "kent"})
        self.assertEqual(n["areas"], ["kent"])

    def test_deadline_to_ask_to_take_part(self):
        n = notice("School cleaning", cpv=("90919300",), deadline=None,
                   expressionOfInterestDeadline="2026-11-25T12:00:00Z")
        self.assertEqual(n["deadline_kind"], "interest")
        self.assertEqual(notices.assess(n, TODAY)["days_left"], 13)


class Judgement(unittest.TestCase):
    def test_small_parish_job_is_best(self):
        a = notices.assess(notice("Grass cutting"), TODAY)
        self.assertEqual((a["section"], a["fit"], a["buyer_type"]), ("best", "high", "parish"))
        self.assertTrue(a["open"])

    def test_tupe_makes_it_large(self):
        a = notices.assess(notice("School cleaning", buyer="Shipston High School", cpv=("90919300",), value=200000,
                                  desc="Eight staff will transfer under TUPE."), TODAY)
        self.assertEqual(a["section"], "large")
        self.assertIn("tupe", a["flags"])

    def test_big_is_large_and_middling_is_more(self):
        self.assertEqual(notices.assess(notice("Cleaning services", buyer="Milton Keynes City Council",
                                               cpv=("90910000",), value=4500000), TODAY)["section"], "large")
        self.assertEqual(notices.assess(notice("Cleaning services", buyer="High Peak Borough Council",
                                               cpv=("90910000",), value=450000), TODAY)["section"], "more")

    def test_frameworks_and_call_offs(self):
        self.assertEqual(notices.assess(notice("Cleaning Services Framework", buyer="Delta Academies Trust",
                                               cpv=("90910000",), value=2000000), TODAY)["section"], "framework")
        self.assertEqual(notices.assess(notice("DPS1 1428 - Tree Work", buyer="London Borough of Haringey",
                                               cpv=("77211500",), method="Call-off from a dynamic purchasing system"),
                                        TODAY)["section"], "list-only")

    def test_lots_are_judged_by_the_smallest(self):
        lots = [{"id": str(i), "title": f"Area {i}", "value": {"amount": v},
                 "contractPeriod": {"startDate": "2027-01-01T00:00:00Z", "endDate": "2029-12-31T23:59:59Z"}}
                for i, v in enumerate((47000, 45000, 27000), 1)]
        n = notice("Close cleaning", buyer="Clyde Valley Housing Association", cpv=("90911200",), value=119000,
                   lots=lots, regions=("UKM82",))
        a = notices.assess(n, TODAY)
        self.assertEqual((a["section"], a["size"]), ("best", 27000))
        self.assertEqual(show.value_text(n, a), "3 lots, from £27,000 to £47,000 over 3 years (smallest lot about £9k a year)")

    def test_a_deadline_after_the_start_date_is_flagged(self):
        n = notice("Tree works", buyer="Ipswich Borough Council", cpv=("77211500",), value=140000,
                   deadline="2029-10-31T12:00:00Z")
        self.assertIn("deadline-after-start", notices.assess(n, TODAY)["flags"])
        self.assertEqual(show.view(n, notices.assess(n, TODAY))[0], "Watch out")

    def test_closed_when_the_deadline_has_passed(self):
        self.assertFalse(notices.assess(notice("Grass cutting", deadline="2026-11-08T17:00:00Z"), TODAY)["open"])


class Wording(unittest.TestCase):
    def test_money_and_time(self):
        self.assertEqual(show.money(28000), "£28,000")
        self.assertEqual(show.money(1500000), "£1.5m")
        self.assertEqual(show.rough(46666), "£47k")
        self.assertEqual([show.years_text(y) for y in (0.3, 1, 2.6, 3)], ["4 months", "1 year", "2½ years", "3 years"])

    def test_value_and_deadline(self):
        n = notice("Grass cutting")
        a = notices.assess(n, TODAY)
        self.assertEqual(show.value_text(n, a), "£28,000 over 3 years (about £9k a year)")
        self.assertIn("Fri 20 Nov, 17:00", show.deadline_html(n, a, TODAY))
        self.assertIn("(8 days)", show.deadline_html(n, a, TODAY, static=True))

    def test_the_same_tender_on_both_feeds_is_shown_once(self):
        a = notice("Graffiti removal", buyer="London Borough of Merton", cpv=("90690000",))
        b = dict(a, id="cf:other", src="cf")
        pairs = [(x, notices.assess(x, TODAY)) for x in (a, b)]
        self.assertEqual([n["src"] for n, _ in show.unique(pairs)], ["fts"])


class Site(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self._old = (site.ROOT, site.MANIFEST, issue.ROOT)
        site.ROOT, site.MANIFEST, issue.ROOT = root, root / "data" / "pages.json", root
        items = [notice("Grass cutting", ocid="a"),
                 notice("School cleaning", buyer="Shipston High School", cpv=("90919300",), value=900000,
                        regions=("UKG13",), buyer_region="UKG13", desc="Staff transfer under TUPE.", ocid="b"),
                 notice("Hedge cutting", deadline="2026-11-08T17:00:00Z", regions=("UKH14",), buyer_region="UKH14",
                        buyer="Cottenham Parish Council", ocid="c")]
        self.data = {"notices": {n["id"]: n for n in items}, "fetched_to": "2026-11-12"}

    def tearDown(self):
        site.ROOT, site.MANIFEST, issue.ROOT = self._old
        self.tmp.cleanup()

    def read(self, rel):
        return (Path(self.tmp.name) / rel).read_text(encoding="utf-8")

    def test_builds_every_page(self):
        issue.build(self.data, dt.date(2026, 11, 9), TODAY)
        made = site.build(self.data, TODAY)
        self.assertEqual(made["open"], 2)
        home = self.read("index.html")
        self.assertIn('action="https://formspree.io/f/', home)
        self.assertIn('name="_subject" value="Bid Ben sign-up"', home)
        self.assertNotIn("noindex", home)
        kent = self.read("tenders/grounds-maintenance/kent/index.html")
        self.assertIn("Grounds maintenance tenders in Kent", kent)
        self.assertIn("Grass cutting", kent)
        self.assertNotIn("noindex", kent)
        self.assertIn('value="Kent"', kent)                      # the sign-up box is filled in for the county
        self.assertIn("noindex", self.read("tenders/pest-control/cornwall/index.html"))
        self.assertIn("Recently closed in Suffolk", self.read("tenders/grounds-maintenance/suffolk/index.html"))
        sitemap = self.read("sitemap.xml")
        self.assertIn("/tenders/grounds-maintenance/kent/", sitemap)
        self.assertIn("/tenders/grounds-maintenance/suffolk/", sitemap)     # recently closed counts as content
        self.assertNotIn("/tenders/pest-control/cornwall/", sitemap)
        self.assertIn("/issues/2026-11-09/", sitemap)
        self.assertEqual(json.loads(self.read("status.json")), {"checked": "2026-11-12", "open": 2})

    def test_pages_from_a_dropped_trade_are_removed(self):
        site.build(self.data, TODAY)
        stale = Path(self.tmp.name) / "tenders" / "old-trade" / "index.html"
        stale.parent.mkdir(parents=True)
        stale.write_text("old")
        manifest = json.loads(site.MANIFEST.read_text())
        site.MANIFEST.write_text(json.dumps(manifest + ["tenders/old-trade/index.html"]))
        site.build(self.data, TODAY)
        self.assertFalse(stale.exists())

    def test_the_issue(self):
        monday = dt.date(2026, 11, 9)
        self.assertTrue(issue.due(TODAY))
        info = issue.build(self.data, monday, TODAY)
        self.assertEqual(info["count"], 2)                      # the closed one is left out
        self.assertFalse(issue.due(TODAY))
        email = self.read("issues/2026-11-09/email.html")
        self.assertIn(issue.NEAR_YOU, email)
        self.assertIn("2 new public tenders this week", email)
        self.assertIn("notices published 2–8 November", email)
        self.assertIn("(8 days)", email)                        # days are written in, as email can't run scripts
        self.assertIn("reply with the word <b>unsubscribe</b>", email)
        self.assertNotIn("<script", email)
        meta = json.loads(self.read("issues/2026-11-09/issue.json"))
        self.assertEqual(sorted(e["areas"][0] for e in meta["entries"]), ["kent", "warwickshire"])
        self.assertEqual(json.loads(self.read("issues/latest.json"))["date"], "2026-11-09")
        again = issue.build(self.data, monday, TODAY)
        self.assertIn("left alone", again["note"])              # a published issue isn't rebuilt by accident

    def test_an_older_issue_does_not_become_the_latest(self):
        issue.build(self.data, dt.date(2026, 11, 9), TODAY)
        issue.build(self.data, dt.date(2026, 11, 2), TODAY)
        self.assertEqual(json.loads(self.read("issues/latest.json"))["date"], "2026-11-09")


class Store(unittest.TestCase):
    def test_add_update_and_end(self):
        data = {"notices": {}, "fetched_to": ""}
        first = notices.from_release("fts", fts("Grass cutting"))
        self.assertEqual(store.add(data, first, "2026-11-03"), "new")
        later = notices.from_release("fts", fts("Grass cutting", deadline="2026-11-27T17:00:00Z",
                                                published="2026-11-03T09:00:00Z"))
        later["updated"] = "2026-11-05T10:00:00Z"
        self.assertEqual(store.add(data, later, "2026-11-05"), "updated")
        self.assertEqual(data["notices"][first["id"]]["first_seen"], "2026-11-03")
        self.assertEqual(data["notices"][first["id"]]["deadline"], "2026-11-27T17:00:00Z")
        end = notices.from_release("fts", fts("Grass cutting", tag="award", status="complete",
                                              published="2026-11-10T09:00:00Z"))
        self.assertEqual(store.add(data, end, "2026-11-10"), "ended")
        self.assertEqual(data["notices"][first["id"]]["status"], "awarded")
        self.assertFalse(notices.assess(data["notices"][first["id"]], TODAY)["open"])


if __name__ == "__main__":
    unittest.main()
