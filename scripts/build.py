#!/usr/bin/env python3
"""Publish loze as dereferenceable documents under https://loze-ontology.org/.

    python3 scripts/build.py

Cribbed from mustrd's scripts/build.py, which does the same job for
https://mustrd.org/. Two things differ, and both come from loze's namespace shape.

WHY THIS IS NOT JUST mustrd's SCRIPT. mustrd's namespaces are
`https://mustrd.org/<slug>/`, so a term lives *under* a slug and the slug is a
tidy directory. loze's foundation namespace is the bare domain root, so its 100
terms sit directly at `/`:

    https://loze-ontology.org/Entity
    https://loze-ontology.org/temporal-relations      <- a module, same level

Terms and modules share one flat path space. Nothing collides today (terms are
CamelCase, modules kebab-case) but there is no structural guarantee, so the build
asserts it rather than trusting it — see check_no_collisions().

That shape decides the output: every term needs its own document, because
`/Entity` has to resolve to something. 100 static files, which is what
schema.org and dcterms do for exactly this reason. A hash namespace
(`/loze#Entity`) would have needed one file; that ship sailed when the IRIs were
minted, and re-cutting them now would be a second rename for no gain.

    docs/index.html                     the foundation, served at /
    docs/loze.ttl|.rdf|.jsonld|.nt      the whole union, all five modules
    docs/<module>.html + serialisations one per module
    docs/<Term>.html                    one per term, 100 of them
    docs/_headers                        content types + caching

Cloudflare Pages serves `<name>.html` at `/<name>`, which is what makes the term
IRIs resolve without a Function. mustrd's script records why a Function cannot do
it: a static asset at the same path always wins, so the Function is never
reached. RDF stays available at `/<name>.ttl` and is advertised from every page
with <link rel="alternate">.

Styling follows the Semantic Partners design system as shipped in
operational-overlord (src/app/globals.css, tailwind.config.ts): ink/off-white
surfaces, one green accent, square corners, Plus Jakarta Sans / DM Sans / DM Mono,
and the reserved graph-node triad — class blue, instance green, property amber —
which is the one place a colour here carries meaning rather than decoration.
"""

from __future__ import annotations

import html as html_mod
import shutil
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
NS = "https://loze-ontology.org/"

# slug -> source file. "" is the foundation, which is the namespace root itself.
MODULES: list[tuple[str, str]] = [
    ("", "loze-foundation.ttl"),
    ("artefacts-information-and-instructions", "artefacts-information-and-instructions.ttl"),
    ("materials-and-composition", "materials-and-composition.ttl"),
    ("temporal-relations", "temporal-relations.ttl"),
    ("suggested-social-extension", "suggested-social-extension.ttl"),
]

SERIALISATIONS = [("ttl", "turtle"), ("rdf", "xml"), ("jsonld", "json-ld"), ("nt", "nt")]

e = html_mod.escape


def local(iri: str) -> str:
    s = str(iri)
    for sep in ("#", "/"):
        if sep in s:
            return s.rsplit(sep, 1)[1] or s
    return s


