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

Styling is close to SP's style sheet. green as the main accent, blue is used as a secondary. amber is dropped. 
Typefaces are changed: Archivo for grotesk, Newsreader for serif, DM Mono for code/IRIs.
"""

from __future__ import annotations

import html as html_mod
import os
import re
import sys as _sys

# rdflib's canonicalisation has to break ties between structurally similar blank
# nodes — loze has them inside the owl:unionOf collections — and the tie-break
# follows Python's randomised string hashing, so two runs produce different
# canonical labels. Everything else here is already byte-stable; this is the last
# source of churn, and it has to be fixed before the interpreter starts.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(_sys.executable, [_sys.executable, *_sys.argv])
import shutil
from pathlib import Path

from rdflib import BNode, Dataset, Graph, URIRef
from rdflib.compare import to_canonical_graph
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

def canonical(g: Graph) -> Graph:
    """A graph that serialises to the same bytes every run.

    Two sources of churn. rdflib mints fresh blank node labels on every parse, and
    it does not sort statements — so .rdf, .jsonld, .nt, .trig and .nq all came out
    reordered each build, ~5,500 lines of diff that meant nothing. Turtle happened
    to be stable, which made it easy to miss.

    to_canonical_graph relabels blank nodes from their structure rather than from
    parse order, and inserting the triples sorted pins the serialiser's iteration,
    since rdflib's memory store iterates in insertion order.

    It matters beyond tidiness: without it there is no way to ask "is the published
    output stale?", because a rebuild always differs.
    """
    out = Graph()
    for t in sorted(to_canonical_graph(g), key=lambda x: (str(x[0]), str(x[1]), str(x[2]))):
        out.add(t)
    for pfx, ns in g.namespaces():
        out.bind(pfx, ns, override=False)
    return out


def write_graph(g: Graph, base, ext: str, fmt: str) -> None:
    data = g.serialize(format=fmt)
    # Line-based formats get sorted too: cheap, and it removes any residual
    # ordering the serialiser introduces on its own.
    if ext in ("nt", "nq"):
        data = "".join(sorted(l + "\n" for l in data.splitlines() if l.strip()))
    elif ext == "rdf":
        # RDF/XML emits its subject blocks in store order and their children in
        # set order. Sort both on the parsed tree, which is safe because the
        # document is a flat list of subject descriptions.
        import xml.etree.ElementTree as _ET
        RDFNS = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
        _ET.register_namespace("rdf", RDFNS[1:-1])
        root = _ET.fromstring(data)
        def key(el):
            return (el.tag, el.get(RDFNS + "about", ""), el.get(RDFNS + "resource", ""),
                    (el.text or ""))
        for child in root:
            child[:] = sorted(child, key=key)
        root[:] = sorted(root, key=key)
        _ET.indent(root, space="  ")
        data = _ET.tostring(root, encoding="unicode", xml_declaration=True)
    elif ext == "jsonld":
        # rdflib's JSON-LD serialiser does not order its node array, and object
        # lists inside a node come out in set order. Sort both.
        import json as _json
        doc = _json.loads(data)
        nodes = doc if isinstance(doc, list) else doc.get("@graph", doc)
        if isinstance(nodes, list):
            for n in nodes:
                for k, v in list(n.items()):
                    if isinstance(v, list):
                        n[k] = sorted(v, key=lambda x: _json.dumps(x, sort_keys=True))
            nodes.sort(key=lambda n: str(n.get("@id", "")))
        data = _json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False)
    Path(f"{base}.{ext}").write_text(data, encoding="utf-8")


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
  /* Application status, kept separate from the node triad above even where hues
     would collide. Only the punning mark uses it. */
  --clr-status-danger: 0 62% 50%;
  --clr-status-ok: 160 96% 30%;

  /* The kind pill is small text, and the triad above was picked to sit on a
     tinted fill in a diagram, not to be read. On the light surface all three
     came out between 1.8:1 and 2.6:1 — under half what small text needs, and
     amber on off-white was the worst of them. Same hues, dark enough to read. */
  --kind-class:    205 90% 39%;
  --kind-instance: 160 96% 25%;
  --kind-property:  38 92% 31%;

  --background: var(--clr-white);
  --foreground: var(--clr-ink);
  --surface: var(--clr-off-white);
  --muted-foreground: var(--clr-grey-600);
  --faint: var(--clr-faint-on-light);
  --border: var(--clr-border);
  --border-emphasis: var(--clr-border-mid);
  --brand-accent: var(--clr-green);
  --tint: var(--clr-green-tint);
  /* Turtle literals. Deliberately NOT the link green: a string is not
     clickable, and colouring it like one is a lie. */
  --code-lit: 25 85% 32%;
  --code-kw:  300 55% 38%;   /* a, @prefix */
  --code-pfx: 212 78% 34%;   /* owl:, rdfs:, xsd: and full IRIs */

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
    /* On ink the original triad already clears 5:1, so it stands. */
    --kind-class: var(--clr-node-class);
    --kind-instance: var(--clr-node-instance);
    --kind-property: var(--clr-node-property);
    --code-lit: 25 80% 66%;
    --code-kw:  300 68% 78%;
    --code-pfx: 206 80% 70%;
    --clr-status-ok: 158 65% 52%;
    --tint: 216 29% 18%;
  }
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: hsl(var(--background));
  color: hsl(var(--foreground));
  font-family: "Archivo", ui-sans-serif, system-ui, -apple-system, sans-serif;
  font-weight: 400;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4 {
  font-family: "Archivo", ui-sans-serif, system-ui, sans-serif;
  font-weight: 500;
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
.lead {
  font-family: "Newsreader", ui-serif, Georgia, serif;
  font-size: var(--fs-body-lg); font-weight: 300; font-style: normal;
  color: hsl(var(--foreground)); margin: 1rem 0 0;
}
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
.kind-class    { color: hsl(var(--kind-class));    border-color: hsl(var(--clr-node-class) / 0.4);    background: hsl(var(--clr-node-class) / 0.08); }
.kind-property { color: hsl(var(--kind-property)); border-color: hsl(var(--clr-node-property) / 0.4); background: hsl(var(--clr-node-property) / 0.08); }
.kind-instance { color: hsl(var(--kind-instance)); border-color: hsl(var(--clr-node-instance) / 0.4); background: hsl(var(--clr-node-instance) / 0.08); }

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
/* Every chip on this site is an <a>. Body-text ink made them read as inert
   badges, so nobody clicked them — the accent is what says "this goes somewhere". */
.chip {
  font-size: var(--fs-sm);
  border: 1px solid hsl(var(--border-emphasis));
  border-radius: var(--radius);
  padding: 0.3rem 0.6rem;
  color: hsl(var(--brand-accent));
  transition: border-color 150ms var(--ease-brand), color 150ms var(--ease-brand);
}
.chip:hover { border-color: hsl(var(--brand-accent)); color: hsl(var(--brand-accent)); text-decoration: none; }
/* Properties keep the amber of the node triad, quietly — a left edge, not a fill. */
.chip-prop { border-left: 3px solid hsl(var(--clr-node-property) / 0.7); font-family: "DM Mono", ui-monospace, monospace; font-size: var(--fs-xs); }

/* Site nav. Every page had exactly one way out — the breadcrumb to / — so a
   property page was a dead end. This is the same four links everywhere. */
nav.site {
  border-bottom: 1px solid hsl(var(--border));
  background: hsl(var(--background));
}
nav.site .wrap { display: flex; gap: 1.4rem; align-items: baseline; padding-top: 0.9rem; padding-bottom: 0.9rem; flex-wrap: wrap; }
nav.site a {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-xs);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: hsl(var(--muted-foreground));
  transition: color 150ms var(--ease-brand);
}
nav.site a:hover { color: hsl(var(--brand-accent)); }
nav.site a.here { color: hsl(var(--foreground)); border-bottom: 2px solid hsl(var(--brand-accent)); padding-bottom: 2px; }
nav.site .navmark { font-weight: 700; color: hsl(var(--foreground)); margin-right: auto; }

/* An example is the ontology's own words about what falls under a term. It
   earns more room than a note: it is what most readers came for. */
.example {
  border-left: 3px solid hsl(var(--clr-node-property) / 0.7);
  padding: 0.15rem 0 0.15rem 1rem;
  margin: 0;
  color: hsl(var(--foreground));
}
.example p { margin: 0; }

/* Plain English, before the diagrams. Set larger than body text because it is
   the thing to read first. */
.inshort { font-size: var(--fs-body-lg); margin: 0 0 0.9rem; }
/* The front page's opening claim. Set at lead size so the first paragraph reads
   as the thing to read, and the rest at body size behind it. */
/* The opening story is prose, so it takes the prose face — the same one the
   lead above it and the figure captions below it use. In the body sans it read
   as a different document wedged between them. */
.why p { font-family: "Newsreader", ui-serif, Georgia, serif; }
.why-lead { font-size: var(--fs-body-lg); }
/* Sub-headings inside the opening story. Smaller than a section head and in the
   body face, so they group paragraphs without competing with the section rules. */
.why-h { font-size: var(--fs-h4); margin: 1.6rem 0 0.4rem; }
.inshort:last-child { margin-bottom: 0; }

/* Turtle snippets. The ontology's own syntax is the clearest example there is,
   so these are plain code — no diagram, nothing to decode. */
pre.ttl {
  font-family: "DM Mono", ui-monospace, SFMono-Regular, monospace;
  font-size: var(--fs-sm);
  line-height: 1.65;
  background: hsl(var(--surface));
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius);
  padding: 1rem 1.15rem;
  overflow-x: auto;
  margin: 0 0 0.5rem;
}
pre.ttl a { color: hsl(var(--brand-accent)); }
pre.ttl a:hover { text-decoration: underline; }
pre.ttl .cm   { color: hsl(var(--muted-foreground)); }
pre.ttl .lit  { color: hsl(var(--code-lit)); }
pre.ttl .kw   { color: hsl(var(--code-kw)); font-weight: 500; }
pre.ttl .pfx  { color: hsl(var(--code-pfx)); }
pre.ttl .tiri { color: hsl(var(--code-pfx)); }
pre.ttl .loc  { color: hsl(var(--foreground)); }
pre.ttl .pn   { color: hsl(var(--faint)); }

.worked { margin-bottom: 2.25rem; }
.worked h3 { font-size: var(--fs-h4); margin: 0 0 0.3rem; }
.worked .why { color: hsl(var(--muted-foreground)); font-size: var(--fs-sm); margin: 0 0 0.75rem; max-width: var(--measure); }

/* The reference page: one row per term, dense enough to scan. */
.refrow { display: flex; gap: 0.75rem; align-items: baseline; padding: 0.3rem 0; border-bottom: 1px solid hsl(var(--border) / 0.6); flex-wrap: wrap; }
.refrow .rt { font-family: "DM Mono", ui-monospace, monospace; font-size: var(--fs-sm); min-width: 15rem; }
.refrow .rd { font-size: var(--fs-sm); color: hsl(var(--muted-foreground)); flex: 1 1 18rem; }
.refrow .rr { font-family: "DM Mono", ui-monospace, monospace; font-size: var(--fs-2xs); color: hsl(var(--muted-foreground)); letter-spacing: 0.04em; }
/* The signature on a class page. Wide enough that domain → range does not wrap
   for the common cases, and it comes before the prose because it is the answer. */
.refrow .rsig { flex: 0 1 21rem; min-width: 15rem; max-width: 26rem; font-size: var(--fs-xs); overflow-wrap: anywhere; }
/* The end of the signature that is the page you are on. Present, but not the
   thing to read — and not a link back to here. */
.refrow .self { color: hsl(var(--faint)); }
/* The specialisation ladder. Indent carries the chain; the signature on every
   rung is what makes the narrowing visible without clicking. */
.specrow { display: flex; gap: 0.75rem; align-items: baseline; padding: 0.35rem 0; flex-wrap: wrap; }
.specrow .rt { font-family: "DM Mono", ui-monospace, monospace; font-size: var(--fs-sm); min-width: 13rem; }
.specnow { background: hsl(var(--tint)); }
.narrows {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-2xs);
  letter-spacing: 0.04em;
  color: hsl(var(--code-lit));
  border: 1px solid hsl(var(--code-lit) / 0.35);
  padding: 0.05rem 0.35rem;
  white-space: nowrap;
}
.specnote { color: hsl(var(--muted-foreground)); font-size: var(--fs-sm); margin: 0 0 1rem; }

.inhead {
  font-family: "DM Mono", ui-monospace, monospace;
  font-size: var(--fs-2xs);
  letter-spacing: 0.04em;
  color: hsl(var(--muted-foreground));
  margin: 1.5rem 0 0.5rem;
}
.refrow .rsig code { font-size: inherit; }

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
  /* It goes to the module page, so it takes the link colour. Kept small rather
     than kept grey: muted ink is what made it read as a dead badge. */
  color: hsl(var(--brand-accent));
  border: 1px solid hsl(var(--border));
  padding: 0.05rem 0.35rem;
  margin-left: 0.5rem;
  white-space: nowrap;
  transition: border-color 150ms var(--ease-brand), color 150ms var(--ease-brand);
}
a.modtag:hover { border-color: hsl(var(--brand-accent)); color: hsl(var(--brand-accent)); text-decoration: none; }

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
  font-family: "Newsreader", ui-serif, Georgia, serif;
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
/* Zemach's quadrants. Three are background and one carries the emphasis: the
   Type cell is the one loze is built on, so it is the only coloured thing here. */
.z-cell { fill: hsl(var(--surface)); stroke: hsl(var(--border)); stroke-width: 1.5; }
.z-hit  { fill: hsl(var(--tint)); stroke: hsl(var(--brand-accent)); stroke-width: 2.5; }
.z-title { font-family: "Archivo", sans-serif; font-size: 15px; letter-spacing: 1.8px; font-weight: 700;
  fill: hsl(var(--foreground)); }
.z-title.z-hit { fill: hsl(var(--brand-accent)); stroke: none; }
/* The four corner codes were bare initials with nothing on the page saying
   what they stood for. Expanded against the two axes rather than quoting
   Zemach's own wording, because the grid is what makes it checkable. */
.z-key { font-family: "DM Mono", monospace; font-size: 12px; letter-spacing: 0.02em;
  fill: hsl(var(--faint)); }
.z-code { font-family: "DM Mono", monospace; font-size: 11px; letter-spacing: 0.1em;
  fill: hsl(var(--faint)); text-anchor: end; }
.z-gloss { font-family: "Archivo", sans-serif; font-size: 15px; letter-spacing: 1.8px; fill: hsl(var(--muted-foreground)); }
.z-item { font-family: "Archivo", ui-serif, Georgia, serif; font-size: 13.5px; fill: hsl(var(--foreground)); }
.z-axis { font-family: "DM Mono", monospace; font-size: 12px; letter-spacing: var(--tracking-label);
  fill: hsl(var(--foreground)); }
/* loze's categories laid over Zemach's grid. Eventuality is the one that spans:
   he separates Event from Process on spatial continuity and loze does not cut
   there, so one outline has to cross a boundary. */
.z-span { fill: none; stroke: hsl(var(--muted-foreground)); stroke-width: 2;
  stroke-dasharray: 7 5; }
.z-span-hit { stroke: hsl(var(--brand-accent)); stroke-width: 2.5; }
.z-span-lab { font-family: "DM Mono", monospace; font-size: 12.5px; letter-spacing: 0.04em;
  fill: hsl(var(--muted-foreground)); text-anchor: middle; stroke: none; }
.z-span-hit-lab { fill: hsl(var(--brand-accent)); }
.z-sub { font-family: "DM Sans", sans-serif; font-size: 12px; fill: hsl(var(--faint)); }
.q-tag { font-family: "DM Mono", monospace; font-size: 11px; letter-spacing: 0.04em;
  fill: hsl(var(--faint)); }
.fig-q { font-family: "DM Mono", monospace; font-size: 12.5px; fill: hsl(var(--foreground)); }
.fig-ok { fill: hsl(var(--clr-status-ok)); }
.q-chip { fill: hsl(var(--clr-node-instance) / 0.12); stroke: hsl(var(--clr-node-instance)); stroke-width: 1.2; }
/* The row that answers the question. */
.q-hit { fill: hsl(var(--clr-status-ok) / 0.16); stroke: hsl(var(--clr-status-ok)); stroke-width: 2; }
.n-schem-e { stroke-width: 3; stroke-dasharray: 3 3; }
.n-event { fill: hsl(var(--surface)); stroke: hsl(var(--foreground) / 0.55);
  stroke-width: 1.5; stroke-dasharray: 2 3; }
.q-lab { font-family: "Archivo", sans-serif; font-size: 12.5px; fill: hsl(var(--foreground)); text-anchor: middle; }

.n-class { fill: hsl(var(--clr-node-class) / 0.10); stroke: hsl(var(--clr-node-class)); stroke-width: 1.5; }
.n-inst  { fill: hsl(var(--clr-node-instance) / 0.12); stroke: hsl(var(--clr-node-instance)); stroke-width: 1.5; }
/* The schematic one is the claim, so it is the only node drawn heavier. */
.n-schem { stroke-width: 3; }
.n-lab  { font-family: "Archivo", sans-serif; font-size: 14px; font-weight: 500;
          fill: hsl(var(--foreground)); text-anchor: middle; }
.n-sm  { font-size: 13px; }
.n-kind { font-family: "DM Mono", monospace; font-size: 11px;
          fill: hsl(var(--faint)); text-anchor: middle; }

.e-base { stroke: currentColor; stroke-width: 1.4; opacity: 0.55; fill: none; }
.e-prop { stroke: hsl(var(--clr-node-property)); stroke-width: 2; fill: none; }
.e-lab  { font-family: "DM Mono", monospace; font-size: 11px; fill: hsl(var(--muted-foreground)); }
.e-lab-prop { fill: hsl(var(--clr-node-property)); }
/* The pun is the cost the figure exists to show, so it is the one mark drawn as a
   problem: dashed, and in the danger colour rather than the node triad. */
.e-pun { stroke: hsl(var(--clr-status-danger)); stroke-width: 1.6; stroke-dasharray: 5 4; fill: none; }
.e-lab-warn { fill: hsl(var(--clr-status-danger)); }
.n-pun { stroke-dasharray: 5 4; }
.fig-warn { fill: hsl(var(--clr-status-danger)); }

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
<svg xmlns="http://www.w3.org/2000/svg" width="1720" height="900" viewBox="0 0 1720 900"
     role="img" aria-label="Two ways to model the same facts, side by side. On the left, punning: :ToyotaCorolla is a class so Alice's and Bob's Corollas can be instances of it, and separately an individual so it can carry an advertised weight of 1205kg. Two entities share one name. On the right, loze: one :_ToyotaCorolla tagged loze:SchematicParticular carries the advertised weight, Alice's and Bob's Corollas are tagged loze:ConcreteParticular and concretize it, and all three are rdf:type :Car. No pun.">
    <defs>
      <marker id="ah-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#0D1117"></path>
      </marker>
      <marker id="ah-amber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#B45309"></path>
      </marker>
      <marker id="ah-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#059669"></path>
      </marker>
    </defs>
  
    <rect x="0" y="0" width="1720" height="900" fill="#FFFFFF"></rect>
  
    <line x1="0" y1="420" x2="1720" y2="420" stroke="#B9BFB8" stroke-width="1" stroke-dasharray="8 8"></line>
    <line x1="840" y1="60" x2="840" y2="840" stroke="#0D1117" stroke-width="2"></line>
  
    <text x="80" y="50" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8" fill="#0D1117">PUNNING</text>
    <text x="920" y="50" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8" fill="#0D1117">SCHEMATIC PARTICULAR</text>
    <text transform="translate(38,240) rotate(-90)" text-anchor="middle" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8" fill="#5A6260">CLASSES</text>
    <text transform="translate(38,610) rotate(-90)" text-anchor="middle" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8" fill="#5A6260">INDIVIDUALS</text>
  
    
    <line x1="420" y1="304" x2="420" y2="162" fill="none" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
    <line x1="220" y1="500" x2="358" y2="362" fill="none" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
    <line x1="482" y1="362" x2="618" y2="498" fill="none" stroke="#B45309" stroke-width="1.5" stroke-dasharray="7 6" marker-start="url(#ah-amber)" marker-end="url(#ah-amber)"></line>
  
    
    <line x1="1060" y1="520" x2="1218" y2="362" fill="none" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
    <line x1="1572" y1="592" x2="1342" y2="362" fill="none" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
    <line x1="1202" y1="620" x2="1448" y2="620" fill="none" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
  
    
    <rect x="300.5" y="100.5" width="239" height="55" fill="#FFFFFF" stroke="#0EA5E9" stroke-width="1"></rect>
    <line x1="300" y1="101.5" x2="540" y2="101.5" stroke="#0EA5E9" stroke-width="3"></line>
    <text x="420" y="135" font-family="DM Mono, Menlo, Consolas, monospace" font-size="20" fill="#0D1117" text-anchor="middle">:Car</text>
  
    
    <rect x="300.5" y="304.5" width="239" height="55" fill="#FFFFFF" stroke="#0EA5E9" stroke-width="1"></rect>
    <line x1="300" y1="305.5" x2="540" y2="305.5" stroke="#0EA5E9" stroke-width="3"></line>
    <text x="420" y="339" font-family="DM Mono, Menlo, Consolas, monospace" font-size="20" fill="#0D1117" text-anchor="middle">:ToyotaCorolla</text>
  
    
    <rect x="80.5" y="500.5" width="279" height="199" fill="#FBFCFA" stroke="#C9CEC7" stroke-width="1"></rect>
    <rect x="100.5" y="530.5" width="239" height="57" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"></rect>
    <line x1="101.5" y1="530" x2="101.5" y2="588" stroke="#059669" stroke-width="3"></line>
    <text x="220" y="565" font-family="DM Mono, Menlo, Consolas, monospace" font-size="19" fill="#0D1117" text-anchor="middle">:_AlicesCorolla</text>
    <rect x="100.5" y="612.5" width="239" height="57" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"></rect>
    <line x1="101.5" y1="612" x2="101.5" y2="670" stroke="#059669" stroke-width="3"></line>
    <text x="220" y="647" font-family="DM Mono, Menlo, Consolas, monospace" font-size="19" fill="#0D1117" text-anchor="middle">:_BobsCorolla</text>
  
    
    <rect x="500.5" y="500.5" width="239" height="55" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"></rect>
    <line x1="501.5" y1="500" x2="501.5" y2="556" stroke="#059669" stroke-width="3"></line>
    <text x="620" y="534" font-family="DM Mono, Menlo, Consolas, monospace" font-size="19" fill="#0D1117" text-anchor="middle">:_ToyotaCorolla</text>
    <rect x="500.5" y="556.5" width="239" height="43" fill="#FFFFFF" stroke="#B9BFB8" stroke-width="1" stroke-dasharray="5 4"></rect>
    <text x="620" y="584" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#5A6260" text-anchor="middle">:advertisedWeight 1205kg</text>
  
    
    <rect x="432" y="222" width="141" height="21" fill="#FFFFFF"></rect>
    <text x="438" y="238" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">rdfs:subClassOf</text>
    <rect x="250" y="419" width="80" height="21" fill="#FFFFFF"></rect>
    <text x="290" y="435" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" text-anchor="middle">rdf:type</text>
    <rect x="512" y="419" width="76" height="21" fill="#FFFFFF"></rect>
    <text x="550" y="435" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="15" font-weight="500" letter-spacing="1.2" fill="#B45309" text-anchor="middle">PUNNED</text>
  
    
    <rect x="1160.5" y="304.5" width="239" height="55" fill="#FFFFFF" stroke="#0EA5E9" stroke-width="1"></rect>
    <line x1="1160" y1="305.5" x2="1400" y2="305.5" stroke="#0EA5E9" stroke-width="3"></line>
    <text x="1280" y="339" font-family="DM Mono, Menlo, Consolas, monospace" font-size="20" fill="#0D1117" text-anchor="middle">:Car</text>
  
    
    <rect x="920.5" y="520.5" width="279" height="199" fill="#FBFCFA" stroke="#C9CEC7" stroke-width="1"></rect>
    <rect x="940.5" y="550.5" width="239" height="57" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"></rect>
    <line x1="941.5" y1="550" x2="941.5" y2="608" stroke="#059669" stroke-width="3"></line>
    <text x="1060" y="577" font-family="DM Mono, Menlo, Consolas, monospace" font-size="19" fill="#0D1117" text-anchor="middle">:_AlicesCorolla</text>
    <text x="1060" y="597" font-family="DM Mono, Menlo, Consolas, monospace" font-size="13" fill="#5A6260" text-anchor="middle">loze:ConcreteParticular</text>
    <rect x="940.5" y="632.5" width="239" height="57" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"></rect>
    <line x1="941.5" y1="632" x2="941.5" y2="690" stroke="#059669" stroke-width="3"></line>
    <text x="1060" y="659" font-family="DM Mono, Menlo, Consolas, monospace" font-size="19" fill="#0D1117" text-anchor="middle">:_BobsCorolla</text>
    <text x="1060" y="679" font-family="DM Mono, Menlo, Consolas, monospace" font-size="13" fill="#5A6260" text-anchor="middle">loze:ConcreteParticular</text>
  
    
    <rect x="1452.5" y="592.5" width="239" height="55" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"></rect>
    <line x1="1453.5" y1="592" x2="1453.5" y2="648" stroke="#059669" stroke-width="3"></line>
    <text x="1572" y="618" font-family="DM Mono, Menlo, Consolas, monospace" font-size="19" fill="#0D1117" text-anchor="middle">:_ToyotaCorolla</text>
    <text x="1572" y="638" font-family="DM Mono, Menlo, Consolas, monospace" font-size="13" fill="#5A6260" text-anchor="middle">loze:SchematicParticular</text>
    <rect x="1452.5" y="648.5" width="239" height="43" fill="#FFFFFF" stroke="#B9BFB8" stroke-width="1" stroke-dasharray="5 4"></rect>
    <text x="1572" y="676" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#5A6260" text-anchor="middle">:advertisedWeight 1205kg</text>
  
    
    <rect x="1028" y="442" width="80" height="21" fill="#FFFFFF"></rect>
    <text x="1034" y="458" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">rdf:type</text>
    <rect x="1444" y="442" width="80" height="21" fill="#FFFFFF"></rect>
    <text x="1450" y="458" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">rdf:type</text>
    <rect x="1236" y="586" width="180" height="21" fill="#FFFFFF"></rect>
    <text x="1242" y="602" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:isConcretizationOf</text>
  </svg>
<figcaption>
By using schematic particulars, modelers are able to leverage a third, 
middle layer of abstraction. The schematic particular is an <code>owl:NamedIndividual</code>, 
yet is semantically more abstract than a concrete object. 
Objects (also individuals) concretize these particulars at the most specific layer, 
while classes typify particulars at the most abstract layer. <br><br>

In the above example, we outline two methods for modeling the fact that there are cars, 
in the most general sense, as well as Toyota Corollas as products,
 in addition to the actual objects that are Alice’s and Bob’s Corollas. <br><br>

In the left approach, we model a Corolla as both an owl:Class and <code>owl:NamedIndividual</code>, 
in a standard example of punning. Punning enables us to say things about the thing 
that is a Toyota Corolla (that it is advertised to be 1205 kg). 
	
In contrast, using Loze and its <code>:SchematicParticular</code> to model this, 
we are able to instantiate a schematic particular (<code>:_ToyotaCorolla</code>), 
which is of type <code>:Car</code>, and is concretized by both Alice and Bob’s 
Corollas, achieving the same semantic content without the need to resort to punning.
</figcaption>
</figure>
'''

QUERY_FIGURE = '''
<figure class="fig">
<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="880" viewBox="0 0 1300 880">
  <rect x="0" y="0" width="1300" height="880" fill="#FFFFFF"/>
  <line x1="667" y1="90" x2="667" y2="860" stroke="#0D1117" stroke-width="2"/>
  <line x1="190" y1="563" x2="1300" y2="563" stroke="#0D1117" stroke-width="2"/>
  <text x="248" y="75" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="11" font-weight="500" letter-spacing="1.8" fill="#0D1117">CLASS</text>
  <text x="700" y="75" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="11" font-weight="500" letter-spacing="1.8" fill="#0D1117">SCHEMATIC PARTICULAR</text>
  <text x="200" y="323" transform="rotate(-90 200 323)" text-anchor="middle" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="11" font-weight="500" letter-spacing="1.8" fill="#5A6260">INDIVIDUAL LEVEL</text>
  <text x="200" y="714" transform="rotate(-90 200 714)" text-anchor="middle" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="11" font-weight="500" letter-spacing="1.8" fill="#5A6260">CONCEPT LEVEL</text>
  <rect x="248" y="110" width="260" height="120" fill="#F6F7F5" stroke="#E4E6E2" stroke-width="1"/>
  <text x="264" y="141" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">SELECT ?car</text>
  <text x="264" y="163" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">WHERE{</text>
  <text x="264" y="185" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">?car a :Car</text>
  <text x="264" y="207" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">}</text>
  <rect x="248" y="250" width="150" height="44" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"/>
  <line x1="249.5" y1="250" x2="249.5" y2="294" stroke="#059669" stroke-width="3"/>
  <text x="323" y="277" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_AlicesCorolla</text>
  <rect x="418" y="250" width="150" height="44" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"/>
  <line x1="419.5" y1="250" x2="419.5" y2="294" stroke="#059669" stroke-width="3"/>
  <text x="493" y="277" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_BobsCorolla</text>
  <rect x="248" y="314" width="384" height="120" fill="#F6F7F5" stroke="#E4E6E2" stroke-width="1"/>
  <text x="264" y="345" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">SELECT ?car ?weight</text>
  <text x="264" y="367" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">WHERE{</text>
  <text x="264" y="389" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">?car :advertisedWeight ?weight</text>
  <text x="264" y="411" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">}</text>
  <rect x="248" y="454" width="172" height="44" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"/>
  <line x1="249.5" y1="454" x2="249.5" y2="498" stroke="#059669" stroke-width="3"/>
  <text x="334" y="481" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_ToyotaCorolla</text>
  <rect x="248" y="498" width="172" height="30" fill="#FFFFFF" stroke="#B9BFB8" stroke-width="1" stroke-dasharray="5 4"/>
  <text x="334" y="517" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="11" fill="#5A6260">:advertisedWeight 1205kg</text>
  <rect x="700" y="314" width="260" height="120" fill="#F6F7F5" stroke="#E4E6E2" stroke-width="1"/>
  <text x="716" y="345" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">SELECT ?car ?weight</text>
  <text x="716" y="367" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">WHERE{</text>
  <text x="716" y="389" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">?car a :Car</text>
  <text x="716" y="411" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">}</text>
  <rect x="700" y="454" width="150" height="44" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"/>
  <line x1="701.5" y1="454" x2="701.5" y2="498" stroke="#059669" stroke-width="3"/>
  <text x="775" y="481" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_AlicesCorolla</text>
  <rect x="866" y="454" width="150" height="44" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"/>
  <line x1="867.5" y1="454" x2="867.5" y2="498" stroke="#059669" stroke-width="3"/>
  <text x="941" y="481" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_BobsCorolla</text>
  <rect x="1032" y="454" width="172" height="44" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"/>
  <line x1="1033.5" y1="454" x2="1033.5" y2="498" stroke="#059669" stroke-width="3"/>
  <text x="1118" y="481" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_ToyotaCorolla</text>
  <rect x="1032" y="498" width="172" height="30" fill="#FFFFFF" stroke="#B9BFB8" stroke-width="1" stroke-dasharray="5 4"/>
  <text x="1118" y="517" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="11" fill="#5A6260">:advertisedWeight 1205kg</text>
  <rect x="248" y="592" width="384" height="142" fill="#F6F7F5" stroke="#E4E6E2" stroke-width="1"/>
  <text x="264" y="623" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">SELECT ?car ?weight</text>
  <text x="264" y="645" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">WHERE{</text>
  <text x="264" y="667" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">?car a :Car ;</text>
  <text x="264" y="689" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">     :advertisedWeight ?weight</text>
  <text x="264" y="711" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">}</text>
  <rect x="700" y="592" width="384" height="142" fill="#F6F7F5" stroke="#E4E6E2" stroke-width="1"/>
  <text x="716" y="623" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">SELECT ?car ?weight</text>
  <text x="716" y="645" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">WHERE{</text>
  <text x="716" y="667" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">?car a :Car ;</text>
  <text x="716" y="689" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">     :advertisedWeight ?weight</text>
  <text x="716" y="711" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117" xml:space="preserve">}</text>
  <rect x="700" y="754" width="172" height="44" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"/>
  <line x1="701.5" y1="754" x2="701.5" y2="798" stroke="#059669" stroke-width="3"/>
  <text x="786" y="781" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_ToyotaCorolla</text>
  <rect x="700" y="798" width="172" height="30" fill="#FFFFFF" stroke="#B9BFB8" stroke-width="1" stroke-dasharray="5 4"/>
  <text x="786" y="817" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="11" fill="#5A6260">:advertisedWeight 1205kg</text>

  <rect x="248" y="754" width="172" height="44" fill="#F49F99" stroke="#FF1500" stroke-width="1"/>
    <line x1="249.5" y1="754" x2="249.5" y2="798" stroke="#EB5045" stroke-width="3"/>
    <text x="332.5" y="781" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">None</text>
    
  </svg>
  <figcaption>
  There are query benefits to using Loze’s schematic particulars. 
  In the Loze example, with <code>:_ToyotaCorolla</code> as both a <code>:Car</code> 
  a repeatable thing which is concretized, users can ask concept-level questions, such as 
  “What is the advertised weight of a Toyota Corolla?” using concise and transparent SPARQL patterns,
  rather than resorting to convoluted metamodeling, or <code>owl:NamedIndividual</code> proxies for an 
  <code>owl:Class</code>
  </figcaption>
</figure>
'''

EVENT_FIGURE = '''
<figure class="fig">
<svg xmlns="http://www.w3.org/2000/svg" width="1060" height="574" viewBox="0 0 1060 574">
<rect x="0" y="0" width="1060" height="574" fill="#FFFFFF"></rect>
<defs><marker id="ah-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#0D1117"></path></marker></defs>
<line x1="486" y1="46" x2="486" y2="530" stroke="#B9BFB8" stroke-width="1" stroke-dasharray="8 8"></line>
<line x1="43" y1="287" x2="991" y2="287" stroke="#B9BFB8" stroke-width="1" stroke-dasharray="8 8"></line>
<line x1="332" y1="167" x2="660" y2="167" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
<line x1="332" y1="424" x2="660" y2="424" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
<line x1="243" y1="188" x2="243" y2="388" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
<line x1="758" y1="188" x2="758" y2="388" stroke="#0D1117" stroke-width="1.5" marker-end="url(#ah-ink)"></line>
<text x="144" y="52" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8" fill="#0D1117">THING</text>
<text x="692" y="52" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8" fill="#0D1117">OCCURENCE</text>
<text x="18" y="167" transform="rotate(-90 18 167)" text-anchor="middle" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="15" font-weight="500" letter-spacing="1.5" fill="#5A6260">SCHEMATIC</text>
<text x="18" y="424" transform="rotate(-90 18 424)" text-anchor="middle" font-family="DM Sans, Helvetica, Arial, sans-serif" font-size="15" font-weight="500" letter-spacing="1.5" fill="#5A6260">CONCRETE</text>
<rect x="145" y="146" width="196" height="42" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"></rect>
<line x1="146.5" y1="146" x2="146.5" y2="188" stroke="#059669" stroke-width="3"></line>
<text x="243" y="172" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_ToyotaCorolla</text>
<rect x="660" y="146" width="196" height="42" fill="#EFF8FD" stroke="#BAE6FD" stroke-width="1"></rect>
<line x1="661.5" y1="146" x2="661.5" y2="188" stroke="#0EA5E9" stroke-width="3"></line>
<text x="758" y="172" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_30kMileSvc</text>
<rect x="145" y="403" width="196" height="42" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1"></rect>
<line x1="146.5" y1="403" x2="146.5" y2="445" stroke="#059669" stroke-width="3"></line>
<text x="243" y="429" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_AlicesCorolla</text>
<rect x="660" y="403" width="196" height="42" fill="#EFF8FD" stroke="#BAE6FD" stroke-width="1"></rect>
<line x1="661.5" y1="403" x2="661.5" y2="445" stroke="#0EA5E9" stroke-width="3"></line>
<text x="758" y="429" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="15" fill="#0D1117">:_Alices30kMileSvc</text>
<rect x="405" y="156" width="180" height="20" fill="#FFFFFF"></rect>
<text x="496" y="171" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="13" fill="#0D1117">:hasRecommendedService</text>
<rect x="450" y="413" width="95" height="20" fill="#FFFFFF"></rect>
<text x="496" y="428" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="13" fill="#0D1117">:hasService</text>
<rect x="173" y="276" width="140" height="20" fill="#FFFFFF"></rect>
<text x="243" y="291" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="13" fill="#0D1117">:hasConcretization</text>
<rect x="688" y="276" width="140" height="20" fill="#FFFFFF"></rect>
<text x="758" y="291" text-anchor="middle" font-family="DM Mono, Menlo, Consolas, monospace" font-size="13" fill="#0D1117">:hasConcretization</text>
</svg>
<figcaption>
Loze allows schematic particulars to represent Things and Occurences, all as individuals. 
By doing so, it is possible to model general, repeatable processes with more information, e.g. 
the schematic particular event <code>:OilChange</code> can have an <code>:expectedPrice</code> of 100 USD.
Because of this flexibility, Loze provides all of the aforementioned benefits not only to things, but happenings too.

</figure>
'''


def zemach_figure() -> str:
    """Zemach's four ontologies, redrawn in the page's own system.

    Redrawn rather than embedded. The original is a raster on a white ground, which
    would invert badly in dark mode and could not take the site's type or palette.
    Redrawing also lets the emphasis go where it belongs: three quadrants are
    background, and the fourth is the one loze is built on.
    """
    CELLS = [
        (170, 96,  "Event", "NC", "a filled chunk of spacetime",
         ["the moon landing", "a handshake", "yesterday&#8217;s sunset"], ""),
        (560, 96,  "Thing", "CT", "the desk you see again today",
         ["Fido the dog", "the Eiffel Tower", "my pencil"], ""),
        (170, 298, "Process", "CS", "everywhere at once, then over",
         ["the French Revolution", "this rain", "the current inflation"], ""),
        (560, 298, "Type", "PC", "wholly present in every token",
         ["water, gold, wheat", "the letter A", "Beethoven&#8217;s Fifth"], " z-hit"),
    ]
    out = ""
    for x, y, title, code, gloss, items, hit in CELLS:
        out += (f'<rect class="z-cell{hit}" x="{x}" y="{y}" width="360" height="176"/>'
                f'<text class="z-title{hit}" x="{x+20}" y="{y+30}">{title}</text>'
                f'<text class="z-code" x="{x+340}" y="{y+30}">{code}</text>'
                f'<text class="z-gloss" x="{x+20}" y="{y+52}">{gloss}</text>')
        for i, it in enumerate(items):
            out += f'<text class="z-item" x="{x+20}" y="{y+82 + i*24}">&#8594; {it}</text>'
        # Which loze class this quadrant becomes. The whole point of showing
        # Zemach here is the mapping, and it was left implicit.
    return f'''
<figure class="fig">
<svg viewBox="0 0 960 572" role="img" xmlns="http://www.w3.org/2000/svg"
     aria-label="Zemach's four ontologies as a two by two. Columns are bound in time and continuous in time; rows are bound in space and continuous in space. Event, Thing, Process and Type. The Type quadrant, wholly present in every token, is highlighted: water, the letter A, Beethoven's Fifth. That is the cell loze keeps as a particular rather than a universal.">
  <text class="z-axis" x="170" y="34" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">BOUND IN TIME</text>
  <text class="z-sub" x="170" y="52" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">has temporal parts; over when done</text>
  <text class="z-axis" x="560" y="34" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">CONTINUOUS IN TIME</text>
  <text class="z-sub" x="560" y="52" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">wholly present at each time</text>
  <text class="z-axis" x="0" y="150" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">BOUND IN</text>
  <text class="z-axis" x="0" y="168" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">SPACE</text>
  <text class="z-sub" x="0" y="188" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">has spatial parts</text>
  <text class="z-axis" x="0" y="352" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">CONTINUOUS</text>
  <text class="z-axis" x="0" y="370" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">IN SPACE</text>
  <text class="z-sub" x="0" y="390" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">wholly present</text>
  <text class="z-sub" x="0" y="406" font-family="Archivo, sans-serif" font-size="15" font-weight="500" letter-spacing="1.8">at each place</text>
  {out}
  <rect class="z-span" x="160" y="86" width="380" height="398"/>
  <text class="z-span-lab" x="350" y="466">loze:Eventuality</text>
  <rect class="z-span z-span-q" x="550" y="86" width="380" height="196"/>
  <text class="z-span-lab" x="740" y="264">loze:Thing</text>
  <rect class="z-span z-span-hit" x="550" y="288" width="380" height="196"/>
  <text class="z-span-lab z-span-hit-lab" x="740" y="466">loze:SchematicParticular</text>
  <text class="z-key" x="152" y="522">NC continuous in neither &#183; CT continuous in time &#183; CS continuous in space &#183; PC continuous in both</text>
  <text class="fig-note" x="152" y="552" font-family="Newsreader">Zemach, &#8220;Four Ontologies&#8221;, Journal of Philosophy 67 (1970). loze takes the fourth cell and keeps it a particular.</text>
</svg>
<figcaption>
	The central novelty of loze is the use of <a href="/SchematicParticular">Schematic Particulars</a>; 
    things that are repeatable, wholly present at each time and place, 
    but are a step of abstraction below classes. Examples of such things, 
    as provided by Zemach, are a work of music (Beethoven’s Fifth), an element or 
    compound (gold, water), and characters or numbers.</figcaption>
</figure>
'''


FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=DM+Mono:wght@400;500&family=Archivo:wght@400;500;600;700&'
    'family=Newsreader:ital,wght@0,300;0,400;1,300&display=swap">'
)


NAV = [("/terms", "terms"), ("/examples", "examples")]


def nav(here: str = "") -> str:
    """The same links on every page. Without this the only way out of a term page
    was the breadcrumb to /, which made every property page a dead end."""
    mark = ('<span class="navmark">loze</span>' if here == "/"
            else '<a class="navmark" href="/">loze</a>')
    links = "".join(
        f'<a class="here" href="{href}">{e(label)}</a>' if href == here
        else f'<a href="{href}">{e(label)}</a>'
        for href, label in NAV)
    return f'<nav class="site"><div class="wrap">{mark}{links}</div></nav>'


def shell(title: str, alternates: str, body: str, here: str = "") -> str:
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
{nav(here)}
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
    example = g.value(s, SKOS.example)
    css, kind = kind_of(g, s)
    return {
        "iri": str(s), "name": local(s),
        "label": str(label) if label else local(s),
        "definition": str(definition) if definition else "",
        "note": str(note) if note else "",
        "example": str(example) if example else "",
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


def rdf_list(g: Graph, head) -> list:
    """Members of an RDF collection, in order."""
    out = []
    while head is not None and head != RDF.nil:
        first = g.value(head, RDF.first)
        if first is None:
            break
        out.append(first)
        head = g.value(head, RDF.rest)
    return out


def anon_expr(g: Graph, node) -> str:
    """Render an anonymous class expression from its content.

    Matteo's axioms introduced owl:unionOf expressions, and these were being
    printed as their blank node label — 'n8289a058adf34293a1ef6d409b38da73b1'.
    Meaningless to a reader, and not even stable: rdflib mints those labels per
    parse, so three pages changed on every build. Describing the expression fixes
    both, because the description comes from the members rather than the label.
    """
    for pred, joiner in ((OWL.unionOf, " or "), (OWL.intersectionOf, " and ")):
        head = g.value(node, pred)
        if head is not None:
            members = rdf_list(g, head)
            if members:
                return joiner.join(term_link(g, m) for m in members)
    on = g.value(node, OWL.onProperty)
    if on is not None:
        return f"a restriction on {term_link(g, on)}"
    return "an anonymous class"


def short_expr(g: Graph, node, keep: int = 2) -> str:
    """An anonymous expression, cut down for a signature line.

    hasTemporalCoordinate ranges over a union of nine xsd date and time types.
    Spelled out that is three lines of noise in a row meant to be scanned, and it
    wrecks the column it sits in. The full list is on the property's own page.
    """
    for pred, joiner in ((OWL.unionOf, " or "), (OWL.intersectionOf, " and ")):
        head = g.value(node, pred)
        if head is not None:
            members = rdf_list(g, head)
            if len(members) > keep + 1:
                shown = joiner.join(term_link(g, m) for m in members[:keep])
                return f"{shown}{joiner}{len(members) - keep} more"
            break
    return anon_expr(g, node)


def term_link(g: Graph, o) -> str:
    if isinstance(o, URIRef) and str(o).startswith(NS):
        lbl = g.value(o, RDFS.label)
        return f'<a href="/{e(local(o))}">{e(str(lbl) if lbl else local(o))}</a>'
    if isinstance(o, URIRef):
        return f'<code>{e(shorten(str(o)))}</code>'
    if isinstance(o, BNode):
        return anon_expr(g, o)
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
            # The tag is the module slug, which is also its URL. It was a span,
            # so it looked exactly like a chip and went nowhere.
            tag = f'<a class="modtag" href="/{e(mod)}">{e(mod)}</a>'
    return (f'<li><a href="/{e(d["name"])}">{e(d["label"])}</a>{tag}'
            f'<span class="tree-def">{e(clip(d["definition"], 90))}</span>'
            + (f"<ul>{inner}</ul>" if inner else "") + "</li>")


def prop_row(g: Graph, p: URIRef, current: URIRef | None = None) -> str:
    """One reference row for a property: name, signature, clipped definition.

    Every page that lists properties uses this. There were three copies of it and
    a module page was still rendering bare chips, which is what a bare chip costs
    you — the reader cannot see what the property joins without clicking.

    `current` is the term whose page this is, if any: that end of the signature
    is muted and unlinked so the eye lands on the end that varies.
    """
    d = describe(g, p)

    def side(which):
        parts = []
        for o in g.objects(p, which):
            if current is not None and o == current:
                lbl = g.value(o, RDFS.label)
                parts.append(f'<span class="self">{e(str(lbl) if lbl else local(o))}</span>')
            elif isinstance(o, BNode):
                parts.append(short_expr(g, o))
            else:
                parts.append(term_link(g, o))
        return ", ".join(parts)

    dom, rng = side(RDFS.domain), side(RDFS.range)
    sig = f"{dom} &rarr; {rng}" if dom and rng else (dom or rng or '<span class="pn">—</span>')
    return (f'<div class="refrow">'
            f'<span class="rt"><a href="/{e(local(p))}">{e(local(p))}</a></span>'
            f'<span class="rr rsig">{sig}</span>'
            f'<span class="rd">{e(clip(d["definition"], 88))}</span>'
            f'</div>')


def prop_ancestors(g: Graph, p: URIRef) -> list[URIRef]:
    """Super-property chain to the top, nearest first."""
    out, seen, cur = [], {p}, p
    while True:
        nxt = None
        for o in g.objects(cur, RDFS.subPropertyOf):
            if isinstance(o, URIRef) and str(o).startswith(NS) and o not in seen:
                nxt = o
                break
        if nxt is None:
            return out
        out.append(nxt); seen.add(nxt); cur = nxt


def _ends(g: Graph, p: URIRef, pred) -> tuple[str, frozenset]:
    vals = sorted(g.objects(p, pred), key=str)
    html = ", ".join(term_link(g, o) for o in vals) or '<span class="pn">—</span>'
    return html, frozenset(str(v) for v in vals)


def spec_table(g: Graph, s: URIRef) -> str:
    """The sub-property chain with the signature at every level.

    A sub-property may narrow its parent's domain and range, and asserting it
    asserts the narrower ones too — isMemberIn goes Actor to Group where its
    parent isComponentIn goes Particular to Composition. That is the step people
    new to this reliably miss, and no page here showed it: you saw one signature
    and had to click up the chain to find out it had been tightened.
    """
    chain = prop_ancestors(g, s)
    kids = sorted([c for c in g.subjects(RDFS.subPropertyOf, s)
                   if isinstance(c, URIRef) and str(c).startswith(NS)],
                  key=lambda x: local(x).lower())
    if not chain and not kids:
        return ""

    line = list(reversed(chain)) + [s]
    rows = []

    def emit(p, depth, parent, current):
        dom_html, dom = _ends(g, p, RDFS.domain)
        rng_html, rng = _ends(g, p, RDFS.range)
        tag = ""
        if parent is not None:
            _, pdom = _ends(g, parent, RDFS.domain)
            _, prng = _ends(g, parent, RDFS.range)
            narrowed = [w for w, a, b in (("domain", dom, pdom), ("range", rng, prng))
                        if a != b]
            if narrowed:
                tag = f'<span class="narrows">narrows {" and ".join(narrowed)}</span>'
        name = (f'<span class="self">{e(local(p))}</span>' if current
                else f'<a href="/{e(local(p))}">{e(local(p))}</a>')
        rows.append(
            f'<div class="specrow{" specnow" if current else ""}" '
            f'style="padding-left:{depth * 1.4:.1f}rem">'
            f'<span class="rt">{name}</span>'
            f'<span class="rr rsig">{dom_html} &rarr; {rng_html}</span>'
            f'{tag}</div>')

    for depth, p in enumerate(line):
        emit(p, depth, line[depth - 1] if depth else None, p == s)
    for k in kids:
        emit(k, len(line), s, False)

    note = ('<p class="specnote measure">Asserting a sub-property asserts its own '
            'domain and range, not just the parent\'s. Anything you put either '
            'side is taken to be of the narrower class, whether or not you said '
            'so.</p>')
    return note + "".join(rows)


def section(head: str, inner: str) -> str:
    return f'<section><div class="section-head">{e(head)}</div>{inner}</section>' if inner else ""


def render_term(union: Graph, s: URIRef, defined_in: str | None) -> str:
    d = describe(union, s)
    classes = {c for c in union.subjects(RDF.type, OWL.Class) if str(c).startswith(NS)}
    is_prop = bool(set(union.objects(s, RDF.type)) & PROP_TYPES)

    # Up the tree, as a trail. Where a term sits matters more than its label.
    chain = ancestors(union, s)
    crumbs = ['<a href="/">loze</a>'] + [term_link(union, a) for a in reversed(chain)]
    trail = f'<div class="trail">{" / ".join(crumbs)} / <span>{e(d["label"])}</span></div>'

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
        """Every property that reaches this class, with its whole signature.

        A bare chip made you click through to learn what the property even
        joined — which is the one thing you opened the class page to find out.
        Both ends are shown; the end that is this page is muted and unlinked, so
        the eye lands on the far one, which is the end that varies.
        """
        # Direct, then inherited. A Composition IS an Eventuality, so atTime
        # applies to it — and leaving it off this page sends the reader hunting
        # up the tree for a property that was theirs all along.
        direct = sorted({p for p in union.subjects(pred, s)
                         if set(union.objects(p, RDF.type)) & PROP_TYPES},
                        key=lambda x: local(x).lower())
        seen_p = set(direct)
        inherited = []
        for anc in chain:
            for p in sorted({p for p in union.subjects(pred, anc)
                             if set(union.objects(p, RDF.type)) & PROP_TYPES},
                            key=lambda x: local(x).lower()):
                if p not in seen_p:
                    seen_p.add(p)
                    inherited.append(p)
        got = direct + inherited
        if not got:
            return ""

        def end(p, which):
            parts = []
            for o in union.objects(p, which):
                if o == s:
                    lbl = union.value(o, RDFS.label)
                    parts.append(f'<span class="self">{e(str(lbl) if lbl else local(o))}</span>')
                elif isinstance(o, BNode):
                    parts.append(short_expr(union, o))
                else:
                    parts.append(term_link(union, o))
            return ", ".join(parts)

        def row(p):
            return prop_row(union, p, current=s)


        out = "".join(row(p) for p in direct)
        if inherited:
            out += ('<div class="inhead">inherited &mdash; the signature names the '
                    'class each one is declared on</div>'
                    + "".join(row(p) for p in inherited))
        return out

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
  {section("In short", in_short_html(d["name"])) if d['name'] in IN_SHORT else ""}
  {section("In the model", props_dl)}
  {section("For example", f'<div class="example measure"><p>{e(d["example"])}</p></div>' if d['example'] else "")}
  {section("Specialisation", spec_table(union, s)) if is_prop else ""}
  {section("Specialised by", subs_html)}
  {"" if is_prop else section("Properties from this", props_where(RDFS.domain))}
  {"" if is_prop else section("Properties onto this", props_where(RDFS.range))}
  {(zemach_figure() + FIGURE + QUERY_FIGURE + EVENT_FIGURE) if d['name'] == "SchematicParticular" else (EVENT_FIGURE if d['name'] in ("Eventuality", "Thing", "hasParticipant", "hasProduct") else (FIGURE if d['name'] in ("isConcretizationOf", "hasConcretization") else ""))}
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
            rows = "".join(prop_row(union, p)
                           for p in sorted(by_domain[dom], key=lambda x: local(x).lower()))
            head = (f'<a href="/{e(dom)}">{e(dom)}</a>' if dom != "—" else "no declared domain")
            blocks.append(f'<div class="domgroup"><div class="domhead">from {head}</div>'
                          f'{rows}</div>')
        prop_html = "".join(blocks)

    modules_nav = ""
    if slug == "":
        cells = "".join(
            f'<div class="cell"><h4><a href="/{e(s2)}">{e(s2.replace("-", " "))}</a></h4>'
            f'<p>{len([x for x in Graph().parse(ROOT / src2, format="turtle").subjects()])} statements</p></div>'
            for s2, src2 in MODULES if s2)
        modules_nav = section("Modules", f'<div class="grid">{cells}</div>')

    schematic_section = (section("What this is for", WHY)
                         + section("Where the idea comes from", zemach_figure())
                         + section("Why a schematic particular", FIGURE)
                         + section("What it buys", QUERY_FIGURE)
                         + section("Things and happenings are a different cut", EVENT_FIGURE))

    trail = ("" if slug == ""
             else f'<div class="trail"><a href="/">loze</a> / <span>{e(label)}</span></div>')

    body = f"""
