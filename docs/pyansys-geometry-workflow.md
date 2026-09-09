# PyAnsys Geometry with Workbench-owned CAD

## Status and decision boundary

This is the proposed, evidence-gated workflow for [issue #24](https://github.com/hanneskoenig457/ansys-mechanical-mcp/issues/24).  SpaceClaim is installed on the reference Windows VM, but neither its PyAnsys Geometry API-server path nor a Geometry Service/Core path has been validated in this workspace.  Nothing in this document proves that either path works yet.

For a Workbench project, the `.wbpj` Project Schematic is the system of record.
External CAD belongs in that project's **Geometry** cell: create or attach it
there, update the project, and only then inspect the downstream Mechanical
model.  Do not import external CAD directly into Mechanical for a `.wbpj`
workflow.  Direct `GeometryImportGroup.AddGeometryImport()` remains limited to
an explicitly authorised standalone `.mechdb` workflow or a clearly labelled
compatibility experiment.

This keeps CAD provenance, SpaceClaim documents, parameter propagation,
design points, and downstream systems under Workbench ownership.  A fixed
external CAD import is still useful; it is just attached to the Geometry cell
rather than injected into Mechanical.

## Backend inventory — 2026-09-09

The following is an observed, read-only inventory for the reference VM.  It is
not a CAD-service connection or licence validation.

| Question | Observation | Consequence |
| --- | --- | --- |
| CAD product | SpaceClaim 2025 R1 (`2025.1.0.0`) is installed under Ansys `v251`. | SpaceClaim is the first candidate backend for the visible Workbench path. |
| Geometry Service/Core | Neither `GeometryService` nor `CoreGeometryService` is installed under `v251`. | Do not plan a local Geometry Service/Core launch for this VM. |
| Existing API session | No SpaceClaim or Discovery process, API-server artefact, or listener was observed. | A normal SpaceClaim session cannot yet be treated as a PyAnsys Geometry endpoint. |
| Python client | The repository's CPython is 3.14.2; `ansys-geometry-core` is not installed. | The current official release supports Python 3.12+, but installation is a later, explicit step. |
| Licence/API-server availability | Not checked by consuming a licence or launching CAD. | Keep the SpaceClaim ApiServer and licence status open until a controlled validation stage. |

The official compatibility policy states that PyAnsys Geometry 0.5 and later
has forward/backward compatibility checks and reports unsupported backend
methods at runtime.  It does not prove that a particular SpaceClaim 25.1
installation exposes the API server or every desired operation.  The current
PyPI release is `ansys-geometry-core` 0.17.1 and requires Python 3.12 or
newer.  Sources: [Ansys compatibility guidance](https://geometry.docs.pyansys.com/version/dev/getting_started/compatibility.html)
and [the published package metadata](https://pypi.org/project/ansys-geometry-core/0.17.1/).

The resulting next decision is deliberately narrow: evaluate a
Workbench-linked, visible SpaceClaim session with a PyAnsys Geometry ApiServer
path.  Do not start a detached SpaceClaim process from the client library as a
substitute.  Its port, loopback binding, existing-SSH-forward reuse, lifecycle
and cleanup remain the acceptance criteria of the next stages.

## Intended topology

```text
Codex skill / reproducible CPython command (Mac)
        |
        | existing SSH ControlMaster; loopback-only forwarding
        v
visible Workbench in Windows Session 1 -- 127.0.0.1:51000 --> PyWorkbench
        |
        +-- Workbench Geometry cell -- visible, linked SpaceClaim session
        |                                  ^
        |                                  | candidate: PyAnsys Geometry API server
        v                                  |
Workbench update --> Mechanical Model --> existing Mechanical MCP path
```

Reuse the existing Workbench launcher, interactive Windows-session task and
SSH forwarding.  Do not add a second SSH tunnel, GUI-automation workaround or
a new MCP server.  A SpaceClaim/Geometry endpoint, if the selected backend
requires one, is a later lifecycle decision after its ownership, loopback
binding, cleanup behaviour and compatibility have been demonstrated.

## Evidence-gated work sequence

1. **Inventory the supported backend (read-only).** Record the installed
   SpaceClaim and Ansys versions, relevant licences, API-server availability,
   and the compatible `ansys-geometry-core` release.  Decide whether the
   first proof uses a Workbench-linked SpaceClaim API server or another
   officially supported backend.  Do not install packages or start CAD here.
2. **Prove Workbench ownership and visibility.** Reuse the existing visible
   Workbench/gRPC runtime to inspect a disposable `.wbpj` and its systems.
   With explicit mutation approval only, create or open a disposable project
   containing a Geometry cell and a downstream Mechanical system.  Stop
   before starting Mechanical or SpaceClaim API automation.
3. **Prove the PyAnsys Geometry connection.** Connect to the *same*
   Workbench-linked, visible SpaceClaim session and identify the backend and
   API-server lifecycle.  A second, detached SpaceClaim instance is a failed
   result for this path, not an acceptable substitute.
4. **Create one parameterised harmless part.** Build a simple part such as a
   ring or block with explicit units, inspect bodies/topology, and save it in
   the Workbench Geometry cell.  Capture visible and programmatic evidence.
5. **Prove downstream update and parameters.** Update Workbench, read back
   the geometry in Mechanical, then publish one or two CAD dimensions to the
   Workbench Parameter Set and validate one design-point update.  Do not
   solve until a separately authorised engineering stage.
6. **Operationalise only validated behaviour.** Add the narrowest reusable
   command, skill routing and troubleshooting documentation.  Treat
   DesignXplorer/DOE as a later optional extension after its licence and the
   basic Parameter Set flow have passed.

## Safety and handoff rules

- Use a disposable project and non-confidential geometry while establishing
  the workflow.  Keep CAD, `.scdoc`, `.wbpj`, Workbench databases and results
  outside Git.
- Preserve an existing visible Workbench project.  The current 25.1 runtime
  cannot automatically attach to a GUI that has not exposed `StartServer()`;
  never replace a session that may contain unsaved work.
- The existing Mechanical-server selection intentionally requires a system
  with `Model` and `Solution`.  That is correct for Mechanical access, but it
  is not Geometry-cell discovery and must not be reused unexamined.
- A successful script invocation is not proof of CAD creation or handoff.
  Verify the visible SpaceClaim state, saved Geometry-cell artifact,
  Workbench update state and Mechanical body readback separately.
