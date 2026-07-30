# Loze's Foundation

Loze is meant as a simple upper-level ontology, which avoids unnecessary categorial distinctions and offers a gamut of highly flexible, easy to use modelling patterns. Its category systems is largely inspired by the Four-Category Ontology outlined by the philosopher Jonathan Lowe (2006, 2009), supplemented with the concept of a schematic particular investigated by Eddy Zemach (1970, 1992). In fact, the very name of the ontology consists of references to the two aforementioned philosophers: **Lo**we and **Ze**mach, hence **Loze**. 

Loze that category system with an apparatus of thematic relations that draws from decades of research at the interface of philosophy and linguistics (Parsons 1990 & 1995; Orilia 2019).

While it has independent philosophical motivations and could be implemented with other formal languages, Loze is specifically optimised for being implemented with the RDF syntax. Indeed, we will see that some of its features are also motivated by finding modelling patterns that are simpler than the conventional Semantic Web solutions.

## Loze's Architecture

Loze is partitioned into one foundational modules and a number of mid-level extensions. The foundational core is hosted in `/loze-foundation.ttl`: it is the most general, top-level part of Loze and is meant to be completely domain-independent. The extensions currently include the following:

1. An ontology of artefacts and information. This includes the general concept of an artefact (`loze:Artefact`), a few subclasses for information artefacts, and relations . 
2. An ontology of materials and composition: this introduces the concept of a substance (`loze:Substance`), which has as superclass the foundational class `loze:SchematicParticular`, as well as a few relations for modelling the material composition of objects and aggregates. 
3. A suggested social extension, which consists of highly general classes pertaining to the social domain, such as `loze:Person`, `loze:Group` and `loze:Organisation`.
4. A set of temporal relations for (i) relating eventualities to periods of time and for (ii) describing the connections between the periods of time themselves. 

The set of extensions is open to additions, so the ones included in this repository should not be viewed as exclusive.

## Loze Foundation and Its Category System

Loze Foundation can be carved itself into - which are highlighted by corresponding comments in the file: (i) a category system consisting of ten top-level classes and two logico-ontological relations, (ii) an apparatus of eighteen domain-independent thematic relations, (iii) five types of eventualities with their two specialised thematic relations, and (iv) two fundamental relations for linking eventualities. (NB the count of the relations does not include their inverses).

. Loze's category system consists of ten class, arranged on four hierarchical levels - that is, between the top-class and the bottom-level classes there are two levels of intermediate classes.

The top-level class of Loze is `loze:Entity`: this is a maximally comprehensive class that is meant to encompass everything that exists, is real, or is in the world. It is equivalent (`owl:equivalentClass`) to the built-in OWL class `owl:Thing`. The direct division of `loze:Entity` is into two direct subclasses, namely `owl:Class` and `loze:Particular`. `owl:Class` is defined in Loze the same way it is defined in the Semantic Web: a class is any entity that is a type or kind of entities, and which can have other entities as instances. The Loze concept of a particular largely correspond to the Semantic Web concept of an individual, but it is not perfectly equivalent: in . By contrast, in Loze a particular is any entity that is *not* a class - that is, any entity that is not a type or kind of entities. Consequently, in Loze `owl:Class` and `loze:Particular` are disjoint, and `loze:Entity` is a disjoint union (`owl:disjouintUnionOf`) of them.

Loze does not introduce any further ontological division under `owl:Class`, so the rest of this documentation will focus on the various subclasses of `loze:Particular` and the relations defined for linking particulars.

### The Parallel Divisions of Particulars 

The class `loze:Particular` has two direct divisions, based on two different criteria: one is based on inherence and modification, the other on spatial boundaries. The former is the division between those particulars that are modifications or qualifications of other particulars and those that are not: those are called respectively *eventualities* (`loze:Eventuality`) and *things* (`loze:Thing`).