<header class="top"><div class="wrap">
  <div class="eyebrow">Semantic Partners &middot; ontology</div>
  {trail}
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


def clip(text: str, n: int = 104) -> str:
    """Shorten to a whole word. Cutting mid-word reads as a rendering fault."""
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


# One pass over the Turtle, left to right. Alternation order is the whole trick:
# a token that can contain another token's opening character must come first, so
# a " inside a comment and a # inside an IRI are both swallowed by the token that
# really owns them. Layered re.sub over already-escaped HTML could not do that.
TTL_TOKEN = re.compile(r"""
      (?P<string>"(?:[^"\\\n]|\\.)*")
    | (?P<comment>\#[^\n]*)
    | (?P<iri><[^>\s]*>)
    | (?P<directive>@[A-Za-z]+)
    | (?P<pname>[A-Za-z][\w.-]*:[\w.\-%]*|:[\w.\-%]*)
    | (?P<num>-?\d[\d.]*)
    | (?P<kw>(?<![\w:-])a(?![\w:-]))
    | (?P<punc>\^\^|[;,.\[\]()])
""", re.X)


def ttl_html(src: str) -> str:
    """Highlight a Turtle snippet and link every loze: term in it.

    Colour follows what a token IS, not whether it happens to be a link. Before,
    only loze: names and strings were coloured — because those were the two things
    the old regexes knew about — so owl:Class, rdfs:subClassOf, xsd:decimal and
    the `a` keyword all read as undifferentiated black.
    """
    src = src.strip("\n")
    out, pos = [], 0
    for m in TTL_TOKEN.finditer(src):
        if m.start() > pos:
            out.append(e(src[pos:m.start()]))
        pos = m.end()
        kind, text = m.lastgroup, m.group()
        if kind == "pname":
            prefix, _, localname = text.partition(":")
            if prefix == "loze" and localname:
                # check_examples() guarantees these resolve, so the link is safe.
                out.append(f'<a href="/{e(localname)}">{e(text)}</a>')
            elif prefix:
                out.append(f'<span class="pfx">{e(text)}</span>')
            else:
                # A name in the example's own namespace — the reader's data.
                out.append(f'<span class="loc">{e(text)}</span>')
        elif kind in ("string", "num"):
            out.append(f'<span class="lit">{e(text)}</span>')
        elif kind in ("kw", "directive"):
            out.append(f'<span class="kw">{e(text)}</span>')
        elif kind == "iri":
            out.append(f'<span class="tiri">{e(text)}</span>')
        elif kind == "comment":
            out.append(f'<span class="cm">{e(text)}</span>')
        else:
            out.append(f'<span class="pn">{e(text)}</span>')
    out.append(e(src[pos:]))
    return f'<pre class="ttl">{"".join(out)}</pre>'


