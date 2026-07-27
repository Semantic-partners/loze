# Loze top-level taxonomy (Entity / Class / Particular / Schematic / Concrete)

Subclasshood relationships between `Entity`, `Class`, `Particular`, `Schematic Particular`, and `Concrete Particular`, based on `loze-foundation.ttl`. Every arrow points from a class to its super-class.

- `Entity` is partitioned into `Class` and `Particular`.
- `Particular` is partitioned into `Schematic Particular` and `Concrete Particular`.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#FBF8F3'}}}%%
flowchart BT
    Entity("Entity")
    Class("Class")
    Particular("Particular")
    SchematicParticular("Schematic Particular")
    ConcreteParticular("Concrete Particular")

    Class --> Entity
    Particular --> Entity
    SchematicParticular --> Particular
    ConcreteParticular --> Particular

    classDef node fill:#FADBC8,stroke:#D9834F,stroke-width:1.5px,color:#4A2C1B;
    class Entity,Class,Particular,SchematicParticular,ConcreteParticular node;
```