![Loze's Top-level Taxonomy: Things vs Eventualities](/diagrams/images/loze-top-taxonomy-thing-eventuality.svg)

The other direct division of `loze:Particular` is between those particulars that are bounded to one place at a time and those that are not: those are called respectively *concrete particulars * (`loze:ConcreteParticular`) and *schematic particulars* (`loze:SchematicParticular`). .

![Loze's Top-level Taxonomy: Concrete Particulars vs Schematic Particulars](/diagrams/images/loze-top-taxonomy-schematic-concrete.svg)

Schematic particulars can indeed seem very similar to classes: both are repeatable, since both can ; classes are represented by their instances, schematic particulars are represented by their concretisations. We said that a schematic particular is presented wherever one of its concretisations is present; but by the same token why might say that a class is present wherever one of its instances is present. Given these similarities, one might wonder whether there is any substantive difference between classes and schematic particulars, and whether concretisation is just instantiation under a different name. However, there is one major disanalogy between classes and schematic particulars, which in our view justifies including the latter under the class `loze:Particular`: differently from a class, a schematic particular share the essential properties of its concretisations. For example, *War and Peace* has the same chapter division as its copies, and it is also a book; likewise, a workflow has the same division in steps as its implementations. By contrast, classes don't have any of the essential properties of their instances: a class of books is not a book, and a class of actions is not an action. At first glance, this might seem like a nuanced philosophical distinction of little relevance in an applied ontology, but in section we will see how the distinctive nature of schematic particulars can vastly simplify the patterns for formalising general statements.

### Fourth-level Classes

The class `loze:Thing` is further divided into four subclasses, based on the individual principles of their instances: `loze:Object`, `loze:Aggregate`, `loze:Place`, and `loze:PeriodOfTime`. Objects are those things that are individuated based on their form, internal organisation, or function: . Differently from objects, aggregates are individuated based on their material composition. Needless to say, this does not entail that objects have no material composition, but only that they are not individuated according to it. 

Places are those things that are individuated according to their position relative to other things: for example, . Finally, period of times are those things that are individuated according to their coordinates across the temporal axis - according to their "when", so to say.

![Loze's Top-level Taxonomy: Thing's Children](/diagrams/images/loze-top-taxonomy-thing-children.svg)

The division between concrete particulars and schematic particulars cuts across all the other subclasses of `loze:Particular`: there are concrete objects as well as schematic objects, concrete aggregates as well as schematic aggregates, concrete eventualities as well as schematic eventualities, and so on.

![Loze's Top-level Taxonomy: Complete View](/diagrams/images/loze-top-taxonomy-complete-view.svg)

### Concretization and Determination

. While we have only used the term "concretization" informally until now, we are actually proposing to have a specialised relation for expressing it in the ontology: `loze:isConcretizationOf`. This relation will have `loze:ConcreteParticular` as domain and `loze:SchematicParticular` as range. .

We have already seen a few analogies between schematic particulars and classes. Now we are going to see another one: just like classes, schematic particulars can entertain *subsumption* with each other. In philosophy and logic, "subsumption" is a broad term used for referring to an entity being a narrower case of another one - a *child*, in the jargon of graphs. In the Semantic Web, the subsumption between classes is represented formally using `rdfs:subClassOf`. However, schematic particulars can also be subsumed under other schematic particulars: for example, the 1869 version of *War and Peace* can be subsumed under *War and Peace*; heavy water can be subsumed under water; the Toyota Corolla Hatchback can be subsumed under the Toyota Corolla. Since schematic particulars are not classes, we cannot formalise those subsumption relationships in terms of subclasshood. Consequently, we have to introduce a specialised relation, which we propose to call *determination*: `loze:isDeterminationOf`. For example, we will say that the 1869 version of *War and Peace* is a determination of *War Peace*, that heavy water is a determination of water, and that the Toyota Corolla Hatchback is a determination of the Toyota Corolla. `loze:isDeterminationOf` will have `loze:SchematicParticular` as both domain and range.

It is worth stressing a few logical analogies between determination and subclasshood. First, just like subclasshood, determination is transitive: if *s* is a determination of *s'* and *s''*, then *s* is also a determination of *s''*. For example, the Toyota Corolla Hatchback Hybrid is a determination of the Toyota Corolla Hatchback, and thus also a determination of the Toyota Corolla.

Second, there is an analogy between instantiation and subclasshood on the one side, and concretization and determination on the other: just like instantiation is inherited through subclasshood, so concretization is inherited through determination. For example, *a* being an instance of *C* and *C* being a subclass of *C'* entails that *a* is also an instance of *C'*. An analogous rule holds for concretization and determination: *c* being a concretization of *s* and *s* being a determination of *s'* entails that *c* is also a concretization of *s'*. For example, a copy of the 1869 version of *War and Peace* is thereby a copy of *War and Peace*; a molecule of heavy water is thereby a molecule of water; a unit of the Toyota Corolla Hatchback is thereby a unit of the Toyota Corolla. 

In SPARQL, such an inference rule will be specified by the following construct-query:

```
PREFIX loze: <http://loze-upper-level-ontology.org/> 
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 

CONSTRUCT { ?x loze:isConcretizationOf ?z . }
WHERE { ?x loze:isConcretizationOf ?y .
        ?y loze:isDeterminationOf ?z . 
    }
```

For brevity, we propose to call this rule *concretization inheritance*. In this repository, this and potentially other custom inference rules are hosted in the folder `/inference-rules`.

## Eventualities and Participation

One distinctive feature of Loze is the scope of the category of *eventualities*, which is a direct subclass of `loze:Particular` disjoint from `loze:Thing`. This top-level class encompasses those entities that in other ontologies are variously called "events", "processes", "qualities", "activities", "relations" etc... . While those are usually considered to be disjoint categories, we believe that the criteria used for distinguishing between them are philosophically superficial and impractical. 

For example, events are commonly characterised as entities that occur or happen over time to other entities; many philosophers and ontologists would also agree that events, differently from things or objects, are extended over time and divide into temporal parts. However, an event can also be viewed as a relation, because it involves multiple entities considered in a given order or according to certain roles. 

Another common distinction is that between those conditions of qualifications that are static - that is, don't consist in change - and those that are dynamic. While *prima facie* clear, this distinction is difficult to apply on a case-by-case basis. Consider John sitting on a sofa for a given period of time: on the one hand, one is inclined to think that there is no change at work, since John sitting consists in him keeping the same position for a while; on the other hand, we know from physiology that core, spine, and hip muscles have to function in order to maintain the body in a certain configuration. Likewise, consider a body maintaining a given temperature for a period: here again, we are inclined to view this as a quality or a state of the body; on the other hand, we know from kinetic gas theory that its temperature equals the average kinetic energy of its particles, so it actually consists in the combination of various microscopic motions.

Other ontologies distinguish between happenings that are instantaneous and other - in HQDM, those are called respectively *events* and *activities*. Again, this is also an ephemeral distinction, since ; in addition to that, all the changes that we observe in natural sciences take a period of time - which might be very brief, but not duration-less. As a result, any supposed ontological distinction between events and activities collapses into the vague distinction between short-lived happenings and longer happenings, which is too loose to be useful.

Overall, we conclude that what is common among those entities is more robust and more relevant than their differences: these are all entities that make some other entities be in a certain way; in other words, they are the *way* in which other entities are. In Lowe's Four-Category Ontology, they are aptly called *modes* (2006, 2009). Unfortunately, the term "mode" would be very confusing in an industry setting, because it can easily make one think of the functional settings of a device. As an alternative, we propose the term *eventuality*, which is more neutral than cognate terms. Compared to "event", "eventuality" does not have a dynamic connotation, and it does not suggest a brief duration. Differently from "action" and "activity", it is not commonly associated with the performances of agents - that is, beings with deliberative capacities. Finally, "eventuality" is loose enough to encompass relations and qualities, for which the term "event" would be forced.

In practical terms, the main rationale for the class `loze:Eventuality` is the construction of a highly versatile reification pattern that can be easily applied across domains and enables temporal modelling: indeed, temporal references can be represented by simply positing an eventuality and linking it to a period of time. The entities that are modified or qualified by an eventuality are its *participants*. In section , we will walk through the apparatus of thematic relations of Loze, which enable its users to specify the different ways in which entities are involved in an eventuality.

## Thematic Relations

. The relation `loze:isParticipantIn` is the top thematic relation, in the formal sense that any other thematic relation is a sub-relation of it. That being said, in most contexts `loze:isParticipantIn` will be too broad to be informative: therefore, we propose a gamut of more specific sub-relations. These are still domain-independent, and yet are informative enough .

For a one-by-one illustrations of Loze's thematic relations, we redirect to the detailed annotations contained in the file `/loze-foundation.ttl`. Here we are going to offer a quick overview of their scope. For example, `loze:isAgentIn` is the relation for specifying who does things in the context - more formally, for picking the participant that causes changes upon other participants. On the other hand, `loze:isAffectedIn` is meant for specifying the participant that is being acted upon by some other participat. These two are very flexibile yet informative relations that can be applied whenever one entity does something to another one. Similarly, `loze:isInstrumentIn` allows us to specify the means by which an eventuality is performed, and can applied across any domain: a kitchen knife is the instrument in a slicing, a debit card is the instrument in a payment, a duct network is the instrument in the supply of water, and so on. Relations like `loze:isRecipientIn` and `loze:isBeneficiaryIn` are meant for specifying respectively the entity on which something is conferred or transferred and the entity that benefits from an eventuality. A dedicated set of relations - - `loze:isDestinationIn`, `loze:isOriginIn`, `loze:isWaypointIn` - are intended for representing the locations or the reference points involved in an eventuality.

This apparatus of domain-independent thematic relation should not prevent an organisation from adding more specific sub-relations of `loze:isParticipantIn`, whenever that's required by their use case. For example, an organisation dealing with payments might introduce `:isPayerIn` as a sub-relation of `loze:isAgentIn` and `:isPayeeIn` as a sub-relation of `loze:isRecipientIn`.


## References

Lowe, E. J. (2006). *The Four-Category Ontology*, Oxford: Oxford University Press.

Lowe, E. J. (2009). *More Kinds of Being*, Wiley-Blackwell.

Orilia, F. (2019). "Relations, O-roles and Applied Ontology", *Philosophical Inquiries*, 7 (1), 115-32.

Parsons, T. (1990). *Events in the Semantics of English*, MIT Press.

Parsons, T. (1995). "Thematic Relations and Arguments", *Linguistic Inquiry*, 26 (4): 635-62.

Zemach, E. M. (1970). "Four Ontologies", *The Journal of Philosophy*, 67 (8): 231-47.

Zemach, E. M. (1992). *Types: Essays in Metaphysics*, E. J. Brill Publishers.



