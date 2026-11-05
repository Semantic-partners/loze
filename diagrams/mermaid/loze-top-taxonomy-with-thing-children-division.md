# Loze top-level taxonomy

Subclasshood relationships between Loze's top-level classes, based on `loze-foundation.ttl`.

- `Entity` is partitioned into `Class` and `Particular`.
- `Particular` is partitioned into `Thing` and `Eventuality`.
- `Thing` is partitioned into `Object`, `Aggregate`, `Place`, and `Period of Time`.

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

    Class --> Entity
    Particular --> Entity
    Thing --> Particular
    Eventuality --> Particular
    Object --> Thing
    Aggregate --> Thing
    Place --> Thing
    PeriodOfTime --> Thing

```