# Worked examples. These answer questions people actually arrive with, in the
# ontology's own syntax. Every term used here is checked against the graph at
# build time by check_examples(), so a snippet cannot rot silently.
WORKED = [
    ("Give an event a time",
     "You have an interview, and you want to say when it happened. Make "
     "<code>:Interview</code> a subclass of <code>loze:Eventuality</code> — you "
     "want the domain class — and every loze property that takes an eventuality "
     "still reaches it, because <code>rdfs:domain</code> is inherited. The time "
     "is a period of time, and <code>loze:atTime</code> joins the two.",
     """
:Interview
    a owl:Class ;
    rdfs:subClassOf loze:Eventuality .       # your class, under loze's category

:interview-delivery-team
    a :Interview ;
    rdfs:label "Interview with the delivery team" ;
    loze:hasAgent       :lance ;             # who ran it
    loze:hasParticipant :sam ;               # who else was there
    loze:hasTopic       :the-migration ;     # what it was about
    loze:atTime         :morning-2026-08-14 .

:morning-2026-08-14
    a loze:PeriodOfTime ;
    loze:hasTemporalCoordinate "2026-08-14T10:00:00"^^xsd:dateTime ;
    loze:hasDuration           "PT90M"^^xsd:duration .
"""),
    ("Say when something started and stopped",
     "<code>loze:atTime</code> says an eventuality was going on then — it need not "
     "cover the whole span. For the ends, use <code>loze:fromTime</code> and "
     "<code>loze:untilTime</code>.",
     """
:Migration
    a owl:Class ;
    rdfs:subClassOf loze:Eventuality .

:the-migration
    a :Migration ;
    loze:fromTime  :2026-q1 ;
    loze:untilTime :2026-q3 ;
    loze:atTime    :2026-q2 .    # still running in Q2

:2026-q2
    a loze:PeriodOfTime ;
    loze:isSubperiodOf :year-2026 .
"""),
    ("Say who did what, to whom, with what",
     "Rather than a bespoke relation per kind of event, loze gives you one set of "
     "roles that works across domains. Reach for these before inventing your own.",
     """
:Payment
    a owl:Class ;
    rdfs:subClassOf loze:Eventuality .

:payment-8871
    a :Payment ;
    loze:hasAgent      :acme-ltd ;       # the one who acts
    loze:hasRecipient  :supplier-ltd ;   # the one it is conferred on
    loze:hasInstrument :card-4417 ;      # the means
    loze:atTime        :2026-08-14 .
"""),
    ("Put each fact where it holds",
     "The model, the model year and the car on the drive are three things, and "
     "the facts belong to different ones. Who makes it is true of every Corolla. "
     "The advertised weight is true of the 1985 and not the 2026. The weighbridge "
     "reading is true of one car. Note that the middle one is still schematic — "
     "refinement usually takes more than one step before anything concrete — and "
     "that all three are <code>:Car</code>, which stays an ordinary class "
     "throughout.",
     """
:Car a owl:Class .

:ToyotaCorolla                                 # the model
    a :Car, loze:SchematicParticular ;
    :manufacturer :Toyota .                    # true of every Corolla

:Corolla1985                                   # a model year — still repeatable
    a :Car, loze:SchematicParticular ;
    loze:isDeterminationOf :ToyotaCorolla ;
    :advertisedWeight "1205"^^xsd:decimal .    # true of this year only

:my-corolla                                    # AB12 CDE, on the drive
    a :Car, loze:ConcreteParticular ;
    loze:isConcretizationOf :Corolla1985 ;
    :kerbWeight "1232"^^xsd:decimal .          # true of this car only

# Nothing here is punned. :Car is a class and never an individual; the model
# and the model year are instances of it, as the car is.
#
# isDeterminationOf is transitive and concretization carries through it, so
# inference-rules/concretization-inheritance.rq derives the step you skipped:
#
#   :my-corolla loze:isConcretizationOf :ToyotaCorolla .
"""),
    ("Say something general, without punning",
     "This is what the category is for. A schematic particular is repeatable like "
     "a class but carries data like an instance, so a general fact about the model "
     "is an ordinary triple. The usual alternatives are a pun — one name used as "
     "both a class and an individual — or a restriction.",
     """
# The usual way. Each model year has to be a class, so units can be instances
# of it, and an individual, so it can hold a weight. OWL 2 permits the pun;
# nothing keeps the two in step, and the weight is invisible to a query over
# cars, because a subclass of :Car is not a :Car.
:Corolla1985 a owl:Class ;
    rdfs:subClassOf :ToyotaCorolla .
:ToyotaCorolla rdfs:subClassOf :Car .
:Corolla1985 :advertisedWeight "1205"^^xsd:decimal .     # the pun
:my-corolla a :Corolla1985 .

# loze. No pun at any level. :Car stays a class; the model and the model year
# are instances of it, so ?m a :Car / ?m :advertisedWeight ?kg both match the
# 1985 and the general question is answered with an ordinary pattern.
:ToyotaCorolla a :Car, loze:SchematicParticular .
:Corolla1985   a :Car, loze:SchematicParticular ;
    loze:isDeterminationOf :ToyotaCorolla ;
    :advertisedWeight "1205"^^xsd:decimal .
:my-corolla    a :Car, loze:ConcreteParticular ;
    loze:isConcretizationOf :Corolla1985 .
"""),
    ("Something that is a happening and still repeatable",
     "The two cuts are independent, so an eventuality can be schematic. The "
     "30,000-mile service is a procedure — carry it out anywhere, any number of "
     "times. The service your car had in March is one occasion in one garage. "
     "Give the first both types; there is nothing else to it.",
     """
:ThirtyThousandMileService
    a loze:Eventuality, loze:SchematicParticular ;   # the procedure
    :takesHours "2.0"^^xsd:decimal .

:service-march
    a loze:Eventuality, loze:ConcreteParticular ;    # one occasion
    loze:isConcretizationOf :ThirtyThousandMileService ;
    loze:hasAgent  :the-garage ;
    loze:hasTheme  :my-corolla ;
    loze:atTime    :2026-03-11 .
"""),
    ("A packaging tree, with no punning in it",
     "Every tier of a pack is schematic: the tablet, the blister, the carton. "
     "What holds them together is a <code>loze:Containment</code>, and that is "
     "schematic too — it is how every carton is packed, not one event on a line. "
     "<code>loze:hasNumberOfOccurrences</code> carries the count, which makes "
     "this a bill of materials over schematic particulars.",
     """
:Tablet500mg  a :Tablet,  loze:SchematicParticular .
:BlisterOf10  a :Blister, loze:SchematicParticular .
:CartonOf3    a :Carton,  loze:SchematicParticular .

# Ten tablets to a blister. The containment is an eventuality AND schematic:
# this is how every blister is packed, not a particular packing that happened.
:tablets-in-blister
    a loze:Containment, loze:SchematicParticular ;
    loze:hasHolder              :BlisterOf10 ;
    loze:hasRepeatedContent     :Tablet500mg ;
    loze:hasNumberOfOccurrences 10 .

# Three blisters to a carton. Same shape, one tier up.
:blisters-in-carton
    a loze:Containment, loze:SchematicParticular ;
    loze:hasHolder              :CartonOf3 ;
    loze:hasRepeatedContent     :BlisterOf10 ;
    loze:hasNumberOfOccurrences 3 .

# Only what is on the dock is concrete.
:carton-SN-88412
    a :Carton, loze:ConcreteParticular ;
    loze:isConcretizationOf :CartonOf3 .
"""),
    ("Hang your own relations off loze's",
     "You do not have to model participation twice. Declare your domain relation "
     "a sub-property of the loze one it specialises, and anything written in your "
     "terms answers to the general one as well — so tooling that knows only "
     "<code>loze:isAgentIn</code> still finds your payers. The ontology does this "
     "to itself: <code>isRecipeIn</code> is under <code>isInstructionIn</code>, "
     "which is under <code>isStandardIn</code>.",
     """
:Payment rdfs:subClassOf loze:Eventuality .

:isPayerIn rdfs:subPropertyOf loze:isAgentIn .
:isPayeeIn rdfs:subPropertyOf loze:isRecipientIn .

:payment-8871
    a loze:ConcreteParticular, :Payment ;
    loze:atTime :2026-08-14 .

:acme-ltd     :isPayerIn :payment-8871 .
:supplier-ltd :isPayeeIn :payment-8871 .

# With rdfs:subPropertyOf entailment on, the general questions answer
# themselves. Without a reasoner these return nothing: the entailed triples
# have to be materialised by something.
#
#   ?who loze:isAgentIn       :payment-8871   -> :acme-ltd
#   ?who loze:isParticipantIn :payment-8871   -> :acme-ltd, :supplier-ltd
#
# The second one is the reason to bother. isAgentIn and isRecipientIn are
# both under isParticipantIn, so "who was involved in this" works across
# every domain that hung its relations off loze's, without naming any of
# them.
#
# Remember what the sub-property brings with it. isAgentIn runs Thing to
# Eventuality, so :acme-ltd :isPayerIn ... makes :acme-ltd a loze:Thing
# whether or not you wrote that down.
"""),
]