# ── The Semantic Partners design system, ported ──────────────────────────────
# Values copied from operational-overlord src/app/globals.css rather than
# re-picked by eye. HSL channel triplets throughout, so the dark block re-points
# the semantic aliases and nothing below has to be restyled — the same move
# `.s-dark` makes in the app.
#
# Deviations from the app, and why:
#   - no --ui-scale lever. That is a signed-in preference with localStorage; a
#     static ontology page has nobody to remember. --root-step by viewport stays,
#     because it costs one media query and does most of the work.
#   - dark comes from prefers-color-scheme, not a scope class. There is no
#     chrome here to spend an ink budget on, and a docs page read at night should
#     not need a toggle it has no way to persist.
CSS = """
:root {
  --clr-ink: 220 25% 7%;
  --clr-ink-mid: 216 29% 15%;
  --clr-white: 0 0% 100%;
  --clr-off-white: 80 11% 96%;
  --clr-border: 80 6% 89%;
  --clr-border-mid: 80 5% 81%;
  --clr-grey-400: 140 3% 61%;
  --clr-grey-600: 168 4% 37%;
  --clr-faint-on-light: 173 3% 45%;
  --clr-faint-on-ink: 144 2% 48%;
  --clr-green: 160 96% 30%;
  --clr-green-light: 158 65% 52%;
  --clr-green-tint: 151 80% 96%;

  /* Reserved for data visualisation. The one place colour means something here:
     a blue chip is a class, green an individual, amber a property. Never a
     status, never decoration. */
  --clr-node-class: 199 89% 48%;
  --clr-node-instance: 158 65% 52%;
  --clr-node-property: 45 93% 47%;

  --background: var(--clr-white);
  --foreground: var(--clr-ink);
  --surface: var(--clr-off-white);
  --muted-foreground: var(--clr-grey-600);
  --faint: var(--clr-faint-on-light);
  --border: var(--clr-border);
  --border-emphasis: var(--clr-border-mid);
  --brand-accent: var(--clr-green);
  --tint: var(--clr-green-tint);

  --radius: 0px;            /* sharp corners are the brand */
  --radius-pill: 9999px;    /* the only round thing */

  --fs-h1: 3rem; --fs-h2: 2.25rem; --fs-h3: 1.5rem; --fs-h4: 1.25rem;
  --fs-body-lg: 1.125rem; --fs-sm: 0.875rem; --fs-xs: 0.75rem; --fs-2xs: 0.6875rem;
  --tracking-label: 0.16em;
  --ease-brand: cubic-bezier(0.16, 1, 0.3, 1);

  --measure: 68ch;
  --root-step: 100%;
}
@media (min-width: 1920px) { :root { --root-step: 106.25%; } }
@media (min-width: 2560px) { :root { --root-step: 112.5%; } }

/* Percentage, not px: 100% resolves against the reader's own browser default,
   so someone who set 20px gets 20px. An absolute 16px would silently override
   exactly the preference this is meant to respect. */
html { font-size: var(--root-step); }

@media (prefers-color-scheme: dark) {
  :root {
    --background: var(--clr-ink);
    --foreground: 0 0% 100%;
    --surface: var(--clr-ink-mid);
    --muted-foreground: var(--clr-grey-400);
    --faint: var(--clr-faint-on-ink);
    --border: 216 20% 22%;
    --border-emphasis: 216 18% 30%;
    /* #059669 fails contrast on ink; the light green is the token for dark. */
    --brand-accent: var(--clr-green-light);
    --tint: 216 29% 18%;
  }
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: hsl(var(--background));
  color: hsl(var(--foreground));
  font-family: "DM Sans", ui-sans-serif, system-ui, -apple-system, sans-serif;
  font-weight: 400;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4 {
  font-family: "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif;
  font-weight: 700;
  line-height: 1.1;
  margin: 0;
}
h1 { font-size: var(--fs-h1); letter-spacing: -0.04em; }
h2 { font-size: var(--fs-h2); letter-spacing: -0.02em; }
h3 { font-size: var(--fs-h3); letter-spacing: -0.01em; }
h4 { font-size: var(--fs-h4); }
code, .mono { font-family: "DM Mono", ui-monospace, SFMono-Regular, monospace; }
a { color: hsl(var(--brand-accent)); text-decoration: none; }
a:hover { text-decoration: underline; }

.wrap { max-width: 78rem; margin: 0 auto; padding: 0 2rem; }
.measure { max-width: var(--measure); }

header.top {
  border-bottom: 1px solid hsl(var(--border));
  background: hsl(var(--surface));
  padding: 3.5rem 0 2.5rem;
}
.eyebrow {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-2xs);
  letter-spacing: var(--tracking-label);
  text-transform: uppercase;
  color: hsl(var(--muted-foreground));
  margin-bottom: 0.75rem;
}
.lead { font-size: var(--fs-body-lg); font-weight: 300; color: hsl(var(--foreground)); margin: 1rem 0 0; }
.iri {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-sm);
  color: hsl(var(--muted-foreground));
  margin-top: 1.25rem;
  word-break: break-all;
}

/* Format links. Square, hairline, mono — the same register as the app's dense
   table chrome, because that is what these are: data affordances, not buttons. */
.formats { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1.5rem; }
.formats a {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-xs);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border: 1px solid hsl(var(--border-emphasis));
  border-radius: var(--radius);
  padding: 0.4rem 0.75rem;
  color: hsl(var(--foreground));
  transition: border-color 150ms var(--ease-brand), color 150ms var(--ease-brand);
}
.formats a:hover { border-color: hsl(var(--brand-accent)); color: hsl(var(--brand-accent)); text-decoration: none; }

main { padding: 3rem 0 5rem; }
section + section { margin-top: 3.5rem; }
.section-head {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-2xs);
  letter-spacing: var(--tracking-label);
  text-transform: uppercase;
  color: hsl(var(--muted-foreground));
  border-bottom: 1px solid hsl(var(--border));
  padding-bottom: 0.5rem;
  margin-bottom: 1.5rem;
}
.grid { display: grid; gap: 1px; background: hsl(var(--border)); border: 1px solid hsl(var(--border)); grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr)); }
.cell { background: hsl(var(--background)); padding: 1.25rem; }
.cell h4 { margin-bottom: 0.35rem; }
.cell p { margin: 0; font-size: var(--fs-sm); color: hsl(var(--muted-foreground)); }

/* The node triad, used only here. */
.kind {
  display: inline-block;
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-2xs);
  letter-spacing: var(--tracking-label);
  text-transform: uppercase;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-pill);
  border: 1px solid;
}
.kind-class    { color: hsl(var(--clr-node-class));    border-color: hsl(var(--clr-node-class) / 0.4);    background: hsl(var(--clr-node-class) / 0.08); }
.kind-property { color: hsl(var(--clr-node-property)); border-color: hsl(var(--clr-node-property) / 0.4); background: hsl(var(--clr-node-property) / 0.08); }
.kind-instance { color: hsl(var(--clr-node-instance)); border-color: hsl(var(--clr-node-instance) / 0.4); background: hsl(var(--clr-node-instance) / 0.08); }

dl.props { display: grid; grid-template-columns: minmax(9rem, auto) 1fr; gap: 0.5rem 1.5rem; margin: 0; font-size: var(--fs-sm); }
dl.props dt { font-family: "DM Mono", ui-monospace, monospace; font-size: var(--fs-xs); letter-spacing: 0.04em; color: hsl(var(--muted-foreground)); }
dl.props dd { margin: 0; }

footer.bot {
  border-top: 1px solid hsl(var(--border));
  padding: 2.5rem 0 4rem;
  font-size: var(--fs-sm);
  color: hsl(var(--muted-foreground));
}
footer.bot .measure p { margin: 0 0 0.75rem; }
"""


FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&'
    'family=Plus+Jakarta+Sans:wght@700;800&display=swap">'
)


def shell(title: str, alternates: str, body: str) -> str:
    """One page. `alternates` advertises the RDF for this document.

    The <link rel="alternate"> lines are the only content negotiation there is:
    a static asset always beats a Pages Function at the same path, so the RDF
    cannot be served from the HTML's own URL. Advertising it is honest and works
    with every RDF client that follows links; pretending to negotiate would not.
    """
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<!-- GENERATED by scripts/build.py from the .ttl sources. Do not edit. -->
{FONTS}
{alternates}
<style>{CSS}</style>
</head>
<body>
{body}
<footer class="bot"><div class="wrap measure">
  <p>loze is a top-level ontology after E. J. Lowe's four-category ontology, with
  Zemach's schematic particulars. Every term here is identified by an IRI under
  <code>{NS}</code>.</p>
  <p>Generated from the Turtle in
  <a href="https://github.com/Semantic-partners/loze">Semantic-partners/loze</a>.
  The Turtle is the source of truth; this page is a view of it.</p>
</div></footer>
</body>
</html>
"""


def alternates_for(slug: str) -> str:
    """RDF links for a module. Terms point at the union, since a term's
    description is spread across whichever modules mention it."""
    base = slug or "loze"
    types = [("ttl", "text/turtle"), ("rdf", "application/rdf+xml"),
             ("jsonld", "application/ld+json"), ("nt", "application/n-triples")]
    return "\n".join(
        f'<link rel="alternate" type="{mt}" href="/{base}.{ext}">' for ext, mt in types
    )


def formats_for(slug: str) -> str:
    base = slug or "loze"
    return '<div class="formats">' + "".join(
        f'<a href="/{base}.{ext}">{ext}</a>' for ext, _ in SERIALISATIONS
    ) + "</div>"


def kind_of(g: Graph, s: URIRef) -> tuple[str, str]:
    """(css class, label). The node triad is reserved for exactly this."""
    types = set(g.objects(s, RDF.type))
    if OWL.Class in types or RDFS.Class in types:
        return "kind-class", "Class"
    if types & {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty,
                RDF.Property, OWL.TransitiveProperty, OWL.SymmetricProperty}:
        return "kind-property", "Property"
    return "kind-instance", "Individual"


def describe(g: Graph, s: URIRef) -> dict:
    label = g.value(s, RDFS.label)
    definition = g.value(s, SKOS.definition) or g.value(s, RDFS.comment)
    note = g.value(s, SKOS.note)
    css, kind = kind_of(g, s)
    return {
        "iri": str(s), "name": local(s),
        "label": str(label) if label else local(s),
        "definition": str(definition) if definition else "",
        "note": str(note) if note else "",
        "css": css, "kind": kind,
    }


def rel_rows(g: Graph, s: URIRef, defined_in: str | None) -> str:
    """Selected relations, as links where the target is a loze term."""
    def link(o):
        if isinstance(o, URIRef) and str(o).startswith(NS):
            return f'<a href="/{e(local(o))}"><code>{e(local(o))}</code></a>'
        if isinstance(o, URIRef):
            return f'<code>{e(shorten(str(o)))}</code>'
        return e(str(o))

    rows = []
    for pred, dt in [(RDFS.subClassOf, "subclass of"), (RDFS.subPropertyOf, "subproperty of"),
                     (RDFS.domain, "domain"), (RDFS.range, "range"),
                     (OWL.equivalentClass, "equivalent to"), (OWL.inverseOf, "inverse of"),
                     (OWL.disjointWith, "disjoint with")]:
        vals = [link(o) for o in g.objects(s, pred)]
        if vals:
            rows.append(f"<dt>{dt}</dt><dd>{', '.join(vals)}</dd>")

    # Which module says this? Useful precisely because the terms are flat: the
    # IRI gives no clue which file to open. Passed in rather than rediscovered —
    # doing it here reparsed all five modules once per term, 480 parses a build.
    if defined_in is not None:
        href = "/" if defined_in == "" else f"/{defined_in}"
        name = "foundation" if defined_in == "" else defined_in
        rows.append(f'<dt>defined in</dt><dd><a href="{href}">{e(name)}</a></dd>')
    return "<dl class=\"props\">" + "".join(rows) + "</dl>" if rows else ""


KNOWN = {"http://www.w3.org/2002/07/owl#": "owl", "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
         "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
         "http://www.w3.org/2004/02/skos/core#": "skos",
         "http://www.w3.org/2001/XMLSchema#": "xsd"}


def shorten(iri: str) -> str:
    for ns, pfx in KNOWN.items():
        if iri.startswith(ns):
            return f"{pfx}:{iri[len(ns):]}"
    return iri


def render_term(union: Graph, s: URIRef, defined_in: str | None) -> str:
    d = describe(union, s)
    body = f"""
