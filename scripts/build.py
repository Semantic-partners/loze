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

from rdflib import Dataset, Graph, URIRef
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

# Quad formats, for the union only. Turtle cannot say WHICH module asserts a
# triple; TriG and N-Quads can, and that is the one fact a consumer of the merged
# file otherwise has to guess. Each module is a named graph identified by its own
# ontology IRI, so the graph name is also the document you can go and fetch.
QUAD_SERIALISATIONS = [("trig", "trig"), ("nq", "nquads")]

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

/* The class tree. Rules rather than bullets: the indent is the information, and
   a disc at every level competes with it. */
ul.tree, ul.tree ul { list-style: none; margin: 0; padding: 0; }
ul.tree ul { margin-left: 0.75rem; padding-left: 1rem; border-left: 1px solid hsl(var(--border)); }
ul.tree li { padding: 0.3rem 0; }
ul.tree a { font-weight: 500; }
.tree-def {
  display: inline; margin-left: 0.6rem;
  font-size: var(--fs-sm); color: hsl(var(--faint));
}
@media (max-width: 40rem) { .tree-def { display: none; } }

/* Where a term sits, above its name. */
.trail {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-xs);
  color: hsl(var(--muted-foreground));
  margin-bottom: 0.75rem;
}
.trail span { color: hsl(var(--foreground)); }
.titleline { display: flex; align-items: baseline; gap: 0.9rem; flex-wrap: wrap; }

.chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.chip {
  font-size: var(--fs-sm);
  border: 1px solid hsl(var(--border-emphasis));
  border-radius: var(--radius);
  padding: 0.3rem 0.6rem;
  color: hsl(var(--foreground));
  transition: border-color 150ms var(--ease-brand), color 150ms var(--ease-brand);
}
.chip:hover { border-color: hsl(var(--brand-accent)); color: hsl(var(--brand-accent)); text-decoration: none; }
/* Properties keep the amber of the node triad, quietly — a left edge, not a fill. */
.chip-prop { border-left: 3px solid hsl(var(--clr-node-property) / 0.7); font-family: "DM Mono", ui-monospace, monospace; font-size: var(--fs-xs); }

.domgroup { margin-bottom: 1.5rem; }
.domhead {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-xs);
  letter-spacing: 0.04em;
  color: hsl(var(--muted-foreground));
  margin-bottom: 0.5rem;
}

.modtag {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-2xs);
  letter-spacing: 0.04em;
  color: hsl(var(--muted-foreground));
  border: 1px solid hsl(var(--border));
  padding: 0.05rem 0.35rem;
  margin-left: 0.5rem;
  white-space: nowrap;
}

/* ── The one figure ──────────────────────────────────────────────────────────
   Nodes take their colour from the same triad the chips use, so blue still means
   class and amber still means property — the page teaches the encoding once and
   the diagram spends it. Everything structural is currentColor, so the drawing
   follows the theme instead of carrying a baked palette that only works on one
   ground. Which is also why mustrd's schema_svg was not lifted: graphviz bakes
   hex into the output. */
.fig { margin: 0 0 1rem; }
.fig svg { width: 100%; height: auto; display: block; }
.fig figcaption {
  max-width: var(--measure); margin-top: 1rem;
  font-size: var(--fs-sm); color: hsl(var(--muted-foreground));
}
.fig-panel {
  font-family: "DM Mono", monospace; font-size: 12px;
  letter-spacing: var(--tracking-label); text-transform: uppercase;
  fill: hsl(var(--muted-foreground));
}
.fig-rule { stroke: hsl(var(--border)); stroke-width: 1; }
/* The line the figure is about: which side of it the model sits on IS the
   argument. Drawn stronger than the panel divider for that reason. */
.fig-band { stroke: hsl(var(--border-emphasis)); stroke-width: 1.5; stroke-dasharray: 6 5; }
.fig-band-lab { font-family: "DM Mono", monospace; font-size: 11px;
  letter-spacing: var(--tracking-label); fill: hsl(var(--faint)); }
/* Groups the particulars so one 'a' arrow can stand for all of them — three
   separate arrows converging read as more machinery, not less. */