PREFIXES = """@prefix :     <https://example.org/> .
@prefix loze: <https://loze-ontology.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
"""


# Plain English for the terms that need it before the figures. The ontology's own
# skos:definition is precise and says nothing about what the term buys you.
IN_SHORT = {
    "SchematicParticular":
        "loze cuts particulars twice, and the two cuts are independent. A thing "
        "or an eventuality: something, or something going on. Schematic or "
        "concrete: tied to one place at a time, or able to turn up again "
        "elsewhere. Both cuts are declared as disjoint unions, so everything is "
        "on one side of each, and all four combinations are inhabited.\n\n"
        "The second cut is the one you will not have met. In RDF you get a class "
        "or an individual. A fact about a class is about the class; saying it of "
        "the members takes a restriction. An individual takes facts directly, "
        "but nothing is an instance of an individual. A car model has to do "
        "both. It has specifications of its own, and it has units.\n\n"
        "A schematic particular does both. Facts attach to it directly and a "
        "query finds it like any other subject, because it is a particular. "
        "Concrete particulars concretize it, which is how it repeats.\n\n"
        "It can also be made more specific without turning into a class, and "
        "there is usually more than one step. The Toyota Corolla is the model. "
        "The 1985 Corolla is a determination of it and is still repeatable — you "
        "can meet one anywhere. The car on my drive concretizes the 1985. All "
        "three are instances of the class Car, and Car never stops being a "
        "class.\n\n"
        "So each fact goes where it holds: the advertised weight on the model "
        "year, the weighbridge reading on my car. Determination is transitive "
        "and concretization carries through it, so my car counts as a unit of "
        "the Toyota Corolla without anyone writing that triple.\n\n"
        "None of this is confined to things. The cuts being independent means a "
        "happening can be schematic too, and plenty are. The 30,000-mile service "
        "is a procedure you can carry out anywhere, any number of times; the "
        "service your car had in March is one occasion, in one garage. The first "
        "is an eventuality and a schematic particular at once, and there is no "
        "trick to it — give it both types. A recipe, an assembly step, a packing "
        "arrangement, a clinical protocol all sit there.",
    "Eventuality":
        "One category for events, processes, states, qualities and relations. "
        "loze does not split them, because the lines between them do not hold up "
        "and you do not need them: anything you want to time, or attribute to "
        "someone, or give participants, is an eventuality.",
}


