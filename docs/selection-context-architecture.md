# Selection Context and Semantic CAE Interaction

Status: accepted architecture direction for the Mechanical prototype.
The deterministic read-only snapshot and `capture_current_selection` MCP tool
are implemented and fake-tested. Runtime validation against a licensed,
interactive Mechanical installation is still pending. Semantic explanation,
resolution, highlighting, and mutation remain unimplemented.

## Decision

Start with a native-first Ansys Mechanical prototype:

1. Mechanical remains the authoritative model, viewer, and selection source.
2. An MCP tool captures the current selection as deterministic structured
   context. This capability must work without semantic explanation.
3. A semantic layer may optionally explain the selection, state uncertainty,
   and propose actions.
4. Action planning remains separate from both capture and explanation.
5. Mechanical resolves the target again, previews the requested change, and
   validates the final action.

A neutral viewer or a build123d/OpenCascade-based geometry service remains a
possible later adapter. It is not a dependency for the first useful workflow.

This decision gives the project a short route to real engineering value while
preserving a path toward a vendor-neutral interaction layer.

## Capability Ladder

Implement and validate the capabilities in this order:

1. **Capture:** read the native current selection and active tree context.
2. **Enrich:** add only deterministic Mechanical facts and explicit warnings.
3. **Describe, optionally:** let a semantic consumer interpret those facts
   without changing the snapshot.
4. **Resolve:** re-identify and highlight a stored target in Mechanical, then
   reject stale or ambiguous references.
5. **Act, later:** preview and apply one explicitly chosen engineering action.

The first selection proof of concept ends after a read-only capture/enrichment
round trip. Explanation is valuable but optional. Mutation, including creating
a named selection, is not part of that first slice.

## What "Semantic Selection" Means

MCP does not make a selected edge or face semantic by itself. It provides the
structured boundary through which facts, interpretations, and actions can be
exchanged. The responsibilities must stay separate:

| Layer | Responsibility | Example |
| --- | --- | --- |
| CAE facts | Data observed directly in Mechanical | "One cylindrical face with native ID 42 is selected." |
| Derived relationships | Deterministic relationships queried from the model | "The face belongs to body `Housing` and is scoped by mesh control `LocalSize`." |
| Semantic interpretation | An evidence-based engineering hypothesis | "This may be a bearing seat or a contact interface." |
| Action intent | A structured, reviewable request | "Preview operation `X` on this target with these parameters and units." |
| CAE execution | Resolve, validate, preview, apply, and report | "The target still resolves exactly; the validated plan was applied." |

Consequently, `capture_current_selection` is the deterministic core capability.
A separate operation or MCP client can provide a semantic description, but it
must label observations and interpretations separately. An engineering role
inferred by a language model must never silently become a CAE fact.

## Context Contract

The exact schema should continue to evolve from real Mechanical integration
tests. The implemented `SelectionSnapshot` v1.0 already preserves the following
minimal concepts without claiming unavailable geometry or revision data.

### Current implemented snapshot boundary

The current contract lives directly under `core/` and is consumed by the
Mechanical adapter. It includes:

- source, provenance, schema version, UTC capture time, capture status, and an
  explicit completeness flag;
- configured session/ownership facts and available product/model names;
- native selection type, supported normalized entity type, count, entity
  entries, and native IDs;
- positional element/face-index pairs only when Mechanical returns equally
  sized documented arrays;
- active tree objects as a separate signal;
- nullable document/model/geometry/mesh revision fields plus an explicit list
  of unavailable fields;
- deterministic summary, raw safe fields, structured warnings, and structured
  errors.

Failed attempts use `capture_status="failed"`, `is_complete=false`, and an
unknown (`null`) count/empty state; they never claim that an unobserved selection
was empty. Successful but incomplete captures use `capture_status="partial"`.
Native selection, richer-entity, element-face, and active-tree arrays are
bounded to 1,000 returned items before JSON serialization. Where Mechanical
exposes a source count, the snapshot retains it while warning that returned IDs
or details were truncated. Consumers must check `is_complete` before treating
the returned arrays as exhaustive.

The adapter reads all native proxies inside one short, self-cleaning Mechanical script and
returns JSON text. It capability-checks the richer Mechanical selection fields
and returns a partial snapshot when only general `ISelectionInfo` fields are
available. Unit tests cover this boundary with fakes; no real proxy population
or GUI interaction has yet been confirmed.