<header class="top"><div class="wrap">
  <div class="eyebrow">loze</div>
  <h1>{e(d['label'])}</h1>
  <p style="margin:.75rem 0 0"><span class="kind {d['css']}">{e(d['kind'])}</span></p>
  {f'<p class="lead measure">{e(d["definition"])}</p>' if d['definition'] else ''}
  <div class="iri">{e(d['iri'])}</div>
  {formats_for('')}
</div></header>
<main><div class="wrap">
  <section>
    <div class="section-head">In the model</div>
    {rel_rows(union, s, defined_in)}
  </section>
  {f'<section><div class="section-head">Note</div><p class="measure">{e(d["note"])}</p></section>' if d['note'] else ''}
  <section>
    <div class="section-head">Elsewhere</div>
    <p class="measure"><a href="/">All of loze</a></p>
  </section>
</div></main>
"""
    return shell(f"{d['label']} — loze", alternates_for(""), body)


def render_module(slug: str, g: Graph, union: Graph) -> str:
    onto = None
    for s in g.subjects(RDF.type, OWL.Ontology):
        onto = s
        break
    label = str(g.value(onto, RDFS.label) or (slug or "loze")) if onto else (slug or "loze")
    definition = str(g.value(onto, SKOS.definition) or "") if onto else ""

    terms = sorted({s for s in g.subjects() if isinstance(s, URIRef)
                    and str(s).startswith(NS) and str(s) != str(onto)},
                   key=lambda x: local(x).lower())
    cells = []
    for t in terms:
        d = describe(g, t)
        cells.append(
            f'<div class="cell"><span class="kind {d["css"]}">{e(d["kind"])}</span>'
            f'<h4><a href="/{e(d["name"])}">{e(d["label"])}</a></h4>'
            f'<p>{e(d["definition"][:150])}</p></div>')

    modules_nav = ""
    if slug == "":
        links = []
        for s2, _ in MODULES:
            if s2 == "":
                continue
            links.append(f'<div class="cell"><h4><a href="/{e(s2)}">{e(s2)}</a></h4></div>')
        modules_nav = (f'<section><div class="section-head">Modules</div>'
                       f'<div class="grid">{"".join(links)}</div></section>')

    body = f"""
<header class="top"><div class="wrap">
  <div class="eyebrow">Semantic Partners &middot; ontology</div>
  <h1>{e(label)}</h1>
  {f'<p class="lead measure">{e(definition)}</p>' if definition else ''}
  <div class="iri">{e(str(onto) if onto else NS)}</div>
  {formats_for(slug)}
</div></header>
<main><div class="wrap">
  {modules_nav}
  <section>
    <div class="section-head">{len(terms)} terms</div>
    <div class="grid">{"".join(cells)}</div>
  </section>
