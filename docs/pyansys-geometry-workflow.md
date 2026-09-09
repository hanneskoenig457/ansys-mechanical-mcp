# PyAnsys Geometry with Workbench-owned CAD

## Status and decision boundary

This is the evidence-gated workflow for [issue #24](https://github.com/hanneskoenig457/ansys-mechanical-mcp/issues/24). The concrete harmless-part and downstream-handoff evidence is recorded in [issue #29](https://github.com/hanneskoenig457/ansys-mechanical-mcp/issues/29). The Workbench-linked SpaceClaim/PyAnsys Geometry path was validated on 2026-09-09. The standalone Geometry Service/Core path remains uninstalled and unvalidated.

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
| Shared ApiServer | `v251\\Addins\\ApiServer` is installed at build `25.1.0.877`.  Its manifest identifies a Discovery remote API server and its assemblies include Geometry gRPC services plus a v251 provider. | The installed SpaceClaim/Discovery stack has the required API-server component; a running session still has to load it and expose a listener. |
| Geometry Service/Core | The Ansys installer file map defines `GeometryService` as a component, but no `GeometryService`/`CoreGeometryService` directory, service, registry key, or candidate server executable is present. | Treat the standalone Geometry Service/Core as not installed on this VM; do not plan a local service launch without installing it deliberately. |
| Existing API session | At the time of the initial inventory, no SpaceClaim or Discovery process or API listener was observed. | A normal SpaceClaim session cannot be treated as a PyAnsys Geometry endpoint merely because its shared ApiServer component is installed. |
| Python client | The repository's CPython is 3.14.2; `ansys-geometry-core==0.17.2` is installed in its project-local `.venv`. | The CPython client is ready for the validated SpaceClaim endpoint; it does not launch a product itself in this workflow. |
| Licence/API-server availability | Not checked by consuming a licence or launching CAD. | Keep the SpaceClaim ApiServer and licence status open until a controlled validation stage. |

The official compatibility policy states that PyAnsys Geometry 0.5 and later
has forward/backward compatibility checks and reports unsupported backend
methods at runtime.  It does not prove that a particular SpaceClaim 25.1
installation exposes the API server or every desired operation.  The current
project-pinned client is `ansys-geometry-core` 0.17.2 and requires Python 3.12 or
newer.  Sources: [Ansys compatibility guidance](https://geometry.docs.pyansys.com/version/dev/getting_started/compatibility.html)
and [the published package metadata](https://pypi.org/project/ansys-geometry-core/).

The resulting next decision is deliberately narrow: evaluate whether the
installed ApiServer loads into a Workbench-linked, visible SpaceClaim session
and exposes a usable PyAnsys Geometry endpoint.  Do not start a detached
SpaceClaim process from the client library as a substitute.  Its port,
loopback binding, existing-SSH-forward reuse, lifecycle and cleanup remain the
acceptance criteria of the next stages.

## Workbench read-only readiness — observed 2026-09-09

The currently launched Workbench session was reached through the established
Mac loopback forward at `127.0.0.1:51000`, using PyWorkbench with the already
documented local `security="insecure"` setting.  A read-only
`GetProjectFile()` / `GetAllSystems()` check returned the temporary project
`wbnew.wbpj` and zero systems.  The check created, opened, saved, updated, or
changed no Workbench project or model.

The Windows listener is bound as `::`:51000 and, for this session, accepts
both `::1:51000` and `127.0.0.1:51000`.  The existing IPv4 Mac forward works;
an IPv6 forward on port 51001 was also tested successfully and then removed.
This is transport evidence only.  It does not show a Geometry cell, a
SpaceClaim process, an ApiServer endpoint, or a CAD handoff.

Consequently, the read-only precondition of the Workbench-ownership stage was
passed.  Its next evidence gate was an explicitly authorised, disposable
`.wbpj` containing a Geometry cell and downstream Mechanical system; the
result is recorded below.

## Workbench-owned system — observed 2026-09-09

With explicit user approval, one in-memory `Static Structural (ANSYS)` system
was created in the already empty temporary Workbench project.  It has internal
name `SYS`, display text `Static Structural`, and the following read-back
components: `Engineering Data`, `Geometry`, `Model`, `Setup`, `Solution`, and
`Results`.  A second, independent `GetAllSystems()` read returned exactly that
one system and component set.

No CAD was attached or created, no Geometry editor or SpaceClaim ApiServer was
started, no Mechanical gRPC server was started, and the temporary project was
not saved.  The exact per-user temporary path is recorded only in the ignored
private handoff, not in tracked documentation or the public issue.  The
visible Workbench Session-1 instance and its established PyWorkbench forward
were reused; no existing project or Mechanical session was replaced.

This passes the Workbench-ownership gate for a disposable system.  The
reusable readiness entry point is `scripts/prepare-ansys-mcp-ready`; the
programmatic Schematic client is `ansys.workbench.core.connect_workbench` via
the existing port 51000 forward.  There is deliberately no reusable
Geometry-cell creation command yet.  The remaining gap for the next stage is
to demonstrate that this *same* Geometry cell launches or attaches the
Workbench-linked visible SpaceClaim ApiServer, then to connect PyAnsys Geometry
to that endpoint.  Native Computer Use could not independently capture the
Workbench window in this run because access to that app was denied.

## Workbench-linked SpaceClaim ApiServer — validated 2026-09-09

The initially embedded Geometry cell opened `DesignModeler`, as confirmed by
its Workbench property `CAD Plug-In = DesignModeler`. This is not the target
backend for PyAnsys Geometry. A separate `Geometry` system (`Geom`) was
therefore created and used to create the right-hand `Static Structural` system
(`SYS 1`) with Workbench's official `ComponentsToShare` construction. The
original embedded `SYS` system remains only as a non-destructive comparison.

Calling `Geom`'s `Geometry.Edit(IsSpaceClaimGeometry=True)` started the correct
visible `SpaceClaim.exe` as a direct child of the existing Workbench process,
but it did not expose a PyAnsys Geometry endpoint. A normal SpaceClaim session
is insufficient: the installed ApiServer manifest has to be present at
SpaceClaim startup. With user approval, the empty disposable editor was closed
through its Geometry container and reopened through the *same* `Geom` cell
using this StartupArguments value:

```text
/ADDINMANIFESTFILE="C:\Program Files\ANSYS Inc\v251\Addins\ApiServer\Presentation.ApiServerAddIn.Manifest.xml"
```

The replacement SpaceClaim process remained a direct Workbench child and its
command line included that manifest. It opened the ApiServer listener
`::50051`. A temporary `127.0.0.1:50051` forward was added through the
existing SSH ControlMaster only; `Modeler(..., transport_mode="insecure")`
then returned `backend_type=SPACECLAIM`, `backend_version=25.1.0`, and
`healthy=True`. The forward was immediately cancelled after the check; the
SpaceClaim and Workbench processes remain open.

This records a lifecycle rule for the reusable workflow: opening SpaceClaim
through Workbench is necessary for Geometry-cell ownership, while injecting
the installed ApiServer manifest at that same Geometry-cell startup is
necessary for a PyAnsys connection. Adding the manifest to an already-running
normal SpaceClaim process is not established; a controlled editor restart is
required. Never do that restart for a non-disposable editor without explicit
user approval, because `Geometry.Exit()` saves and updates its editor database.

Sources: [Workbench Geometry container API](https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/wb2_js/ContainerName56.html) and [PyAnsys Geometry existing-session guidance](https://geometry.docs.pyansys.com/version/stable/getting_started/existing/index.html).

## Workbench Geometry-cell creation and persistence — validated 2026-09-09

The separate `Geom` Geometry system and the downstream `SYS 1` Static
Structural system both resolve their Geometry container as `Geometry 1`.
They therefore share the same Workbench Geometry-cell output; the downstream
link is not a second direct file import into Mechanical.

For a connected existing SpaceClaim session, PyAnsys Geometry must read the
Workbench-opened design before editing it:

```python
modeler = Modeler(host="127.0.0.1", port=50051, transport_mode="insecure")
design = modeler.read_existing_design()
# sketch/extrude on design
modeler.close(close_design=False)
```

On the reference backend, the resulting active Workbench design was named
`Design1`. A 40 x 20 x 10 mm `ProofBlock` was created there with one body,
six faces, twelve edges, eight vertices, and 8,000 mm³ volume. It remained
visibly present in the Workbench-started SpaceClaim window before persistence.

Two rejected approaches are important guardrails:

- `modeler.create_design(...)` creates a separate active SpaceClaim document.
  Its body may be visible, but it is not automatically the Workbench Geometry
  document.
- Do not call `design.save()` to the already-open Workbench `Geom.scdocx`.
  SpaceClaim rejects that as a same-name open-document save. Do not call
  `modeler.close()` with its default either: `close_design=True` closes the
  active remote design.

The correct persistence owner is Workbench. After closing only the API client
with `close_design=False`, call the Geometry container's `Exit()` method. It
closes the visible editor and saves/updates its database. The disposable
Geometry-cell artifact grew from 38,836 to 66,822 bytes. Reopening the same
`Geom` cell with the ApiServer manifest and calling `read_existing_design()`
returned the same `ProofBlock` with the identical topology and volume. This
passes the Geometry-cell creation, visible-state, persistence, and reopen
evidence gate. Mechanical was not started for this validation.

## Downstream Workbench-to-Mechanical handoff — validated 2026-09-09

The downstream gate was repeated in a fresh, explicitly disposable Workbench
session. It contained only a `Geom` Geometry component system and one
downstream `Static Structural` system (`SYS`). Workbench assigned its Geometry
cell the internal component name `Geometry 1`, but both `Geom` and `SYS`
resolved that component to the same `Geometry` container. The numerical suffix
is an internal Workbench name; the shared container is the ownership evidence.

The Workbench-started SpaceClaim editor loaded the ApiServer manifest through
the `StartupArguments` argument of `Geometry.Edit(...)`. PyAnsys Geometry
called `read_existing_design()`, created `ProofBlock`, and read back one body,
six faces, twelve edges, eight vertices, and 8,000 mm³. After
`modeler.close(close_design=False)`, `Geometry.Exit()` persisted the Geometry
cell and closed SpaceClaim. The temporary `50051` forward on the existing SSH
ControlMaster was then removed.

Before starting Mechanical, the narrow downstream operation was `SYS`'s
**Model**-cell `Update()`. `Setup`, `Solution`, and `Results` were not
addressed. The documented Workbench path
`start_mechanical_server(system_name="SYS")` then returned Windows port
`58263` for a fresh Mechanical 2025 R1 gRPC instance. A prior local default was
held by an unrelated Codex remote proxy and accepted TCP without serving
Mechanical gRPC. The Ansys ControlMaster mapped the returned port to loopback
`127.0.0.1:50056`; that route passed a real gRPC round-trip. `50056` is now the
configured local Mechanical endpoint for both runtime paths.

Mechanical reported the expected temporary Workbench project directory,
`is_alive=True`, and no busy operation. A read-only PyMechanical body query
returned exactly one non-suppressed body named `Geom\\ProofBlock`. This is
direct downstream evidence that the Workbench-owned Geometry-cell output
arrived in Mechanical; it is not an engineering-model validation. No direct
CAD import, mesh generation, parameter publication, project save, solution
setup, or solve was performed.

The server lifecycle boundary was then deliberately exercised on the same
disposable `SYS` session. A controlled `Mechanical.exit()` stopped the current
system gRPC endpoint; Workbench's project server remained available. Starting
the system again only through `start_mechanical_server(system_name="SYS")`
returned a new Windows endpoint and, after a real read-only gRPC round-trip,
the body query again returned `Geom\\ProofBlock` as non-suppressed. This is an
additional Geometry-cell persistence/handoff check, not evidence of a solve,
project save, or a visible-Mechanical-GUI restart.

## Intended topology

```text
Codex skill / reproducible CPython command (Mac)
        |
        | existing SSH ControlMaster; loopback-only forwarding
        v
visible Workbench in Windows Session 1 -- 127.0.0.1:51000 --> PyWorkbench
        |
        +-- `Geom` Geometry cell -- visible, linked SpaceClaim + ApiServer
        |                                  ^
        |                                  | PyAnsys Geometry via temporary 50051 forward
        |                                  |
        +-- `SYS 1` Static Structural consumes the Geometry-cell output
        v                                  |
Workbench update --> Mechanical Model --> existing Mechanical MCP path
```

Reuse the existing Workbench launcher, interactive Windows-session task and
SSH ControlMaster. Do not create a second SSH process, GUI-automation
workaround or a new MCP server. A temporary loopback-only ApiServer forward
may be added to that existing ControlMaster for an active Geometry operation;
record and cancel it afterwards. Its ownership, loopback binding, cleanup
behaviour and compatibility have been demonstrated for SpaceClaim 25.1.

## Evidence-gated work sequence

1. **Inventory the supported backend (read-only) — completed 2026-09-09.** Record the installed
   SpaceClaim and Ansys versions, relevant licences, API-server availability,
   and the compatible `ansys-geometry-core` release.  Decide whether the
   first proof uses a Workbench-linked SpaceClaim API server or another
   officially supported backend.  Do not install packages or start CAD here.
2. **Prove Workbench ownership and visibility — completed 2026-09-09.** Reuse the existing visible
   Workbench/gRPC runtime to inspect a disposable `.wbpj` and its systems.
   With explicit mutation approval only, create or open a disposable project
   containing a Geometry cell and a downstream Mechanical system.  Stop
   before starting Mechanical or SpaceClaim API automation.
3. **Prove the PyAnsys Geometry connection — completed 2026-09-09.** Connect to the *same*
   Workbench-linked, visible SpaceClaim session and identify the backend and
   API-server lifecycle.  A second, detached SpaceClaim instance is a failed
   result for this path, not an acceptable substitute.
4. **Create and persist one harmless part — completed 2026-09-09.** Build a
   simple part with explicit units in the already-open Workbench design,
   inspect bodies/topology, disconnect the API client without closing the
   design, and let the Geometry cell save it through `Exit()`. Reopen and
   inspect it before involving Mechanical. Do not create a separate PyAnsys
   design or directly Save As over the open Workbench document.
5. **Prove downstream update — completed 2026-09-09.** Update the downstream
   Model cell, start Mechanical through Workbench gRPC, and read back the
   Geometry-cell body without solving. The later, separately authorised stage
   is to publish one or two CAD dimensions to the Workbench Parameter Set and
   validate one design-point update.
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