.grp { fill: none; stroke: hsl(var(--border)); stroke-width: 1; stroke-dasharray: 3 4; }
.fig-note { font-size: 13px; fill: hsl(var(--muted-foreground)); }

.n-class { fill: hsl(var(--clr-node-class) / 0.10); stroke: hsl(var(--clr-node-class)); stroke-width: 1.5; }
.n-inst  { fill: hsl(var(--clr-node-instance) / 0.12); stroke: hsl(var(--clr-node-instance)); stroke-width: 1.5; }
/* The schematic one is the claim, so it is the only node drawn heavier. */
.n-schem { stroke-width: 3; }
.n-lab  { font-family: "DM Sans", sans-serif; font-size: 14px; font-weight: 500;
          fill: hsl(var(--foreground)); text-anchor: middle; }
.n-sm  { font-size: 13px; }
.n-kind { font-family: "DM Mono", monospace; font-size: 11px;
          fill: hsl(var(--faint)); text-anchor: middle; }

.e-base { stroke: currentColor; stroke-width: 1.4; opacity: 0.55; fill: none; }
.e-prop { stroke: hsl(var(--clr-node-property)); stroke-width: 2; fill: none; }
.e-lab  { font-family: "DM Mono", monospace; font-size: 11px; fill: hsl(var(--muted-foreground)); }
.e-lab-prop { fill: hsl(var(--clr-node-property)); }

