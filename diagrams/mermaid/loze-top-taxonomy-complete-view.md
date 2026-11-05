# Loze top-level taxonomy (complete view)

Subclasshood relationships between Loze's top-level classes, based on `loze-foundation.ttl`. Every arrow points from a class to its super-class.

- `Entity` is partitioned into `Class` and `Particular`.
- `Particular` is partitioned into `Thing` and `Eventuality`.
- `Thing` is partitioned into `Object`, `Aggregate`, `Place`, and `Period of Time`.
- `Particular` is **also** partitioned into `Schematic Particular` and `Concrete Particular`.

The two boxes are the two partitions of `Particular`. They are independent cuts, not four sibling classes: every particular falls on one side of each.

```mermaid
flowchart BT
    Entity["Entity"]
    Class["Class"]
    Particular["Particular"]
    Thing["Thing"]
    Eventuality["Eventuality"]
    Object["Object"]
    Aggregate["Aggregate"]
    Place["Place"]
    PeriodOfTime["Period of Time"]
    SchematicParticular["Schematic Particular"]
    ConcreteParticular["Concrete Particular"]

    Class --> Entity
    Particular --> Entity
    Thing --> Particular
    Eventuality --> Particular
    Object --> Thing
    Aggregate --> Thing
    Place --> Thing
    PeriodOfTime --> Thing
    SchematicParticular --> Particular
    ConcreteParticular --> Particular
    Object ~~~ Eventuality

    subgraph Happens ["things and happenings"]
        Thing
        Eventuality
        Object
        Aggregate
        Place
        PeriodOfTime
    end

    subgraph Repeats ["schematic and concrete"]
        SchematicParticular
        ConcreteParticular
    end
```