</div></main>
"""
    return shell(f"{label} — loze", alternates_for(slug), body)


def check_no_collisions(union: Graph) -> None:
    """Terms and module slugs share one flat path space. Assert, do not assume.

    A term named `temporal-relations` would overwrite that module's page, and the
    only symptom would be a page quietly containing the wrong thing. Cheap to
    check, invisible if it ever happened.
    """
    slugs = {s for s, _ in MODULES if s}
    # The module ontology IRIs are themselves subjects under the namespace. They
    # are documents, not terms, and they legitimately own their own path.
    ontologies = {str(o) for o in union.subjects(RDF.type, OWL.Ontology)}
    terms = {local(s) for s in union.subjects()
             if isinstance(s, URIRef) and str(s).startswith(NS)
             and str(s) != NS and str(s) not in ontologies}
    clash = slugs & terms
    if clash:
        raise SystemExit(
            f"REFUSING TO BUILD — term name(s) collide with module slugs: {sorted(clash)}\n"
            "  Both want the same path under the namespace root. Rename one."
        )
    lower = {}
    for t in terms:
        lower.setdefault(t.lower(), []).append(t)
    dupes = {k: v for k, v in lower.items() if len(v) > 1}
    if dupes:
        # Pages is case-insensitive on lookup; two terms differing only by case
        # would resolve to whichever file was written last.
        raise SystemExit(f"REFUSING TO BUILD — terms differing only by case: {dupes}")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    union = Graph()
    per_module: dict[str, Graph] = {}
    for slug, src in MODULES:
        g = Graph(); g.parse(ROOT / src, format="turtle")
        per_module[slug] = g
        union += g

    check_no_collisions(union)

    # The union, under /loze.*, so one fetch gets the whole ontology.
    for ext, fmt in SERIALISATIONS:
        union.serialize(destination=str(OUT / f"loze.{ext}"), format=fmt)

    # Per module: serialisations + a page. The foundation is the namespace root,
    # so its page is index.html and it is served at /.
    for slug, src in MODULES:
        g = per_module[slug]
        base = slug or "loze-foundation"
        for ext, fmt in SERIALISATIONS:
            g.serialize(destination=str(OUT / f"{base}.{ext}"), format=fmt)
        shutil.copy(ROOT / src, OUT / Path(src).name)
        page = render_module(slug, g, union)
        (OUT / ("index.html" if slug == "" else f"{slug}.html")).write_text(page, encoding="utf-8")

    # One document per term, because /Entity has to resolve to something.
    ontologies = {str(o) for o in union.subjects(RDF.type, OWL.Ontology)}
    terms = sorted({s for s in union.subjects()
                    if isinstance(s, URIRef) and str(s).startswith(NS)
                    and str(s) != NS and str(s) not in ontologies},
                   key=lambda x: local(x))
    # term IRI -> the slug of the module that introduces it. First module wins,
    # in MODULES order, so the foundation takes precedence over an extension.
    defined_in: dict[str, str] = {}
    for slug, _ in MODULES:
        for subj in per_module[slug].subjects():
            if isinstance(subj, URIRef) and str(subj).startswith(NS):
                defined_in.setdefault(str(subj), slug)
    for t in terms:
        (OUT / f"{local(t)}.html").write_text(
            render_term(union, t, defined_in.get(str(t))), encoding="utf-8")

    # Content types Pages will not infer, and caching. An ontology is meant to be
    # fetched by machines: .ttl served as text/plain is a parse failure at the
    # other end, and the default octet-stream is worse.
    (OUT / "_headers").write_text(
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Access-Control-Allow-Origin: *\n"
        "\n"
        "/*.ttl\n  Content-Type: text/turtle; charset=utf-8\n"
        "\n/*.nt\n  Content-Type: application/n-triples; charset=utf-8\n"
        "\n/*.rdf\n  Content-Type: application/rdf+xml; charset=utf-8\n"
        "\n/*.jsonld\n  Content-Type: application/ld+json; charset=utf-8\n",
        encoding="utf-8")

    n_terms = len(terms)
    print(f"docs/ — {len(union)} triples, {len(MODULES)} modules, {n_terms} term pages")
    print(f"  union:   /loze.{{{','.join(x for x, _ in SERIALISATIONS)}}}")
    print(f"  root:    /            ({len(per_module['']):>3} triples)")
    for slug, _ in MODULES:
        if slug:
            print(f"  module:  /{slug:<38} ({len(per_module[slug]):>3} triples)")


if __name__ == "__main__":
    main()