### Future durable selection reference

A target reference identifies where the selection came from and the revision
in which it was valid:

```json
{
  "source": "ansys-mechanical",
  "project_id": "project-fingerprint",
  "model_id": "model-fingerprint",
  "geometry_revision": "geometry-fingerprint",
  "mesh_revision": "mesh-fingerprint-or-null",
  "selection_type": "geometry_entities",
  "entity_type": "edge",
  "native_ids": [42],
  "named_selection": null
}
```

Native IDs alone are not durable cross-tool identifiers. They are meaningful
only together with their source model and revision. Any identifier or revision
field that cannot be read reliably must remain `null` or explicitly unavailable;
the adapter must not manufacture a fingerprint from unstable hints.

### Future snapshot enrichment

Where the installed Mechanical version and selected entity type expose the
information, a snapshot can contain:

- entity type, native IDs, count, and selection mode;
- parent part, body, assembly path, material, and analysis association;
- geometric descriptors such as centroid, length or area, bounding box,
  normal, radius, and adjacency;
- related named selections, contacts, loads, supports, mesh controls, and
  result objects;
- active tree objects and the current analysis;
- units, coordinate systems, geometry revision, and mesh revision;
- an optional viewport image and camera state for visual context;
- explicit warnings for unavailable or version-dependent attributes.

The adapter should return partial, truthful data rather than manufacture fields
that Mechanical cannot supply reliably.

### Semantic description

The language-model-facing result can add:

- a concise natural-language summary;
- possible engineering roles with evidence and confidence;
- alternative interpretations;
- missing context and assumptions;
- compatible next actions and reasons an action may be invalid.

For example, "cylindrical face" may be an observed geometric fact, while
"probably a bearing seat" is an interpretation supported by its diameter,
location, neighboring bodies, contacts, and boundary conditions.

### Action intent and resolution result

An action request should reference the captured target but remain independent
of the Mechanical scripting command used to realize it. It should state:

- the engineering operation;
- target reference and expected entity type;
- parameters, units, coordinate systems, and provenance;
- required target and product capabilities;
- preconditions and validation rules;
- whether preview and explicit confirmation are required.

Before changing the model, the Mechanical adapter returns a resolution result:
target found or ambiguous, revision match, compatibility checks, planned CAE
objects, warnings, and the generated preview. Apply should consume the exact
preview or plan identifier and fail if the target revision or requested intent
has changed in the meantime.

## Native Mechanical Interaction Flow

For the first Ansys implementation, a controlled script can run inside an
interactive PyMechanical remote session. The script reads Mechanical's current
selection and active tree objects, converts supported properties into a
JSON-compatible snapshot, and returns that snapshot through the MCP tool. The
Mechanical/.NET objects themselves do not cross the process boundary.

```text
User selects geometry in Mechanical
              |
              v
MCP captures a read-only snapshot of selection and native context
              |
              v
Caller can inspect/use the facts directly or request an optional explanation
              |
              v
Later: user chooses or refines a separately planned engineering action
              |
              v
Mechanical re-resolves target -> validates -> previews -> applies -> reports
```

The first implementation should use an explicit capture call. It should not
depend on an undocumented selection-change event. Event-driven synchronization
can be added later if a stable official API is verified.

The first real integration test should start with empty, single, and multiple
geometry selections, active tree objects, unknown-type passthrough, and a fully
JSON-compatible response. Node, element, and element-face semantics should be
added as their runtime interfaces and ID/index relationships are confirmed in
the tested Mechanical version. Geometry descriptors, screenshots, camera state,
and revision fingerprints remain optional until their behavior has been
demonstrated rather than inferred from API names.

## Selection Origins and Native Resolution

Mechanical is the first selection origin, not the only origin allowed by the
long-term contract. A later external viewer may emit a neutral
`SelectionIntent` containing source document and revision, assembly path, pick
ray or hit point, entity kind, geometric descriptors, and neighborhood clues.
It must not send only a label such as `Face 17` and assume that Mechanical uses
the same topology.

The target adapter resolves the intent into one of these explicit outcomes:

- `exact`: one valid native target;
- `split` or `merge`: topology changed and requires review;
- `ambiguous`: several candidates remain;
- `unresolved`: no compatible target exists;
- `stale`: the source or target revision no longer matches.

