# Roadmap

## v0.1 Mechanical MVP

Goal: control and postprocess an existing Static Structural Mechanical analysis.

Current state: `check_environment`, read-only `inspect_mechanical_model`, and
read-only `capture_current_selection` are exposed through MCP. Mechanical tools
share one lazy stdio lifespan context with explicit start/connect ownership and
idempotent cleanup. This path is fake-tested, including an in-process MCP round
trip, but still needs opt-in validation against a real licensed Mechanical
installation.

Internal helpers for controlled scripting, an existing Static Structural solve,
and PyDPF metadata remain fake-tested and deliberately unexposed.

Implemented foundation:

- Check local Python/PyAnsys environment.
- Start or connect to Mechanical through PyMechanical.
- Run controlled Mechanical scripts.
- Inspect model/project state at a basic level.
- Solve an existing Static Structural analysis.
- Extract PyDPF result metadata and available-result names.

Only environment diagnostics, session lifecycle, model inspection, and native
selection capture are MCP-exposed today. Solve and result bullets remain v0.1
targets, not current public tools.

## v0.2 Native Mechanical Selection Context

Goal: let a user select real model entities in interactive Mechanical and
retrieve a read-only, structured, revision-scoped context through MCP. This
must be useful without an LLM explanation.

Implemented and awaiting live validation:

- Capture the current graphical selection and active tree objects explicitly.
- Handle empty, single, and multiple selections plus supported geometry, node,
  element, and element-face selection types without inventing unavailable data.
- Return supported entity types, native IDs, available model context, nullable
  revision fields, deterministic summaries, completeness status, bounded arrays,
  and explicit warnings/errors.
- Cover the fake path with unit tests and the public tools with an in-process MCP
  round trip.

Next validation work:

- Run the default-skipped integration tests against Mechanical 2026 R1 in an
  interactive `batch=False` or explicitly declared GUI-connected session.
- Confirm native runtime type text and actual population of `Ids`, `Entities`,
  `ElementFaceIndices`, and `Tree.ActiveObjects` for representative selections.

Later potential capabilities:

- Enrich the snapshot with active tree and model relationships only where stable
  official APIs and real integration tests support them.
- Re-resolve and re-highlight a stored native target as the first round-trip
  proof, rejecting stale or ambiguous references.
- Add an optional Mechanical viewport image only after the GUI capture path is
  validated in the supported runtime.

See
[Selection Context and Semantic CAE Interaction](selection-context-architecture.md)
for the accepted prototype contract and safety boundary.

## v0.3 Semantic Mechanical Workflows

Goal: add optional evidence-based explanations and prove a safe, reviewable
action protocol while reducing reliance on generic scripts.

Potential capabilities:

- Explain a selected entity using observed facts, related model objects,
  explicitly labeled interpretations, and missing context.
- Create a structured action plan that declares parameters, units, target and
  product capabilities, prerequisites, warnings, and expected changes.
- Preview the plan without mutation, then require the exact preview identifier
  and unchanged model revision for apply.
- Resolve the target again immediately before any mutation and stop on
  ambiguity.
- Demonstrate one end-to-end flow: select, explain, preview, apply, solve, and
  summarize results.

The first mutating action and physical phenomenon will be chosen explicitly
after the selection prototype is validated. Mesh controls, mapped CSV fields,
loads, contacts, material models, and coupled workflows are illustrative
examples only, not roadmap commitments.

## v0.4 Prepared Project Orchestration

Goal: orchestrate prepared Workbench projects and parameters after the native
Mechanical workflow reveals which parameter pipeline is actually needed.

Potential capabilities:

- Open Workbench projects.
- Locate Mechanical systems.
- Launch Mechanical for a selected system.
- Manage project files and working directories.
- Inspect and update already prepared parameters through verified official
  interfaces.

## Research Gate: Neutral Geometry Context

Goal: decide from measured native-prototype gaps whether a neutral viewer or
build123d/OpenCascade adapter is worth its additional geometry-mapping cost.

Reasons to open this track can include:

- A common selection experience is required across several CAE products.
- Native Mechanical cannot expose sufficient selection or visual context.
- Code-defined geometry generation is a core parameter-study workflow.
- Geometry must be inspected or changed independently of a proprietary CAE
  session.

Until one of these needs is demonstrated, use the native Mechanical viewer and
its geometry model as the source of truth.

If opened, evaluate the neutral viewer/picking role separately from the
independent build123d CAD/preprocessor role. Sharing an OpenCascade-based kernel
can help geometry exchange, but does not provide universal, revision-stable
entity IDs across products.

## Later

- PyMAPDL/APDL fallback for solver-near workflows.
- Abaqus, ANSA, NX, Simpack, Fluent, or other product adapters only after the
  Mechanical path establishes a useful neutral context and action contract.
