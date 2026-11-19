# Loze

An upper-level ontology largely inspired - with a few deviations and additions - by the four-category ontology outlined by the philosopher E. J. Lowe (2006), supplemented with the concept of a schematic particular explored by Eddy Zemach (1970).

A peculiar feature is the category of schematic particulars: these are repeatable like classes, but have many of the properties that are typical of ordinary individuals. While the concept of a schematic particular might come across as weird to those who are used to the class-individual duality, it has a robust philosophical underpinning, and we believe that it can provide surprisingly powerful design patterns; these could vastly simplify modelling in circumstances in which the standard solution would be use restrictions or punning.

## The site

The Turtle is the source. `docs/` is a generated view of it — one page per term,
plus a reference and a page of examples. It is **not** in git: build it first,
and rebuild it after editing any `.ttl`. Run these from the root of this repo:

    cd /path/to/loze

    python3 scripts/build.py     # writes docs/ — do this first
    python3 scripts/serve.py     # read it:    http://localhost:8788
    python3 scripts/check.py     # assert the output holds together

Deploying is the same build plus an upload:

    python3 scripts/build.py && npx wrangler pages deploy docs --project-name=loze

Add `--branch=<name>` to get a preview URL for a branch instead of publishing to
production.

Nothing to install and no virtualenv: `serve.py` is standard library only, and
`build.py` needs `rdflib`, which is already on the system Python. Pass a port if
8788 is taken — `python3 scripts/serve.py 9000`. `serve.py` finds `docs/` from
its own location, so an absolute path works from any directory.

Do not open the HTML files directly.

Opening `docs/Entity.html` from Finder gives you an unstyled page with dead
links. Every asset and link is an absolute path — `/style.css`, `/Entity` — and
under `file://` those resolve against your filesystem root. `python3 -m
http.server` fixes the stylesheet but not the links, because Cloudflare Pages
maps `/Entity` to `Entity.html` and a plain static server does not. `serve.py`
does both, and serves the RDF with the content types from `_headers`.

`npx wrangler pages dev docs` is the same thing through the real Pages runtime,
if you want to check `_headers` too.

Three places to start:

| page | what it is for |
|---|---|
| `/` | why loze exists — the four categories, schematic particulars |
| `/terms` | every class and property, properties grouped under the class they hang off |
| `/examples` | Turtle for common modelling jobs, then every term's own example |

## Licence

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Use it, extend it, build
on it, commercially or otherwise. Credit Semantic Partners.

The point of an upper ontology is that other people reuse its terms, so the licence
has to allow reuse term by term rather than whole. That rules out CC BY-ND, which
OBO Foundry bans for the same reason. CC0 was the other candidate and would have
given up the attribution.

Each module declares it, so it travels with the Turtle and not just with this file:

    loze: a owl:Ontology ;
        dcterms:license <https://creativecommons.org/licenses/by/4.0/> .

## Namespace

    https://loze-ontology.org/

Every term is identified by that IRI — `loze:Entity` is
`https://loze-ontology.org/Entity`. The domain is registered (Cloudflare, 2026-08-14)
and the modules declare themselves under it:

| module | ontology IRI |
|---|---|
| foundation | `https://loze-ontology.org/` |
| artefacts, information and instructions | `https://loze-ontology.org/artefacts-information-and-instructions` |
| materials and composition | `https://loze-ontology.org/materials-and-composition` |
| temporal relations | `https://loze-ontology.org/temporal-relations` |
| suggested social extension | `https://loze-ontology.org/suggested-social-extension` |
| suggested calendar extension | `https://loze-ontology.org/suggested-calendar-extension` |

The calendar extension ships a generator for date-based periods, in
`calendar-periods/`. Its guide is on the module page, `/suggested-calendar-extension`.
Its tests need PyYAML, and rdflib for the Turtle checks:

    python3 -m unittest discover -s calendar-periods

The domain now serves the site, but it is closed. Cloudflare Access sits in front of
it, so `https://loze-ontology.org/Entity` returns a redirect to a login for anyone
outside the Access policy, and an RDF client asking for `/loze.ttl` gets that login
page rather than Turtle. **The IRIs do not dereference for the public yet.** Everything
needed for them to is in place — a document per term, every module in Turtle, RDF/XML,
JSON-LD and N-Triples, each with its own content type — and removing the Access
application is the only step left. That is a decision about when to publish, not more
work.

Owning the domain is what makes that possible, and what stops the identity of these
terms resting on a name a stranger could register. It replaced
`http://loze-upper-level-ontology.org/`, which was never registered by anyone and
never used in anger, so the change was a rename rather than a migration: no redirect,
no `owl:sameAs` bridge.

Once it does open, publishing an IRI is a promise that it keeps resolving.
`scripts/check.py` asserts every term has a document and neither workflow deploys
without it, but nothing outside this repo enforces it — so renaming or dropping a
term breaks whatever already points at it.

**References**

## References

Lowe, E. J. (2006). *The Four-Category Ontology*, Oxford: Oxford University Press.

Zemach, E. M. (1970). "Four Ontologies", *The Journal of Philosophy*, 67 (8): 231-47.