footer.bot {
  border-top: 1px solid hsl(var(--border));
  padding: 2.5rem 0 4rem;
  font-size: var(--fs-sm);
  color: hsl(var(--muted-foreground));
}
footer.bot .measure p { margin: 0 0 0.75rem; }
"""


FIGURE = '''
<figure class="fig">
<svg viewBox="0 0 960 380" role="img" xmlns="http://www.w3.org/2000/svg"
     aria-label="A line divides classes above from particulars below. Without a schematic particular, the work Toyota Corolla sits above the line with the classes, separated from its own performances. With one, the work sits below the line among the particulars, alongside the performances that concretize it.">
  <defs>
    <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/>
    </marker>
  </defs>

  <!-- The one line the whole figure is about -->
  <line class="fig-band" x1="0" y1="196" x2="960" y2="196"/>
  <text class="fig-band-lab" x="0" y="72">CLASSES</text>
  <text class="fig-band-lab" x="0" y="240">PARTICULARS</text>

  <text class="fig-panel" x="150" y="24">Without a schematic particular</text>
  <text class="fig-panel" x="590" y="24">With one</text>
  <line class="fig-rule" x1="510" y1="44" x2="510" y2="356"/>

  <!-- LEFT: the work is stranded above the line -->
  <rect class="n-class" x="150" y="52" width="170" height="40"/>
  <text class="n-lab" x="235" y="77">Car</text>

  <rect class="n-class" x="150" y="128" width="170" height="40"/>
  <text class="n-lab" x="235" y="153">Toyota Corolla</text>

  <line class="e-base" x1="235" y1="128" x2="235" y2="96" marker-end="url(#ar)"/>
  <text class="e-lab" x="246" y="118">subClassOf</text>

  <rect class="grp" x="120" y="266" width="246" height="62"/>
  <rect class="n-inst" x="132" y="278" width="102" height="38"/>
  <text class="n-lab n-sm" x="183" y="302">my Corolla</text>
  <rect class="n-inst" x="242" y="278" width="112" height="38"/>
  <text class="n-lab n-sm" x="298" y="302">a new one</text>

  <line class="e-base" x1="243" y1="266" x2="243" y2="172" marker-end="url(#ar)"/>
  <text class="e-lab" x="253" y="222">a</text>

  <!-- RIGHT: the work has crossed the line -->
  <rect class="n-class" x="700" y="52" width="170" height="40"/>
  <text class="n-lab" x="785" y="77">Car</text>

  <rect class="grp" x="546" y="252" width="384" height="90"/>
  <rect class="n-inst n-schem" x="562" y="272" width="150" height="50"/>
  <text class="n-lab n-sm" x="637" y="295">Toyota Corolla</text>
  <text class="n-kind" x="637" y="312">schematic</text>

  <rect class="n-inst" x="762" y="266" width="150" height="30"/>
  <text class="n-lab n-sm" x="837" y="286">my Corolla</text>
  <rect class="n-inst" x="762" y="304" width="150" height="30"/>
  <text class="n-lab n-sm" x="837" y="324">a new one</text>

  <line class="e-prop" x1="762" y1="281" x2="716" y2="291" marker-end="url(#ar)"/>
  <line class="e-prop" x1="762" y1="319" x2="716" y2="305" marker-end="url(#ar)"/>

  <line class="e-base" x1="738" y1="252" x2="785" y2="96" marker-end="url(#ar)"/>
  <text class="e-lab" x="752" y="180">a</text>

  <text class="fig-note" x="150" y="360">The model is a class, so it cannot carry a wheelbase or a</text>
  <text class="fig-note" x="150" y="376">kerb weight without being punned as an individual too.</text>
  <text class="fig-note" x="590" y="360">The model is a particular. It carries its own specification,</text>
  <text class="fig-note" x="590" y="376">and sets the benchmark its units are measured against.</text>
</svg>
<figcaption>One line, two layers. On the left the work is stuck above it, a different kind of
thing from the performances it governs. On the right it has crossed: <code>Toyota Corolla</code>
and a performance of it are both particulars, both <code>a Car</code>, differing only in
that one is repeatable and the others are not. The amber arrows are
<code>isConcretizationOf</code>.</figcaption>
</figure>
'''


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
<link rel="stylesheet" href="/style.css">
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


def formats_for(slug: str, quads: bool = False) -> str:
    """Quads are offered only where they say something: the union, where the graph
    name records which module asserts each statement. For a single module they
    would be Turtle in a wrapper."""
    base = slug or "loze"
    items = [f'<a href="/{base}.{ext}">{ext}</a>' for ext, _ in SERIALISATIONS]
    if quads:
        items += [f'<a href="/loze.{ext}" title="quads — keeps the module each '
                  f'statement came from">{ext}</a>' for ext, _ in QUAD_SERIALISATIONS]
    return '<div class="formats">' + "".join(items) + "</div>"


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


PROP_TYPES = {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty,
              RDF.Property, OWL.TransitiveProperty, OWL.SymmetricProperty}


def term_link(g: Graph, o) -> str:
    if isinstance(o, URIRef) and str(o).startswith(NS):
        lbl = g.value(o, RDFS.label)
        return f'<a href="/{e(local(o))}">{e(str(lbl) if lbl else local(o))}</a>'
    if isinstance(o, URIRef):
        return f'<code>{e(shorten(str(o)))}</code>'
    return e(str(o))


def ancestors(g: Graph, s: URIRef) -> list[URIRef]:
    """Superclass chain to the root, nearest first. Cycles cannot loop it."""
    out, seen, cur = [], {s}, s
    while True:
        nxt = None
        for o in g.objects(cur, RDFS.subClassOf):
            if isinstance(o, URIRef) and str(o).startswith(NS) and o not in seen:
                nxt = o
                break
        if nxt is None:
            return out
        out.append(nxt); seen.add(nxt); cur = nxt


def class_tree(g: Graph, root: URIRef, classes: set, depth: int = 0, seen=None, tags=None) -> str:
    """The four-category structure, which is the reason to read this ontology at
    all. A flat alphabetical list of 27 classes hides exactly what makes loze
    different from a vocabulary."""
    seen = seen if seen is not None else set()
    if root in seen or depth > 8:
        return ""
    seen.add(root)
    d = describe(g, root)
    kids = sorted([c for c in g.subjects(RDFS.subClassOf, root) if c in classes],
                  key=lambda x: local(x).lower())
    inner = "".join(class_tree(g, k, classes, depth + 1, seen, tags) for k in kids)
    tag = ""
    if tags:
        mod = tags.get(str(root))
        if mod:
            tag = f'<span class="modtag">{e(mod)}</span>'
    return (f'<li><a href="/{e(d["name"])}">{e(d["label"])}</a>{tag}'
            f'<span class="tree-def">{e(d["definition"][:90])}</span>'
            + (f"<ul>{inner}</ul>" if inner else "") + "</li>")


def section(head: str, inner: str) -> str:
    return f'<section><div class="section-head">{e(head)}</div>{inner}</section>' if inner else ""


def render_term(union: Graph, s: URIRef, defined_in: str | None) -> str:
    d = describe(union, s)
    classes = {c for c in union.subjects(RDF.type, OWL.Class) if str(c).startswith(NS)}
    is_prop = bool(set(union.objects(s, RDF.type)) & PROP_TYPES)

    # Up the tree, as a trail. Where a term sits matters more than its label.
    chain = ancestors(union, s)
    trail = ""
    if chain:
        parts = " / ".join(term_link(union, a) for a in reversed(chain))
        trail = f'<div class="trail">{parts} / <span>{e(d["label"])}</span></div>'

    rows = []
    for pred, dt in [(RDFS.subClassOf, "specialises"), (RDFS.subPropertyOf, "subproperty of"),
                     (RDFS.domain, "domain"), (RDFS.range, "range"),
                     (OWL.equivalentClass, "equivalent to"), (OWL.inverseOf, "inverse of"),
                     (OWL.disjointWith, "disjoint with")]:
        vals = [term_link(union, o) for o in union.objects(s, pred)]
        if vals:
            rows.append(f"<dt>{dt}</dt><dd>{', '.join(vals)}</dd>")
    types = [shorten(str(t)) for t in union.objects(s, RDF.type)]
    if types:
        rows.append(f"<dt>type</dt><dd><code>{e(', '.join(sorted(types)))}</code></dd>")
    if defined_in is not None:
        href = "/" if defined_in == "" else f"/{defined_in}"
        name = "foundation" if defined_in == "" else defined_in
        rows.append(f'<dt>defined in</dt><dd><a href="{href}">{e(name)}</a></dd>')
    props_dl = f'<dl class="props">{"".join(rows)}</dl>' if rows else ""

    # Down the tree, and the properties that reach this class. Without these a
    # term page is a dead end: you can climb but never explore.
    subs = sorted([c for c in union.subjects(RDFS.subClassOf, s) if c in classes],
                  key=lambda x: local(x).lower())
    subs_html = ('<div class="chips">' + "".join(
        f'<a class="chip" href="/{e(local(c))}">{e(str(union.value(c, RDFS.label) or local(c)))}</a>'
        for c in subs) + "</div>") if subs else ""

    def props_where(pred):
        got = sorted({p for p in union.subjects(pred, s)
                      if set(union.objects(p, RDF.type)) & PROP_TYPES},
                     key=lambda x: local(x).lower())
        return ('<div class="chips">' + "".join(
            f'<a class="chip chip-prop" href="/{e(local(p))}">{e(str(union.value(p, RDFS.label) or local(p)))}</a>'
            for p in got) + "</div>") if got else ""

    body = f"""
