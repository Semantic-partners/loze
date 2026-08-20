# Loze suggested social extension — class taxonomy

Subclasshood relationships between the classes defined in `suggested-social-extension.ttl`, rooted at `Object` (from `loze-foundation.ttl`) as the super-class of `Living Being` and `Group`.

- `Object` (top-level class) is the super-class of `Living Being` and `Group`.
- `Living Being` is partitioned into `Animal` and `Plant`.
- `Animal` is partitioned into `Person` and `Non-Human Animal`.
- `Group` is the super-class of `Organisation` and `Organisation Subdivision`.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#FBF8F3'}}}%%
flowchart BT
    Object("Object")
    LivingBeing("Living Being")
    Animal("Animal")
    Plant("Plant")
    Person("Person")
    NonHumanAnimal("Non-Human Animal")
    Group("Group")
    Organisation("Organisation")
    OrganisationSubdivision("Organisation Subdivision")

    LivingBeing --> Object
    Group --> Object
    Animal --> LivingBeing
    Plant --> LivingBeing
    Person --> Animal
    NonHumanAnimal --> Animal
    Organisation --> Group
    OrganisationSubdivision --> Group

    classDef node fill:#FADBC8,stroke:#D9834F,stroke-width:1.5px,color:#4A2C1B;
    class Object,LivingBeing,Animal,Plant,Person,NonHumanAnimal,Group,Organisation,OrganisationSubdivision node;
```
