#!/usr/bin/env python3
"""Verify docs/ against the sources. Run after scripts/build.py.

    python3 scripts/check.py

This exists because the checks kept being re-typed at a shell prompt and got
written wrong twice — once counting a CSS rule as if it were a rendered chip, once
testing `/module.ttl` for the existence of `module.ttl.html`. Both reported a
problem that was not there, which is the cheaper failure; the same sloppiness
reports success just as easily. A check worth running is worth committing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from rdflib import Dataset, Graph, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
NS = "https://loze-ontology.org/"
MODULES = [
    ("", "loze-foundation.ttl"),
    ("artefacts-information-and-instructions", "artefacts-information-and-instructions.ttl"),
    ("materials-and-composition", "materials-and-composition.ttl"),
    ("temporal-relations", "temporal-relations.ttl"),
    ("suggested-social-extension", "suggested-social-extension.ttl"),
]
PROP_TYPES = {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty,
              RDF.Property, OWL.TransitiveProperty, OWL.SymmetricProperty}

fails: list[str] = []
def check(ok: bool, msg: str) -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {msg}")
    if not ok:
        fails.append(msg)


def main() -> None:
    if not DOCS.exists():
        sys.exit("docs/ does not exist — run scripts/build.py first.")

    source_union = Graph()
    for _, f in MODULES:
        source_union.parse(ROOT / f, format="turtle")

    print("RDF fidelity")
    for ext, fmt in [("ttl", "turtle"), ("rdf", "xml"), ("jsonld", "json-ld"), ("nt", "nt")]:
        g = Graph(); g.parse(DOCS / f"loze.{ext}", format=fmt)
        check(isomorphic(g, source_union), f"loze.{ext} isomorphic to the source union ({len(g)} triples)")

    print("\nNamed-graph isolation")
    ds = Dataset(); ds.parse(DOCS / "loze.trig", format="trig")
    flat = Graph()
    for s, p, o, _c in ds.quads((None, None, None, None)):
        flat.add((s, p, o))
    check(isomorphic(flat, source_union), f"loze.trig flattens to the source union ({len(flat)} triples)")
    for slug, f in MODULES:
        want = Graph(); want.parse(ROOT / f, format="turtle")
        got = Graph()
        for s, p, o, _c in ds.quads((None, None, None, URIRef(NS + slug))):
            got.add((s, p, o))
        check(isomorphic(got, want), f"graph <{NS + slug}> is exactly {f} ({len(got)} triples)")

    print("\nPer-module serialisations stay per-module")
    for slug, f in MODULES:
        base = slug or "loze-foundation"
        want = Graph(); want.parse(ROOT / f, format="turtle")
        got = Graph(); got.parse(DOCS / f"{base}.ttl", format="turtle")
        check(isomorphic(got, want), f"{base}.ttl is {f} and not the union ({len(got)} triples)")

    print("\nLinks")
    # Two candidate resolutions, because Pages serves <name>.html at /<name>:
    # a literal file, or the .html that stands in for it. Testing only one is the
    # mistake this script was written after.
    missing = []
    for p in sorted(DOCS.glob("*.html")):
        for href in re.findall(r'href="/([^"]*)"', p.read_text(encoding="utf-8")):
            if href.startswith("http"):
                continue
            target = "index.html" if href == "" else href
            if (DOCS / target).exists() or (DOCS / f"{target}.html").exists():
                continue
            missing.append(f"{p.name} -> /{href}")
    check(not missing, f"no broken internal links ({len(missing)} found)")
    for m in missing[:10]:
        print(f"       {m}")

    print("\nEvery term resolves")
    ontologies = {str(o) for o in source_union.subjects(RDF.type, OWL.Ontology)}
    terms = {s for s in source_union.subjects()
             if isinstance(s, URIRef) and str(s).startswith(NS)
             and str(s) != NS and str(s) not in ontologies}
    unresolved = [str(t) for t in terms if not (DOCS / f"{str(t)[len(NS):]}.html").exists()]
    check(not unresolved, f"all {len(terms)} term IRIs have a document ({len(unresolved)} missing)")
    for u in unresolved[:10]:
        print(f"       {u}")

    print("\nKind chips tell the truth")
    def kind_of(t: URIRef) -> str:
        ty = set(source_union.objects(t, RDF.type))
        if OWL.Class in ty or RDFS.Class in ty:
            return "Class"
        if ty & PROP_TYPES:
            return "Property"
        return "Individual"
    wrong = []
    for t in sorted(terms, key=str):
        page = DOCS / f"{str(t)[len(NS):]}.html"
        if not page.exists():
            continue
        m = re.search(r'<span class="kind kind-[a-z]+">([A-Za-z]+)</span>', page.read_text(encoding="utf-8"))
        if m and m.group(1) != kind_of(t):
            wrong.append(f"{page.name}: page says {m.group(1)}, graph says {kind_of(t)}")
    check(not wrong, f"chip matches rdf:type on every term page ({len(wrong)} disagree)")
    for w in wrong[:10]:
        print(f"       {w}")

    print("\nContent types declared")
    headers = (DOCS / "_headers").read_text(encoding="utf-8")
    for ext in ("ttl", "nt", "rdf", "jsonld", "trig", "nq"):
        check(f"/*.{ext}" in headers, f"_headers sets a Content-Type for .{ext}")

    print()
    if fails:
        print(f"{len(fails)} check(s) failed.")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