<header class="top"><div class="wrap">
  {trail}
  <div class="titleline">
    <h1>{e(d['label'])}</h1>
    <span class="kind {d['css']}">{e(d['kind'])}</span>
  </div>
  {f'<p class="lead measure">{e(d["definition"])}</p>' if d['definition'] else ''}
  <div class="iri">{e(d['iri'])}</div>
  {formats_for('')}
</div></header>
<main><div class="wrap">
  {section("In the model", props_dl)}
  {section("Specialised by", subs_html)}
  {"" if is_prop else section("Properties from this", props_where(RDFS.domain))}
  {"" if is_prop else section("Properties onto this", props_where(RDFS.range))}
  {FIGURE if d['name'] in ("SchematicParticular", "isConcretizationOf", "hasConcretization") else ""}
  {section("Note", f'<p class="measure">{e(d["note"])}</p>' if d['note'] else "")}
</div></main>
"""
    return shell(f"{d['label']} — loze", alternates_for(""), body)


def render_module(slug: str, g: Graph, union: Graph, defined_in: dict | None = None) -> str:
    onto = next(iter(g.subjects(RDF.type, OWL.Ontology)), None)
    label = str(g.value(onto, RDFS.label) or (slug or "loze")) if onto else (slug or "loze")
    definition = str(g.value(onto, SKOS.definition) or "") if onto else ""

    own = sorted({s for s in g.subjects() if isinstance(s, URIRef)
                  and str(s).startswith(NS) and s != onto},
                 key=lambda x: local(x).lower())
    classes_all = {c for c in union.subjects(RDF.type, OWL.Class) if str(c).startswith(NS)}
    own_classes = [t for t in own if t in classes_all]
    own_props = [t for t in own if set(union.objects(t, RDF.type)) & PROP_TYPES]

    # The hierarchy. On the root page show ALL of it, not just the foundation's
    # own 15 of 27: every extension class is a subclass of a foundation one, so
    # the tree from Entity reaches them naturally, and hiding them behind module
    # links makes the front page a worse map of the ontology than the ontology is.
    # The serialisations stay exactly this module — only the HTML view is wider,
    # and each borrowed class is tagged with where it is actually defined.
    tree_classes = classes_all if slug == "" else set(own_classes)
    tags = None
    if slug == "" and defined_in:
        tags = {k: v for k, v in defined_in.items() if v}
    roots = [c for c in tree_classes
             if not any(o in tree_classes for o in union.objects(c, RDFS.subClassOf))]
    tree = ""
    if tree_classes:
        tree = ('<ul class="tree">' +
                "".join(class_tree(union, r, tree_classes, tags=tags)
                        for r in sorted(roots, key=lambda x: local(x).lower())) +
                "</ul>")

    # Properties read best grouped by what they start from.
    by_domain: dict[str, list] = {}
    for p in own_props:
        doms = [o for o in union.objects(p, RDFS.domain) if isinstance(o, URIRef)]
        key = local(doms[0]) if doms else "—"
        by_domain.setdefault(key, []).append(p)
    prop_html = ""
    if by_domain:
        blocks = []
        for dom in sorted(by_domain):
            chips = "".join(
                f'<a class="chip chip-prop" href="/{e(local(p))}">{e(str(union.value(p, RDFS.label) or local(p)))}</a>'
                for p in sorted(by_domain[dom], key=lambda x: local(x).lower()))
            head = (f'<a href="/{e(dom)}">{e(dom)}</a>' if dom != "—" else "no declared domain")
            blocks.append(f'<div class="domgroup"><div class="domhead">from {head}</div>'
                          f'<div class="chips">{chips}</div></div>')
        prop_html = "".join(blocks)

    modules_nav = ""
    if slug == "":
        cells = "".join(
            f'<div class="cell"><h4><a href="/{e(s2)}">{e(s2.replace("-", " "))}</a></h4>'
            f'<p>{len([x for x in Graph().parse(ROOT / src2, format="turtle").subjects()])} statements</p></div>'
            for s2, src2 in MODULES if s2)
        modules_nav = section("Modules", f'<div class="grid">{cells}</div>')

    schematic_section = section("Why a schematic particular", FIGURE)

    body = f"""