# The front page opened on where the idea came from — a 1970 philosophy paper —
# which tells a reader nothing about whether to keep going. This is the part that
# says what goes wrong without loze, in terms someone arrives already having.
WHY = """
<div class="why">
<p class="why-lead measure">Semantic Partners builds knowledge graphs in pharma, in
manufacturing, and for information exchange between government departments.
Different industries, different vocabularies, and the same two problems in all of
them.</p>

<h3 class="why-h">Time arrives late</h3>
<p class="measure">Nearly every question worth asking has a time in it. What did we
hold, what did it cost, who approved it, and as of when. Time usually gets added
once the model is settled, and from then on every query pays for it. RDF-star and
SPARQL 1.2 are the standards agreeing that this matters. We have always taken the
other route: if you care about it, model it.</p>

<p class="measure">So in loze a happening is an entity in its own right, with
participants and a period, and you can say as much about it as about anything
else &mdash; including when it stopped being the case. Nothing has to be bolted on
later, because the thing that carries the time was there from the start.</p>

<h3 class="why-h">A new place</h3>
<p class="measure">Every organisation has things it must describe that are neither
a class nor an individual. A bill of materials. A material master, which despite the
name is not material: it describes the thing in general, often from several
suppliers, and there is nothing in it to weigh. An ISA-88 recipe, which is made more
concrete at every step down the chain of recipe types &mdash; general, site, master
&mdash; and is still not concrete at the end of it. Only the batch is that. These
are real to the business and they change over time, and not one of them is something
you could put your hand on.</p>

<p class="measure">RDF offers a class, which cannot carry its own facts, or an
individual, which nothing can be an instance of. So people pun, one name doing both
jobs and two entities kept in step by hand. Or they add a domain class that does a
schematic particular's work without being called one, which is the commoner case and
the better instinct.</p>

<p class="measure">Either way the pattern is already in the model. What is missing is
the name &mdash; and until it has one, nothing can rely on it. No query can ask for
the repeatable things, no tool can treat them alike, and the next modeller along
invents it again somewhere else.</p>

<p class="measure">loze gives each of these a place of its own &mdash;
<a href="/Eventuality">eventualities</a> for the happenings,
<a href="/SchematicParticular">schematic particulars</a> for the repeatable things.
Both are ordinary subjects, so ordinary queries reach them.</p>

<p class="measure">Which is why this is public. A name that is ours alone solves
nothing: the next modeller still invents their own, and the two models still do not
meet. An ontology is worth most when it can be used freely, so loze is meant to be
taken, extended, and argued with.</p>

<p class="measure"><a href="/examples">The examples</a> are the quickest way to see
whether this is your problem. <a href="/terms">The terms</a> are the reference once
you know it is.</p>
</div>
"""


