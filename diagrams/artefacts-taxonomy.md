# Loze artefacts, information, and instructions — class taxonomy

Subclasshood relationships between the classes defined in `artefacts-information-and-instructions.ttl`, rooted at `Object` (from `loze-foundation.ttl`) as the super-class of `Artefact`.

- `Object` (top-level class) is the super-class of `Artefact`.
- `Artefact` is the super-class of `Information Artefact`.
- `Information Artefact` is the super-class of `Text`.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#FBF8F3'}}}%%
flowchart TD
    Object("Object")
    Artefact("Artefact")
    InformationArtefact("Information Artefact")
    Text("Text")

    Object --> Artefact
    Artefact --> InformationArtefact
    InformationArtefact --> Text

    classDef node fill:#FADBC8,stroke:#D9834F,stroke-width:1.5px,color:#4A2C1B;
    class Object,Artefact,InformationArtefact,Text node;
```