<header class="top"><div class="wrap">
  <div class="eyebrow">Semantic Partners &middot; ontology</div>
  <h1>{e(label)}</h1>
  {f'<p class="lead measure">{e(definition)}</p>' if definition else ''}
  <div class="iri">{e(str(onto) if onto else NS)}</div>
  {formats_for(slug, quads=(slug == ''))}
</div></header>
<main><div class="wrap">
  {schematic_section if slug == "" else ""}
  {modules_nav}
  {section(f"{len(tree_classes)} classes", tree)}
  {section(f"{len(own_props)} properties", prop_html)}
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

    # One named graph per source file, named by that module's ontology IRI. Two
    # things follow, and both were previously reconstructed by hand:
    #   - "which module says this" is a quad lookup, not a re-parse of five files
    #     followed by a first-wins guess;
    #   - the merged download can be published as quads, keeping that provenance
    #     instead of flattening it away.
    # default_union=True so the dataset reads as the whole graph when nothing
    # names a context, which is what every renderer wants.
    ds = Dataset(default_union=True)
    per_module: dict[str, Graph] = {}
    for slug, src in MODULES:
        g = ds.graph(URIRef(NS + slug))
        g.parse(ROOT / src, format="turtle")
        per_module[slug] = g

    # Assert the graph name and the ontology IRI agree. They are the same string
    # by construction here, but a module whose owl:Ontology said something else
    # would publish a graph named for a document that does not describe it.
    for slug, src in MODULES:
        declared = {str(o) for o in per_module[slug].subjects(RDF.type, OWL.Ontology)}
        if declared and NS + slug not in declared:
            raise SystemExit(
                f"REFUSING TO BUILD — {src} declares {declared} but its graph is "
                f"named <{NS + slug}>. Make the owl:Ontology IRI match the slug."
            )

    union = ds
    check_no_collisions(union)

    # The union, under /loze.*, so one fetch gets the whole ontology. Flattened to
    # a single Graph first: Turtle and friends have no way to express a quad, and
    # serialising a Dataset to them drops everything but the default graph.
    merged = Graph()
    for s_, p_, o_, _c in union.quads((None, None, None, None)):
        merged.add((s_, p_, o_))
    for pfx, ns in union.namespaces():
        merged.bind(pfx, ns, override=False)
    for ext, fmt in SERIALISATIONS:
        merged.serialize(destination=str(OUT / f"loze.{ext}"), format=fmt)

    # And as quads, which keep the module each statement came from — the one thing
    # the flattened download cannot tell you.
    for ext, fmt in QUAD_SERIALISATIONS:
        union.serialize(destination=str(OUT / f"loze.{ext}"), format=fmt)

    # Per module: serialisations + a page. The foundation is the namespace root,
    # so its page is index.html and it is served at /.
    # Straight out of the quads. Ordered by MODULES so the foundation wins when a
    # term is mentioned in more than one graph — mentioned is not defined.
    order = [NS + slug for slug, _ in MODULES]
    defined_in: dict[str, str] = {}
    for subj, _p, _o, ctx in union.quads((None, RDF.type, None, None)):
        if not (isinstance(subj, URIRef) and str(subj).startswith(NS)):
            continue
        cur = defined_in.get(str(subj))
        if cur is None or order.index(str(ctx)) < order.index(NS + cur):
            defined_in[str(subj)] = str(ctx)[len(NS):]

    for slug, src in MODULES:
        g = per_module[slug]
        base = slug or "loze-foundation"
        for ext, fmt in SERIALISATIONS:
            g.serialize(destination=str(OUT / f"{base}.{ext}"), format=fmt)
        shutil.copy(ROOT / src, OUT / Path(src).name)
        page = render_module(slug, g, union, defined_in)
        (OUT / ("index.html" if slug == "" else f"{slug}.html")).write_text(page, encoding="utf-8")

    # One document per term, because /Entity has to resolve to something.
    ontologies = {str(o) for o in union.subjects(RDF.type, OWL.Ontology)}
    terms = sorted({s for s in union.subjects()
                    if isinstance(s, URIRef) and str(s).startswith(NS)
                    and str(s) != NS and str(s) not in ontologies},
                   key=lambda x: local(x))
    for t in terms:
        (OUT / f"{local(t)}.html").write_text(
            render_term(union, t, defined_in.get(str(t))), encoding="utf-8")

    # One stylesheet, not 101 copies. grabbag inlines its CSS on purpose — single
    # file, strict CSP, works from file://. Neither applies here: this is a
    # public multi-page site, so a shared sheet is smaller and the reader fetches
    # it once for the whole ontology instead of per term.
    (OUT / "style.css").write_text(CSS, encoding="utf-8")

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
        "\n/*.jsonld\n  Content-Type: application/ld+json; charset=utf-8\n"
        "\n/*.trig\n  Content-Type: application/trig; charset=utf-8\n"
        "\n/*.nq\n  Content-Type: application/n-quads; charset=utf-8\n",
        encoding="utf-8")

    n_terms = len(terms)
    print(f"docs/ — {len(union)} triples, {len(MODULES)} modules, {n_terms} term pages")
    print(f"  union:   /loze.{{{','.join(x for x, _ in SERIALISATIONS)}}}"
          f"  + quads /loze.{{{','.join(x for x, _ in QUAD_SERIALISATIONS)}}}")
    print(f"  root:    /            ({len(per_module['']):>3} triples)")
    for slug, _ in MODULES:
        if slug:
            print(f"  module:  /{slug:<38} ({len(per_module[slug]):>3} triples)")


if __name__ == "__main__":
    main()
