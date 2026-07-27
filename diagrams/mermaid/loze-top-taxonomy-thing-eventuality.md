# Loze top-level taxonomy (core classes only)

Subclasshood relationships between Loze's top-level classes `Entity`, `Class`, `Particular`, `Thing`, and `Eventuality`, based on `loze-foundation.ttl`.

- `Entity` is partitioned into `Class` and `Particular`.
- `Particular` is partitioned into `Thing` and `Eventuality`.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#FBF8F3'}}}%%
flowchart BT
    Entity("Entity")
    Class("Class")
    Particular("Particular")
    Thing("Thing")
    Eventuality("Eventuality")

    Class --> Entity
    Particular --> Entity
    Thing --> Particular
    Eventuality --> Particular

    classDef node fill:#FADBC8,stroke:#D9834F,stroke-width:1.5px,color:#4A2C1B;
    class Entity,Class,Particular,Thing,Eventuality node;
```