def in_short_html(name: str) -> str:
    """The plain-English block, one <p> per blank-line-separated paragraph."""
    return "".join(f'<p class="inshort measure">{e(para.strip())}</p>'
                   for para in IN_SHORT[name].split("\n\n") if para.strip())


def check_examples(union: Graph) -> None:
    """Every loze: term named in a worked snippet must exist. A hand-written
    example that quietly names a term the ontology dropped is worse than none."""
    known = {local(s) for s in union.subjects() if isinstance(s, URIRef)
             and str(s).startswith(NS)}
    bad = set()
    for title, _why, snippet in WORKED:
        # It must parse. A snippet a reader cannot paste into a store is not an
        # example, it is a picture of one.
        try:
            Graph().parse(data=PREFIXES + snippet, format="turtle")
        except Exception as exc:
            raise SystemExit(
                f"REFUSING TO BUILD — worked example {title!r} is not valid "
                f"Turtle: {exc}") from exc
        for name in re.findall(r"\bloze:([A-Za-z][A-Za-z0-9_-]*)", snippet):
            if name not in known:
                bad.add(name)
    if bad:
        raise SystemExit(
            "REFUSING TO BUILD — worked examples name terms that are not in the "
            f"ontology: {', '.join(sorted(bad))}")


def render_examples(union: Graph, defined_in: dict) -> str:
    """Every example in one place. The worked snippets first, because they answer
    a task; then the per-term examples, which answer 'what counts as one of these'."""
    # Prefixes once, not four lines of boilerplate before every snippet.
    prelude = ('<p class="why">Every snippet below assumes these prefixes.</p>'
               + ttl_html(PREFIXES))
    blocks = prelude + "".join(
        f'<div class="worked"><h3>{e(title)}</h3><p class="why">{why}</p>'
        f'{ttl_html(snippet)}</div>'
        for title, why, snippet in WORKED)

    ontologies = {str(o) for o in union.subjects(RDF.type, OWL.Ontology)}
    rows = []
    for s in sorted({s for s in union.subjects()
                     if isinstance(s, URIRef) and str(s).startswith(NS)
                     and str(s) != NS and str(s) not in ontologies},
                    key=lambda x: local(x).lower()):
        d = describe(union, s)
        if not d["example"]:
            continue
        rows.append(
            f'<div class="refrow"><span class="rt">'
            f'<a href="/{e(local(s))}">{e(d["label"])}</a></span>'
            f'<span class="rd">{e(d["example"])}</span></div>')

    body = f"""
<header class="top"><div class="wrap">
  <div class="trail"><a href="/">loze</a> / <span>examples</span></div>
  <h1>Examples</h1>
  <p class="lead measure">Turtle for the jobs people actually turn up with, then the
  ontology's own examples for every term that has one.</p>
</div></header>
<main><div class="wrap">
  {section("Worked examples", blocks)}
  {section(f"{len(rows)} terms, by example", "".join(rows))}
</div></main>
"""
    return shell("Examples — loze", alternates_for(""), body, here="/examples")


