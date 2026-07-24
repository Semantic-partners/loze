# Loze top-level taxonomy

Subclasshood relationships between Loze's top-level classes, based on `loze-foundation.ttl`.

- `Entity` is partitioned into `Class` and `Particular`.
- `Particular` is partitioned into `Thing` and `Eventuality`.
- `Thing` is partitioned into `Object`, `Aggregate`, `Place`, and `Period of Time`.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#FBF8F3'}}}%%
flowchart TD
    Entity("Entity")
    Class("Class")
    Particular("Particular")
    Thing("Thing")
    Eventuality("Eventuality")
    Object("Object")
    Aggregate("Aggregate")
    Place("Place")
    PeriodOfTime("Period of Time")

    Entity --> Class
    Entity --> Particular
    Particular --> Thing
    Particular --> Eventuality
    Thing --> Object
    Thing --> Aggregate
    Thing --> Place
    Thing --> PeriodOfTime

    classDef node fill:#FADBC8,stroke:#D9834F,stroke-width:1.5px,color:#4A2C1B;
    class Entity,Class,Particular,Thing,Eventuality,Object,Aggregate,Place,PeriodOfTime node;
```