Only `exact` can proceed automatically to a preview. The native target should be
highlighted for review whenever the selection originated outside Mechanical.

## Persistence and the Topological Naming Problem

Geometry entity IDs can change after CAD updates, geometry repair, remeshing,
or import through another kernel. MCP transports references but cannot solve
this topological naming problem.

The safe policy is:

1. Treat a captured selection as revision-scoped.
2. Re-resolve and validate it immediately before an action.
3. In a later mutating phase, materialize important scopes as Mechanical named
   selections when appropriate; do not do this in the capture-only slice.
4. Store geometric descriptors and hierarchy as a secondary fingerprint, not
   as proof of identity.
5. Stop on ambiguity instead of choosing the nearest-looking entity silently.
6. Revalidate named selections after geometry changes because their contents
   may also require an update.

This policy becomes especially important when a future CAD, build123d, or
second CAE adapter hands topology to Mechanical.

Using the same or a related geometry kernel does not remove this problem. It can
reduce translation differences and make similar descriptors available, but
stable identity also depends on each application's document, feature history,
assembly structure, import process, and topology evolution. A generic STEP/BREP
exchange therefore does not preserve a universal face or edge ID.

## Illustrative Examples Are Not Scope Commitments

Mesh refinement, mapped CSV fields, temperature or heat-flux loading, line
loads, contacts, ideal-plastic materials, coupled analyses, hotspots, and
similar-geometry queries have been discussed only to test whether the
architecture can express realistic requests. They are not promised tools,
roadmap items, or a decision about the first supported physical phenomenon.

The first action will be chosen later. Whatever it is, the workflow must first
decompose the request into compatible target scopes, units, product
capabilities, analysis prerequisites, and validation rules instead of attaching
every requested property blindly to the currently selected entity.

## Why Not Build the External Viewer First?

A neutral viewer could eventually provide a consistent picking experience for
Mechanical, Abaqus, ANSA, NX, Simpack, and other tools. build123d could also
become a useful parametric geometry producer. Those are valuable but distinct
roles and should not be bundled into one mandatory service:

- neutral viewer and selection broker;
- independent parametric CAD/preprocessor;
- topology-mapping service between geometry kernels;
- geometry variant generator for parameter studies.

For an existing native parametric model, the originating CAD or prepared
Workbench pipeline remains the authority for feature history and design
parameters. Importing STEP into build123d does not reconstruct that proprietary
history. build123d is a credible parameter master when the geometry is authored
there, when independent code-defined variants are desired, or when a deliberately
lossy neutral-file workflow is acceptable.

Building this first would also introduce a second geometry representation,
kernel translation, topology reconciliation, assembly and unit handling, a
viewer UI, and synchronization with every native model. It would delay learning
which context is actually missing from Mechanical.

The external path should be reconsidered when at least one of these conditions
is demonstrated by the native prototype:

- Mechanical cannot expose enough selection or visual context for useful
  interaction.
- The same user experience is needed across several CAE products.
- Geometry must be created or changed independently of proprietary CAD/CAE
  installations.
- Reproducible, code-defined geometry variants are a core workflow rather than
  an occasional need.

Until then, build123d is a research option, not the project's primary context
source or default parameterization pipeline.

## Product Narrative

The longer-term public-facing project story can be expressed as a target, not
as current support:

> Select a real entity in Mechanical, inspect its structured context, optionally
> ask for an evidence-based explanation, preview a valid engineering action,
> apply it in the native model, solve, and inspect the result through structured
> MCP tools.

Today only the first read-only selection and structured-context portion of that
sentence is implemented. Explanation, preview, mutation, solve exposure, and
result inspection through public MCP tools remain future stages.

This is a concrete Ansys prototype and, at the same time, a test bed for a later
vendor-neutral CAE interaction contract.

## Deferred Decisions

The following choices should be driven by experience from the native prototype,
not fixed now:

- which first physical phenomenon or mutating engineering action to support;
- Workbench, CAD, build123d, or direct CAE ownership of design parameters;
- whether build123d is needed first as a viewer, geometry generator, both, or
  neither;
- synchronization protocols for multiple simultaneous tools;
- whether any persistence mechanism stronger than revision-scoped native IDs
  and geometric hints can be justified;
- event streaming versus explicit snapshot capture;
- generalized adapters for Abaqus, ANSA, NX, Simpack, or other products.
