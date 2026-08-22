# CAE project structure

## Design goals

The structure must answer four questions quickly:

1. What is the project and what is currently known?
2. Which source data and assumptions produced the model?
3. How can each important result be reproduced and validated?
4. What work is proposed or active, and where is its status tracked?

Use the following as a menu, not a mandatory empty skeleton.

```text
project/
├── README.md
├── AGENTS.md
├── docs/
│   ├── project-state.md
│   ├── model-and-assumptions.md
│   ├── validation-evidence.md
│   ├── reproduction.md
│   └── decisions/
│       └── decision-index.md
├── inputs/
│   ├── input-sources.md
│   ├── papers/
│   ├── measurements/
│   ├── cad/
│   └── datasheets/
├── workflow/
│   ├── workflow-index.md
│   ├── 01_geometry/
│   ├── 02_setup/
│   ├── 03_solve/
│   ├── 04_analysis/
│   └── 05_reporting/
├── deliverables/
│   └── deliverables-index.md
└── archive/
    └── archive-index.md
```

## Required core

- `README.md`: concise dashboard and navigation. It is not the full report.
- `AGENTS.md`: project-specific operating and safety rules for agents.
- At least one linked document that records the model/method and its limits.
- A reproducible link between important generated results and their producer.

## Optional areas

Create a directory only when it has real content or an imminent use.

- `inputs/papers/`: source publications; keep citation metadata and license or
  access notes in `input-sources.md`.
- `inputs/measurements/`: immutable original measurements. Never silently edit
  raw data; put cleaning and transformed data in the workflow stage that
  produced them.
- `inputs/cad/`: received CAD and source geometry. Generated or repaired CAD
  belongs beside its generating workflow unless the CAE application requires a
  fixed project-relative location.
- `inputs/datasheets/`: manufacturer data and specifications, with source and
  revision recorded.
- `workflow/`: ordered transformations. A stage document states inputs,
  method/tool/version, outputs, validation, and rerun command.
- `deliverables/`: intentionally published reports, plots, exports, or release
  packages. Do not duplicate every intermediate result here.
- `archive/`: superseded artifacts retained for a stated reason. Record the
  replacement and why the archived path must not be used.

## Large and confidential engineering files

Git tracks instructions, scripts, small tables, configuration, and evidence
that can safely be shared. Mechanical databases, result directories, large CAD,
raw measurement sets, and confidential papers need an explicit storage policy:

- ignore and keep in the working project when they are reproducible or local;
- use an approved artifact store or Git LFS only after size, licensing, and
  confidentiality are understood;
- commit a manifest with path, source, revision/checksum, and access method
  when the actual artifact cannot be committed.

Do not move an application-linked file for cosmetic consistency. Document the
exception in the root dashboard or relevant workflow document.

