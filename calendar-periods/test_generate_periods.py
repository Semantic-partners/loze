"""Tests for generate_periods.py.

    python3 -m unittest discover -s calendar-periods

The Turtle tests need rdflib, which scripts/build.py already uses; they are
skipped without it. Everything else needs only PyYAML.
"""
import html
import re
import unittest
from pathlib import Path

import yaml

import generate_periods as gp

HERE = Path(__file__).resolve().parent
BASE = "https://example.org/time/"

try:
    import rdflib
except ImportError:  # pragma: no cover
    rdflib = None

ALL = ["day", "week", "month", "quarter", "year", "fiscal_quarter", "fiscal_year", "season"]


def org(id_, month=4, day=1, label_by="end", scheme="meteorological", hemi="north"):
    o = {"id": id_, "fiscal_year_start": {"month": month, "day": day}, "label_by": label_by}
    if scheme:
        o["seasons"] = {"scheme": scheme, "hemisphere": hemi}
    return o


def build(start, end, orgs, granularity=ALL):
    cfg = gp.load_config({"base": BASE, "range": {"start": start, "end": end},
                          "granularity": granularity, "orgs": orgs})
    return gp.build_periods(cfg)


def within(ps, path):
    """Every period that `path` is a subperiod of, following the links."""
    seen, todo = set(), [path]
    while todo:
        for parent in ps.get(todo.pop()).parents:
            if parent not in seen:
                seen.add(parent)
                todo.append(parent)
    return seen