def render_terms(union: Graph, defined_in: dict) -> str:
    """The reference. Someone who already knows why loze exists and just needs a
    property lands here, not at the bottom of a page of philosophy."""
    classes = {c for c in union.subjects(RDF.type, OWL.Class) if str(c).startswith(NS)}
    roots = sorted([c for c in classes
                    if not any(p in classes for p in union.objects(c, RDFS.subClassOf))],
                   key=lambda x: local(x).lower())
    # Which module a class comes from is worth knowing on the reference page too,
    # and it is the same tag the front page carries.
    tags = {k: v for k, v in (defined_in or {}).items() if v}
    tree = "".join(class_tree(union, r, classes, tags=tags) for r in roots)

    ontologies = {str(o) for o in union.subjects(RDF.type, OWL.Ontology)}
    props = sorted({s for s in union.subjects()
                    if isinstance(s, URIRef) and str(s).startswith(NS)
                    and str(s) != NS and str(s) not in ontologies
                    and set(union.objects(s, RDF.type)) & PROP_TYPES},
                   key=lambda x: local(x).lower())

    # Grouped by the class they hang off, because that is how the question
    # arrives: "I have an eventuality — what can I say about it?"
    groups: dict[str, list] = {}
    heads: dict[str, str] = {}
    for p in props:
        doms = list(union.objects(p, RDFS.domain))
        named = [o for o in doms if isinstance(o, URIRef)]
        if named:
            key = local(named[0])
            heads[key] = f'from <a href="/{e(key)}">{e(key)}</a>'
        elif doms:
            # An anonymous domain is usually a union — say which classes, not
            # "Anything", which is both wrong and unhelpful.
            key = "~" + local(p)
            heads[key] = f"from {anon_expr(union, doms[0])}"
        else:
            key = "~~any"
            heads[key] = "on any subject"
        groups.setdefault(key, []).append(p)

    out = []
    for key in sorted(groups, key=str.lower):
        rows = [prop_row(union, p) for p in groups[key]]
        out.append(f'<div class="domgroup"><div class="domhead">{heads[key]}</div>{"".join(rows)}</div>')

    body = f"""
<header class="top"><div class="wrap">
  <div class="trail"><a href="/">loze</a> / <span>terms</span></div>
  <h1>Terms</h1>
  <p class="lead measure">Every class and every property. Properties sit under the
  class they attach to — find your thing, then read across.</p>
</div></header>
<main><div class="wrap">
  {section(f"{len(classes)} classes", f'<ul class="tree">{tree}</ul>')}
  {section(f"{len(props)} properties", "".join(out))}
</div></main>
"""
    return shell("Terms — loze", alternates_for(""), body, here="/terms")



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
    merged = canonical(merged)
    for ext, fmt in SERIALISATIONS:
        write_graph(merged, OUT / "loze", ext, fmt)

    # And as quads, which keep the module each statement came from — the one thing
    # the flattened download cannot tell you.
    canon_ds = Dataset()
    for slug_, _s in MODULES:
        cg_ = canonical(per_module[slug_])
        tgt = canon_ds.graph(URIRef(NS + slug_))
        # Canonical blank node labels are derived from structure, so two modules
        # containing the same shape get the SAME label — three of them do here.
        # Harmless while each graph stands alone, but in one dataset they merge,
        # and flattening the quads then loses the triples that collided. Namespace
        # them by graph. Still deterministic: the prefix is the slug.
        pfx = slug_ or "root"
        def rename(t, _p=pfx):
            return tuple(BNode(f"{_p}_{x}") if isinstance(x, BNode) else x for x in t)
        for t in sorted(cg_, key=lambda x: (str(x[0]), str(x[1]), str(x[2]))):
            tgt.add(rename(t))
        for pfx, ns_ in cg_.namespaces():
            tgt.bind(pfx, ns_, override=False)
    for ext, fmt in QUAD_SERIALISATIONS:
        data = canon_ds.serialize(format=fmt)
        if ext == "nq":
            data = "".join(sorted(l + "\n" for l in data.splitlines() if l.strip()))
        elif ext == "trig":
            import re as _re
            blocks = _re.findall(r"(?m)^(\S+)\s*\{\n(.*?)\n\}\n", data, _re.S)
            if blocks:
                head = data[:data.index(blocks[0][0] + " {")] if blocks[0][0] + " {" in data else ""
                body = "".join(f"{name} {{\n{inner}\n}}\n\n"
                               for name, inner in sorted(blocks, key=lambda b: b[0]))
                data = head.rstrip("\n") + "\n\n" + body
        (OUT / f"loze.{ext}").write_text(data, encoding="utf-8")

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
        cg = canonical(g)
        for ext, fmt in SERIALISATIONS:
            write_graph(cg, OUT / base, ext, fmt)
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

    # The two pages that are not generated from one term: a reference for someone
    # who already knows why loze exists, and every example in one place.
    check_examples(union)
    (OUT / "terms.html").write_text(render_terms(union, defined_in), encoding="utf-8")
    (OUT / "examples.html").write_text(render_examples(union, defined_in), encoding="utf-8")

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
