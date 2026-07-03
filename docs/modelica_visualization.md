# Modelica workflow visualization

Tento Mermaid diagram ukazuje tok dat a modelu ve webove aplikaci: od vstupnich
CSV souboru pres readery a docasnou SQLite databazi az po Python model,
OpenModelica simulaci a spolecny Plotly graf.

```mermaid
flowchart LR
    A["Libre CSV"] --> B["LibreCsvReader"]
    M["manual meals.csv"] --> C["ManualMealsCsvReader"]

    B --> D["ImportedData"]
    C --> D

    D --> E["Temporary SQLite"]
    E --> F["glucose_frame"]
    E --> G["insulin_frame"]
    E --> H["meals_frame"]

    F --> P["Python Gaussian response model"]
    G --> P
    H --> P

    F --> O["OpenModelica wrapper"]
    G --> O
    H --> O

    O --> MO["GaussianResponseGlucose.mo"]
    MO --> CSV["OpenModelica CSV result"]

    P --> V["Plotly comparison chart"]
    CSV --> V
    F --> V
```
