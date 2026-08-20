# Loze

An upper-level ontology largely inspired - with a few deviations and additions - by the four-category ontology outlined by the philosopher E. J. Lowe (2006), supplemented with the concept of a schematic particular explored by Eddy Zemach (1970).

A peculiar feature is the category of schematic particulars: these are repeatable like classes, but have many of the properties that are typical of ordinary individuals. While the concept of a schematic particular might come across as weird to those who are used to the class-individual duality, it has a robust philosophical underpinning, and we believe that it can provide surprisingly powerful design patterns; these could vastly simplify modelling in circumstances in which the standard solution would be use restrictions or punning.

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

The IRIs do not dereference yet — nothing is served at the domain. Owning it is what
makes that possible, and what stops the identity of these terms resting on a name a
stranger could register. It replaced `http://loze-upper-level-ontology.org/`, which was
never registered by anyone and never used in anger, so the change was a rename rather
than a migration: no redirect, no `owl:sameAs` bridge.

**References**

## References

Lowe, E. J. (2006). *The Four-Category Ontology*, Oxford: Oxford University Press.

Zemach, E. M. (1970). "Four Ontologies", *The Journal of Philosophy*, 67 (8): 231-47.

