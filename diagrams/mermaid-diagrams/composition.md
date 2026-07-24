# Loze composition eventualities — class taxonomy

Subclasshood relationships between `Eventuality`, `Composition`, `Parthood`, and `Constitution`, based on `loze-foundation.ttl`.

- `Eventuality` is the super-class of `Composition`.
- `Composition` is partitioned into `Parthood` and `Constitution`.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#FBF8F3'}}}%%
flowchart TD
    Eventuality("Eventuality")
    Composition("Composition")
    Parthood("Parthood")
    Constitution("Constitution")

    Eventuality --> Composition
    Composition --> Parthood
    Composition --> Constitution

    classDef node fill:#FADBC8,stroke:#D9834F,stroke-width:1.5px,color:#4A2C1B;
    class Eventuality,Composition,Parthood,Constitution node;
```
