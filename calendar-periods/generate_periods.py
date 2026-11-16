#!/usr/bin/env python3
"""Generate calendar, fiscal and season periods for a range of dates, as Turtle.

    python3 calendar-periods/generate_periods.py calendar-periods/example.yaml > periods.ttl
    python3 calendar-periods/generate_periods.py calendar-periods/example.yaml -o periods.ttl

Part of loze's suggested calendar extension (suggested-calendar-extension.ttl),
not core loze. Standard library plus PyYAML. The output is the same bytes for
the same input: statements are sorted and nothing depends on the clock.

Every period is a loze:PeriodOfTime with loze:hasStartDate and loze:hasEndDate
(both inclusive xsd:date). Membership is loze:isSubperiodOf, written once, from
the largest calendar period that fits; see calendar_links() and the module page.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import yaml

LOZE = "https://loze-ontology.org/"
CALENDAR_KINDS = ["day", "month", "quarter", "year"]
KINDS = CALENDAR_KINDS + ["week", "fiscal_quarter", "fiscal_year", "season"]
DEFAULT_GRANULARITY = ["day", "month", "quarter", "year",
                       "fiscal_quarter", "fiscal_year", "season"]
CLASS = {
    "day": "CalendarDay", "week": "CalendarWeek", "month": "CalendarMonth",
    "quarter": "CalendarQuarter", "year": "CalendarYear",
    "fiscal_quarter": "FiscalQuarter", "fiscal_year": "FiscalYear", "season": "Season",
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# Season start (month, day) in order: the first starts in March.
SEASON_STARTS = {
    "meteorological": [(3, 1), (6, 1), (9, 1), (12, 1)],
    # Fixed approximations of the March equinox, June solstice, September
    # equinox and December solstice. The real dates move by a day either way
    # from year to year; a day near a boundary can land in the wrong season.
    "astronomical": [(3, 20), (6, 21), (9, 22), (12, 21)],
}
SEASON_NAMES = {
    "north": ["spring", "summer", "autumn", "winter"],
    "south": ["autumn", "winter", "spring", "summer"],
}


# ── Date arithmetic ─────────────────────────────────────────────────────────

def add_months(d: date, n: int) -> date:
    """d moved by n months. Only called with day <= 28, so always valid."""
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, d.day)


def month_span(y: int, m: int) -> Tuple[date, date]:
    start = date(y, m, 1)
    return start, add_months(start, 1) - timedelta(days=1)


def fiscal_year_start(d: date, month: int, day: int) -> date:
    """First day of the fiscal year that contains d."""
    y = d.year if (d.month, d.day) >= (month, day) else d.year - 1
    return date(y, month, day)


def season_start(d: date, method: str) -> Tuple[date, int]:
    """First day of the season containing d, and its index (0 = March start)."""
    best = None
    for y in (d.year - 1, d.year):
        for i, (m, dd) in enumerate(SEASON_STARTS[method]):
            s = date(y, m, dd)
            if s <= d:
                best = (s, i)
    return best


def season_end(start: date, index: int, method: str) -> date:
    m, dd = SEASON_STARTS[method][(index + 1) % 4]
    return date(start.year + (1 if index == 3 else 0), m, dd) - timedelta(days=1)


def daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


# ── Configuration ───────────────────────────────────────────────────────────

@dataclass
class Org:
    id: str
    iri: str
    label: Optional[str]
    fy_month: int
    fy_day: int
    label_by: str
    season_method: Optional[str]
    hemisphere: Optional[str]

    @property
    def scheme(self) -> Optional[str]:
        return f"{self.season_method}-{self.hemisphere}" if self.season_method else None


@dataclass
class Config:
    base: str
    start: date
    end: date
    granularity: List[str]
    orgs: List[Org]


def as_date(v, key: str) -> date:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        raise ValueError(f"{key}: {v!r} is not a date (YYYY-MM-DD)")


def load_config(data: dict) -> Config:
    base = str(data.get("base", "https://example.org/time/"))
    if not base.endswith(("/", "#")):
        base += "/"
    rng = data.get("range") or {}
    start, end = as_date(rng.get("start"), "range.start"), as_date(rng.get("end"), "range.end")
    if end < start:
        raise ValueError("range.end is before range.start")
    gran = list(data.get("granularity") or DEFAULT_GRANULARITY)
    bad = [g for g in gran if g not in KINDS]
    if bad:
        raise ValueError(f"granularity: unknown {bad}; choose from {KINDS}")

    raw = data.get("orgs")
    if raw is None:
        raw = [data["org"]] if "org" in data else []
    orgs = []
    for o in raw:
        oid = str(o["id"])
        fy = o.get("fiscal_year_start") or {"month": 1, "day": 1}
        m, d = int(fy.get("month", 1)), int(fy.get("day", 1))
        if not (1 <= m <= 12 and 1 <= d <= 28):
            # Day 29-31 has no counterpart in every month, so the quarters would
            # need a rule for it. Real fiscal years do not start there.
            raise ValueError(f"org {oid}: fiscal_year_start must be month 1-12, day 1-28")
        label_by = str(o.get("label_by", "end"))
        if label_by not in ("start", "end"):
            raise ValueError(f"org {oid}: label_by must be start or end")
        seasons = o.get("seasons")
        method = hemi = None
        if seasons:
            method = str(seasons.get("scheme", "meteorological"))
            hemi = str(seasons.get("hemisphere", "north"))
            if method not in SEASON_STARTS:
                raise ValueError(f"org {oid}: seasons.scheme must be meteorological or astronomical")
            if hemi not in SEASON_NAMES:
                raise ValueError(f"org {oid}: seasons.hemisphere must be north or south")
        orgs.append(Org(oid, str(o.get("iri") or f"{base}org/{oid}"), o.get("label"),
                        m, d, label_by, method, hemi))
    if len({o.id for o in orgs}) != len(orgs):
        raise ValueError("org ids must be unique")
    if {"fiscal_quarter", "fiscal_year"} & set(gran) and not orgs:
        raise ValueError("fiscal granularity needs at least one org")
    return Config(base, start, end, gran, orgs)


# ── Periods ─────────────────────────────────────────────────────────────────

@dataclass
class Period:
    path: str            # relative to base, e.g. "day/2025-11-16"
    kind: str
    label: str
    start: date
    end: date
    family: str = "calendar"          # "calendar", "fiscal:<org>" or "season:<scheme>"
    delimiter: Optional[str] = None   # path of the fiscal calendar or season scheme
    parents: List[str] = field(default_factory=list)

    def contains(self, other: "Period") -> bool:
        return self.start <= other.start and other.end <= self.end


class Periods:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.by_path: Dict[str, Period] = {}
        self.by_kind: Dict[str, List[Period]] = {k: [] for k in KINDS}

    def add(self, p: Period) -> Period:
        if p.path not in self.by_path:
            self.by_path[p.path] = p
            self.by_kind[p.kind].append(p)
        return self.by_path[p.path]

    def get(self, path: str) -> Optional[Period]:
        return self.by_path.get(path)


def day_period(d: date) -> Period:
    return Period(f"day/{d.isoformat()}", "day", f"{d.day} {MONTHS[d.month - 1]} {d.year}", d, d)


def month_period(d: date) -> Period:
    s, e = month_span(d.year, d.month)
    return Period(f"month/{d.year}-{d.month:02d}", "month", f"{MONTHS[d.month - 1]} {d.year}", s, e)


def quarter_period(d: date) -> Period:
    q = (d.month - 1) // 3 + 1
    s = date(d.year, 3 * q - 2, 1)
    return Period(f"quarter/{d.year}-Q{q}", "quarter", f"{d.year} Q{q}", s,
                  add_months(s, 3) - timedelta(days=1))


def year_period(d: date) -> Period:
    return Period(f"year/{d.year}", "year", str(d.year), date(d.year, 1, 1), date(d.year, 12, 31))


def week_period(d: date) -> Period:
    iy, iw, wd = d.isocalendar()
    s = d - timedelta(days=wd - 1)
    return Period(f"week/{iy}-W{iw:02d}", "week", f"{iy}-W{iw:02d}", s, s + timedelta(days=6))


def fiscal_name(org: Org, fy_start: date) -> int:
    fy_end = add_months(fy_start, 12) - timedelta(days=1)
    return fy_end.year if org.label_by == "end" else fy_start.year


def fiscal_year_period(org: Org, d: date) -> Period:
    s = fiscal_year_start(d, org.fy_month, org.fy_day)
    n = fiscal_name(org, s)
    who = org.label or org.id
    return Period(f"fiscal/{org.id}/FY{n}", "fiscal_year", f"{who} FY{n}", s,
                  add_months(s, 12) - timedelta(days=1),
                  family=f"fiscal:{org.id}", delimiter=f"fiscal/{org.id}/calendar")


def fiscal_quarter_period(org: Org, d: date) -> Period:
    fs = fiscal_year_start(d, org.fy_month, org.fy_day)
    n = fiscal_name(org, fs)
    q = next(k for k in range(1, 5) if d < add_months(fs, 3 * k))
    s = add_months(fs, 3 * (q - 1))
    who = org.label or org.id
    return Period(f"fiscal/{org.id}/FY{n}-Q{q}", "fiscal_quarter", f"{who} FY{n} Q{q}", s,
                  add_months(s, 3) - timedelta(days=1),
                  family=f"fiscal:{org.id}", delimiter=f"fiscal/{org.id}/calendar")


def season_period(method: str, hemi: str, d: date) -> Period:
    s, i = season_start(d, method)
    e = season_end(s, i, method)
    name = SEASON_NAMES[hemi][i]
    scheme = f"{method}-{hemi}"
    # Named by the year it starts in, so December-February is "<year>-winter"
    # in the north; the label spells out both years.
    span = str(s.year) if s.year == e.year else f"{s.year}-{str(e.year)[2:]}"
    return Period(f"season/{scheme}/{s.year}-{name}", "season",
                  f"{name} {span} ({method}, {hemi}ern hemisphere)", s, e,
                  family=f"season:{scheme}", delimiter=f"season/{scheme}")


def build_periods(cfg: Config) -> Periods:
    """Every period of each chosen kind that overlaps the range, whole.

    Days are the range itself. A month, quarter, fiscal year or season that
    overlaps the range is generated with its true start and end, never clipped.
    """
    ps = Periods(cfg)
    g = set(cfg.granularity)
    # Walk every day of every period that overlaps the range, so the containers
    # of a generated period are generated too.
    lo = date(cfg.start.year - 1, 1, 1)
    hi = date(cfg.end.year + 1, 12, 31)
    makers = []
    if "month" in g: makers.append(month_period)
    if "quarter" in g: makers.append(quarter_period)
    if "year" in g: makers.append(year_period)
    if "week" in g: makers.append(week_period)
    for o in cfg.orgs:
        if "fiscal_year" in g: makers.append(lambda d, o=o: fiscal_year_period(o, d))
        if "fiscal_quarter" in g: makers.append(lambda d, o=o: fiscal_quarter_period(o, d))
        if "season" in g and o.scheme:
            makers.append(lambda d, o=o: season_period(o.season_method, o.hemisphere, d))
    for d in daterange(lo, hi):
        for mk in makers:
            p = mk(d)
            if p.path not in ps.by_path and p.start <= cfg.end and cfg.start <= p.end:
                ps.add(p)
    if "day" in g:
        for d in daterange(cfg.start, cfg.end):
            ps.add(day_period(d))
    calendar_links(ps)
    return ps


def calendar_parent(ps: Periods, p: Period) -> Optional[Period]:
    """The next generated calendar kind up the chain day → month → quarter → year."""
    chain = [k for k in CALENDAR_KINDS if k in ps.cfg.granularity]
    i = chain.index(p.kind)
    for k in chain[i + 1:]:
        mk = {"month": month_period, "quarter": quarter_period, "year": year_period}[k]
        q = ps.get(mk(p.start).path)
        if q is not None:
            return q
    return None


def smallest_container(family: List[Period], p: Period) -> Optional[Period]:
    found = [f for f in family if f.contains(p)]
    return min(found, key=lambda f: (f.end - f.start, f.path)) if found else None


def calendar_links(ps: Periods) -> None:
    """Write each isSubperiodOf once, from the largest calendar period that fits.

    Calendar periods chain day → month → quarter → year, and days link to their
    ISO week. Fiscal quarters link to their fiscal year. For each fiscal
    calendar and each season scheme, a calendar period links to the smallest
    of that family's periods containing it, unless its calendar parent already
    links there. So with an April fiscal year, 2025 Q4 links to FY2026 Q3 and
    the days and months under it reach it through the quarter; with
    meteorological seasons, a month links to its season.
    """
    cal = [p for k in CALENDAR_KINDS for p in ps.by_kind[k]]
    for p in cal:
        par = calendar_parent(ps, p)
        if par is not None:
            p.parents.append(par.path)
    if "week" in ps.cfg.granularity:
        for p in ps.by_kind["day"]:
            p.parents.append(week_period(p.start).path)

    families: Dict[str, List[Period]] = {}
    for p in ps.by_path.values():
        if p.family != "calendar":
            families.setdefault(p.family, []).append(p)
    for fam in families.values():
        for fq in (p for p in fam if p.kind == "fiscal_quarter"):
            fy = smallest_container([f for f in fam if f.kind == "fiscal_year"], fq)
            if fy is not None:
                fq.parents.append(fy.path)
        memo: Dict[str, Optional[Period]] = {}
        def container(p: Period) -> Optional[Period]:
            if p.path not in memo:
                memo[p.path] = smallest_container(fam, p)
            return memo[p.path]
        for p in cal:
            c = container(p)
            if c is None:
                continue
            par = calendar_parent(ps, p)
            if par is not None and container(par) is c:
                continue
            p.parents.append(c.path)


# ── Turtle ──────────────────────────────────────────────────────────────────

def lit(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def iri(cfg: Config, path_or_iri: str) -> str:
    """Relative to @base when it is one of ours, else absolute."""
    if "://" in path_or_iri:
        rel = path_or_iri[len(cfg.base):] if path_or_iri.startswith(cfg.base) else None
        return f"<{rel}>" if rel is not None else f"<{path_or_iri}>"
    return f"<{path_or_iri}>"


def block(subject: str, pairs: List[Tuple[str, List[str]]]) -> str:
    lines = [subject]
    pairs = [(p, os_) for p, os_ in pairs if os_]
    for i, (pred, objs) in enumerate(pairs):
        end = " ." if i == len(pairs) - 1 else " ;"
        lines.append(f"    {pred} {' , '.join(objs)}{end}")
    return "\n".join(lines)


def to_turtle(cfg: Config, ps: Periods) -> str:
    blocks: List[Tuple[str, str]] = []
    abs_ = lambda p: p if "://" in p else cfg.base + p

    schemes = {}
    for o in cfg.orgs:
        org_pairs = [("a", ["loze:Organisation"])]
        if o.label:
            org_pairs.append(("rdfs:label", [lit(o.label)]))
        org_pairs.append(("loze:hasFiscalCalendar", [iri(cfg, f"fiscal/{o.id}/calendar")]))
        blocks.append((abs_(o.iri), block(iri(cfg, o.iri), org_pairs)))
        cal_pairs = [
            ("a", ["loze:FiscalCalendar"]),
            ("rdfs:label", [lit(f"{o.label or o.id} fiscal calendar")]),
            ("loze:isFiscalCalendarOf", [iri(cfg, o.iri)]),
            ("loze:hasFiscalYearStart", [f'"--{o.fy_month:02d}-{o.fy_day:02d}"^^xsd:gMonthDay']),
            ("loze:namesFiscalYearBy", [lit(o.label_by)]),
            ("loze:usesSeasonScheme", [iri(cfg, f"season/{o.scheme}")] if o.scheme else []),
        ]
        path = f"fiscal/{o.id}/calendar"
        blocks.append((abs_(path), block(iri(cfg, path), cal_pairs)))
        if o.scheme:
            schemes[o.scheme] = o

    for scheme, o in schemes.items():
        path = f"season/{scheme}"
        pairs = [
            ("a", ["loze:SeasonScheme"]),
            ("rdfs:label", [lit(f"{o.season_method} seasons, {o.hemisphere}ern hemisphere")]),
            ("loze:hasSeasonMethod", [lit(o.season_method)]),
            ("loze:hasHemisphere", [lit(o.hemisphere)]),
        ]
        if o.season_method == "astronomical":
            pairs.append(("rdfs:comment", [lit(
                "Approximate: equinoxes and solstices fixed at 20 March, 21 June, "
                "22 September and 21 December every year")]))
        blocks.append((abs_(path), block(iri(cfg, path), pairs)))

    for p in ps.by_path.values():
        pairs = [
            ("a", [f"loze:{CLASS[p.kind]}"]),
            ("rdfs:label", [lit(p.label)]),
            ("loze:hasStartDate", [f'"{p.start.isoformat()}"^^xsd:date']),
            ("loze:hasEndDate", [f'"{p.end.isoformat()}"^^xsd:date']),
            ("loze:isSubperiodOf", [iri(cfg, x) for x in sorted(set(p.parents))]),
            ("loze:isDelimitedBy", [iri(cfg, p.delimiter)] if p.delimiter else []),
        ]
        blocks.append((abs_(p.path), block(iri(cfg, p.path), pairs)))

    head = (
        "# Generated by calendar-periods/generate_periods.py from loze's suggested\n"
        "# calendar extension. Regenerate rather than edit.\n"
        f"@base <{cfg.base}> .\n"
        f"@prefix loze: <{LOZE}> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
    )
    body = "\n\n".join(b for _, b in sorted(blocks, key=lambda x: x[0]))
    return head + "\n" + body + "\n"


def generate(data: dict) -> str:
    cfg = load_config(data)
    return to_turtle(cfg, build_periods(cfg))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("config", help="YAML configuration, see calendar-periods/example.yaml")
    ap.add_argument("-o", "--output", help="write here instead of stdout")
    a = ap.parse_args(argv)
    with open(a.config, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    try:
        out = generate(data)
    except (ValueError, KeyError) as err:
        print(f"{a.config}: {err}", file=sys.stderr)
        return 2
    if a.output:
        with open(a.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(out)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
