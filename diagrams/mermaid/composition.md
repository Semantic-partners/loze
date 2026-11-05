# Loze composition eventualities — class taxonomy

Subclasshood relationships between `Eventuality`, `Composition`, `Parthood`, and `Constitution`, based on `loze-foundation.ttl`.

- `Eventuality` is the super-class of `Composition`.
- `Composition` is partitioned into `Parthood` and `Constitution`.

```mermaid
flowchart BT
    Eventuality["Eventuality"]
    Composition["Composition"]
    Parthood["Parthood"]
    Constitution["Constitution"]

    Composition --> Eventuality
    Parthood --> Composition
    Constitution --> Composition

```