class Memberships(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ps = build("2023-12-01", "2026-04-30", [
            org("acme"),                                         # April, named by end
            org("acme-start", label_by="start", scheme=None),    # April, named by start
            org("calyear", month=1, scheme="meteorological", hemi="south"),
            org("taxyear", month=4, day=6, scheme="astronomical", hemi="north"),
        ])

    def test_2025_11_16_calendar(self):
        w = within(self.ps, "day/2025-11-16")
        self.assertTrue({"month/2025-11", "quarter/2025-Q4", "year/2025", "week/2025-W46"} <= w)

    def test_2025_11_16_fiscal_april_named_by_end(self):
        w = within(self.ps, "day/2025-11-16")
        self.assertIn("fiscal/acme/FY2026-Q3", w)
        self.assertIn("fiscal/acme/FY2026", w)
        self.assertNotIn("fiscal/acme/FY2025", w)

    def test_label_by_start_names_the_same_year_differently(self):
        w = within(self.ps, "day/2025-11-16")
        self.assertIn("fiscal/acme-start/FY2025-Q3", w)
        a, b = self.ps.get("fiscal/acme/FY2026"), self.ps.get("fiscal/acme-start/FY2025")
        self.assertEqual((a.start, a.end), (b.start, b.end))

    def test_two_orgs_same_day_different_fiscal_membership(self):
        w = within(self.ps, "day/2025-11-16")
        self.assertIn("fiscal/acme/FY2026-Q3", w)
        self.assertIn("fiscal/calyear/FY2025-Q4", w)
        self.assertIn("fiscal/taxyear/FY2026-Q3", w)
        self.assertNotIn("fiscal/calyear/FY2026-Q3", w)

    def test_seasons_by_hemisphere(self):
        w = within(self.ps, "day/2025-11-16")
        self.assertIn("season/meteorological-north/2025-autumn", w)
        self.assertIn("season/meteorological-south/2025-spring", w)

    def test_astronomical_boundaries_are_fixed_dates(self):
        self.assertIn("season/astronomical-north/2025-autumn", within(self.ps, "day/2025-12-20"))
        self.assertIn("season/astronomical-north/2025-winter", within(self.ps, "day/2025-12-21"))
        self.assertIn("season/astronomical-north/2025-winter", within(self.ps, "day/2026-03-19"))
        self.assertIn("season/astronomical-north/2026-spring", within(self.ps, "day/2026-03-20"))

    def test_year_boundary(self):
        dec31, jan1 = within(self.ps, "day/2025-12-31"), within(self.ps, "day/2026-01-01")
        self.assertTrue({"year/2025", "quarter/2025-Q4", "fiscal/acme/FY2026-Q3",
                         "fiscal/calyear/FY2025"} <= dec31)
        self.assertTrue({"year/2026", "quarter/2026-Q1", "fiscal/acme/FY2026-Q4",
                         "fiscal/calyear/FY2026"} <= jan1)
        # Same winter, same fiscal year, either side of New Year.
        for w in (dec31, jan1):
            self.assertIn("season/meteorological-north/2025-winter", w)
            self.assertIn("fiscal/acme/FY2026", w)
        self.assertEqual(dec31 & {"week/2026-W01"}, {"week/2026-W01"})  # ISO week 1 of 2026

    def test_leap_day(self):
        d = self.ps.get("day/2024-02-29")
        self.assertIsNotNone(d)
        self.assertEqual(str(self.ps.get("month/2024-02").end), "2024-02-29")
        w = within(self.ps, "day/2024-02-29")
        self.assertTrue({"month/2024-02", "quarter/2024-Q1", "fiscal/acme/FY2024-Q4",
                         "season/meteorological-north/2023-winter"} <= w)
        self.assertEqual(str(self.ps.get("season/meteorological-north/2023-winter").end),
                         "2024-02-29")
        self.assertIsNone(self.ps.get("day/2025-02-29"))

    def test_fiscal_year_spanning_calendar_years(self):
        fy = self.ps.get("fiscal/acme/FY2026")
        self.assertEqual((str(fy.start), str(fy.end)), ("2025-04-01", "2026-03-31"))
        self.assertIn("fiscal/acme/FY2026", within(self.ps, "day/2025-04-01"))
        self.assertIn("fiscal/acme/FY2026", within(self.ps, "day/2026-03-31"))
        self.assertIn("fiscal/acme/FY2027", within(self.ps, "day/2026-04-01"))
        quarters = [self.ps.get(f"fiscal/acme/FY2026-Q{q}") for q in range(1, 5)]
        self.assertEqual([str(q.start) for q in quarters],
                         ["2025-04-01", "2025-07-01", "2025-10-01", "2026-01-01"])

    def test_fiscal_year_starting_mid_month(self):
        # 6 April start: quarters cut months in two, so days link to them directly.
        self.assertIn("fiscal/taxyear/FY2026-Q1", within(self.ps, "day/2025-04-06"))
        self.assertIn("fiscal/taxyear/FY2025-Q4", within(self.ps, "day/2025-04-05"))
        self.assertIn("fiscal/taxyear/FY2026-Q2", within(self.ps, "day/2025-10-05"))
        self.assertIn("fiscal/taxyear/FY2026-Q3", within(self.ps, "day/2025-10-06"))

    def test_links_are_written_once_from_the_largest_fit(self):
        self.assertEqual(self.ps.get("day/2025-11-16").parents, ["month/2025-11", "week/2025-W46"])
        self.assertIn("fiscal/acme/FY2026-Q3", self.ps.get("quarter/2025-Q4").parents)
        self.assertIn("season/meteorological-north/2025-autumn",
                      self.ps.get("month/2025-11").parents)
        self.assertEqual(self.ps.get("fiscal/acme/FY2026-Q3").parents, ["fiscal/acme/FY2026"])

    def test_missing_level_is_skipped(self):
        ps = build("2025-11-01", "2025-11-30", [org("acme")],
                   granularity=["day", "quarter", "fiscal_quarter"])
        self.assertEqual(ps.get("day/2025-11-16").parents, ["quarter/2025-Q4"])
        self.assertIn("fiscal/acme/FY2026-Q3", within(ps, "day/2025-11-16"))


class Config(unittest.TestCase):
    def test_rejects_day_past_28(self):
        with self.assertRaises(ValueError):
            build("2025-01-01", "2025-01-31", [org("x", month=1, day=31)])

    def test_rejects_unknown_label_by(self):
        with self.assertRaises(ValueError):
            build("2025-01-01", "2025-01-31", [org("x", label_by="middle")])

    def test_single_org_key(self):
        cfg = gp.load_config({"range": {"start": "2025-01-01", "end": "2025-01-02"},
                              "org": org("solo")})
        self.assertEqual([o.id for o in cfg.orgs], ["solo"])


class Turtle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = yaml.safe_load((HERE / "example.yaml").read_text(encoding="utf-8"))
        cls.ttl = gp.generate(cls.data)

    def test_same_input_same_bytes(self):
        self.assertEqual(self.ttl, gp.generate(self.data))

    @unittest.skipUnless(rdflib, "rdflib not installed")
    def test_parses_and_describes_its_conventions(self):
        g = rdflib.Graph()
        g.parse(data=self.ttl, format="turtle")
        loze = rdflib.Namespace("https://loze-ontology.org/")
        cal = rdflib.URIRef(BASE + "fiscal/acme-ltd/calendar")
        self.assertEqual(str(g.value(cal, loze.hasFiscalYearStart)), "--04-01")
        self.assertEqual(str(g.value(cal, loze.namesFiscalYearBy)), "end")
        scheme = g.value(cal, loze.usesSeasonScheme)
        self.assertEqual(str(g.value(scheme, loze.hasHemisphere)), "north")
        fq = rdflib.URIRef(BASE + "fiscal/acme-ltd/FY2026-Q3")
        self.assertEqual(g.value(fq, loze.isDelimitedBy), cal)
        self.assertEqual(g.value(fq, loze.hasStartDate).toPython().isoformat(), "2025-10-01")
        self.assertEqual(g.value(rdflib.URIRef(BASE + "season/astronomical-south/2025-spring"),
                                 loze.isDelimitedBy),
                         rdflib.URIRef(BASE + "season/astronomical-south"))

    @unittest.skipUnless(rdflib, "rdflib not installed")
    def test_everything_in_fy2026_q3(self):
        g = rdflib.Graph()
        g.parse(data=self.ttl, format="turtle")
        g.parse(HERE / "sample-payments.ttl", format="turtle")
        rows = g.query("""
            PREFIX loze: <https://loze-ontology.org/>
            SELECT ?payment WHERE {
              ?payment loze:atTime ?period .
              ?period loze:isSubperiodOf* <https://example.org/time/fiscal/acme-ltd/FY2026-Q3> .
            }""")
        got = sorted(str(r[0]).rsplit("/", 1)[1] for r in rows)
        self.assertEqual(got, ["payment-8852", "payment-8871", "payment-8890", "payment-8902"])

    @unittest.skipUnless(rdflib, "rdflib not installed")
    def test_every_query_in_the_guide_answers(self):
        g = rdflib.Graph()
        g.parse(data=self.ttl, format="turtle")
        g.parse(HERE / "sample-payments.ttl", format="turtle")
        guide = (HERE / "guide.html").read_text(encoding="utf-8")
        queries = [html.unescape(q) for q in re.findall(r'<pre class="ttl">(PREFIX.*?)</pre>',
                                                         guide, re.S)]
        self.assertEqual(len(queries), 4)
        for q in queries:
            with self.subTest(q=q.splitlines()[-1]):
                self.assertTrue(list(g.query(q)), "no rows")


if __name__ == "__main__":
    unittest.main()
