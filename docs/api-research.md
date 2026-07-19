# API Research

Track official sources and verified API decisions here.

## Primary Sources

- PyAnsys documentation: https://docs.pyansys.com/
- PyMechanical documentation: https://mechanical.docs.pyansys.com/
- Mechanical Scripting API documentation: https://scripting.mechanical.docs.pyansys.com/
- PyDPF documentation: https://dpf.docs.pyansys.com/
- Ansys Common MCP: https://github.com/ansys/pyansys-common-mcp
- Model Context Protocol Python SDK: https://github.com/modelcontextprotocol/python-sdk

## Questions To Resolve

- How should the server start Mechanical for the supported Ansys versions?
- Can the server attach to an already running Mechanical session?
- What is the most stable way to execute Mechanical scripts from PyMechanical?
- What structured model inspection data is available directly through PyMechanical?
- Which result files should PyDPF consume for the v0.1 Static Structural workflow?
- How should integration tests detect and skip when Ansys is not installed?
- Which geometry, mesh, and tree selection types are returned consistently by
  `CurrentSelection` in the supported Mechanical versions?
- Which geometric descriptors and model relationships can be read through
  stable official interfaces for each selected entity type?
- What should form the geometry and mesh revision fingerprints used to reject
  stale selection references?
- Can viewport image and camera context be captured consistently in a remote
  interactive Mechanical session?
- Is there a documented, stable selection-change event, or should the server
  continue to use explicit capture calls?

## Decisions

- PyMechanical launch/connect: use `ansys.mechanical.core.launch_mechanical()`
  to launch and `ansys.mechanical.core.Mechanical(...)` or
  `connect_to_mechanical(...)` to connect to an existing Mechanical server.
  Source: https://mechanical.docs.pyansys.com/version/stable/getting_started/running_mechanical.html
- PyMechanical gRPC transport: require `ansys-mechanical-core>=0.12.12` for the
  implemented boundary and pass `transport_mode` explicitly. PyMechanical
  documents `wnua`, `mtls`, and `insecure`; its platform defaults are WNUA on
  Windows and mTLS on Linux. Secure modes require 2024 R2/242 SP05+, 2025
  R1/251 SP04+, 2025 R2/252 SP03+, or any 2026 R1/261+ service pack. Earlier
  listed service packs support insecure transport only. PyMechanical 0.12.12's
  supported Mechanical boundary begins at 2024 R2/242, so the MCP blocks older
  revisions rather than interpreting the security matrix as full client support.
  Sources:
  https://mechanical.docs.pyansys.com/version/stable/user_guide/remote_session/grpc_security.html
  and
  https://mechanical.docs.pyansys.com/version/stable/getting_started/installation.html
- Local transport selection: default the MCP policy to `auto`, but only after
  mode remains explicitly `start` or `connect`. For a local start, resolve the
  exact executable through `ansys.tools.common.path.get_mechanical_path()`,
  derive its revision with `version_from_path()`, and apply the documented
  `has_grpc_service_pack()` rule before any launch call. Pass a requested
  three-digit revision into path discovery and pass the same resolved path back
  as `exec_file`; a requested/detected mismatch blocks launch. Cross-check an
  explicit SP marker in that executable's `builddate.txt` with PyMechanical.
  Unknown or conflicting evidence never authorizes automatic insecure
  transport; a persisted explicit local choice remains auditable. A confirmed
  legacy SP returns
  `MECHANICAL_INSECURE_TRANSPORT_OPT_IN_REQUIRED` with zero launch calls because
  that release cannot accept the newer host-binding argument. One persisted
  explicit local `insecure` choice is required; this is not a runtime fallback.
  Sources:
  https://tools.docs.pyansys.com/version/stable/api/ansys/tools/common/path/path/index.html
  and
  https://mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/core/misc/index.html
- Local `version` scopes path discovery, but remains a request rather than proof.
  Current `launch_mechanical()` documentation assigns `version` to PyPIM when
  `exec_file` is absent and identifies `exec_file` as the exact local selector.
  The derived exact-path revision is therefore authoritative. Preflight reports
  `detected_service_pack` only when the exact build metadata contains an
  explicit SP marker; otherwise it remains `null`. A validated exact executable
  is mandatory so local start cannot silently delegate to PyPIM.
  Source:
  https://mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/core/mechanical/index.html
- Transport retry boundary: never implement a secure-then-insecure launch
  retry. In PyMechanical 0.12.12, the observed SP compatibility exception is
  raised while command-line arguments are built before `subprocess.Popen`, so
  that exact failure starts no OS process. However, the chosen port has already
  been appended to PyMechanical's `LOCAL_PORTS`. Other failures can occur after
  process creation, and the launcher does not retain a process handle for a
  general rollback. The manager therefore makes at most one launch attempt and
  latches a start failure until MCP restart.
  Sources:
  https://github.com/ansys/pymechanical/blob/v0.12.12/src/ansys/mechanical/core/mechanical.py#L2129-L2172
  and
  https://github.com/ansys/pymechanical/blob/v0.12.12/src/ansys/mechanical/core/launcher.py#L127-L219
- Connect transport boundary: the client transport must match the existing
  server. There is no reliable pre-connection product/SP query, so connect mode
  never auto-downgrades. Explicit loopback classification uses only
  `localhost` or loopback IP literals, without DNS inference. Non-loopback auto
  mode selects mTLS; remote insecure requires a second explicit acknowledgement.
  WNUA is Windows-only and PyMechanical accepts only exact `localhost` or
  `127.0.0.1`; the adapter canonicalizes an accepted WNUA endpoint.
  Sources:
  https://mechanical.docs.pyansys.com/version/stable/user_guide/remote_session/grpc_security.html
  and
  https://github.com/ansys/pymechanical/blob/v0.12.12/src/ansys/mechanical/core/mechanical.py#L803-L844
- Treat `version` as a launch-only requested value and never as a connected
  version selector. Current stable PyMechanical notes that `version` selects a
  PyPIM product; exact local executable selection uses `exec_file`, which the
  session configuration now accepts and auto preflight resolves when omitted.
  The actual connected/started product version remains an inspection result and
  needs live validation.
  Source: https://mechanical.docs.pyansys.com/version/stable/user_guide/remote_session/overview.html
- PyMechanical script execution: use `Mechanical.run_python_script(...)` or
  `Mechanical.run_python_script_from_file(...)`; the API returns the string value
  of the last executed statement where possible.
  Source: https://mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/core/mechanical/Mechanical.html
- PyMechanical cleanup: use `Mechanical.exit(force=True)` only when lifecycle
  policy permits terminating the session. `force=True` avoids a UI confirmation
  prompt. Connected and started UI sessions therefore default to
  `cleanup_on_exit=False`; only a started headless session defaults to automatic
  cleanup. Configuration is immutable after manager creation.
  Source: https://mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/core/mechanical/Mechanical.html
- Environment executable diagnostics cover Python-side PyMechanical commands,
  not `AnsysWBU.exe`. Search `PATH` first and then the running Python
  environment's scripts directory. `mechanical-env` is a Linux-only embedding
  helper; its absence on Windows is not a workflow failure. A CLI hit does not
  prove a Mechanical product installation, license, GUI, or gRPC server.
  Sources:
  https://mechanical.docs.pyansys.com/version/stable/user_guide/cli/ansys-mechanical.html
  and
  https://mechanical.docs.pyansys.com/version/stable/user_guide/cli/mechanical-env.html
- Mechanical model inspection: use the Mechanical scripting `DataModel` object,
  including `AnalysisList`, `AnalysisNames`, and object lookup methods.
  Source: https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v261/Ansys/ACT/Interfaces/Mechanical/IMechanicalDataModel.html
- Mechanical solve: use the Mechanical scripting `Analysis.Solve(wait: bool)`
  method on a real analysis object.
  Source: https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v241/Ansys/ACT/Automation/Mechanical/Analysis.html
- PyDPF result summary: create `ansys.dpf.core.Model(...)` from a result file and
  use `model.metadata.result_info`, `model.metadata.meshed_region`, available
  results, and time/frequency support for v0.1 summaries.
  Source: https://dpf.docs.pyansys.com/version/stable/user_guide/model.html
- MCP application lifecycle: use the stable MCP Python SDK v1 `FastMCP`
  lifespan and access its typed state from tools through
  `ctx.request_context.lifespan_context`. Pin `mcp>=1.28.1,<2`; the v2 line was
  still beta on 2026-07-17 and changes server, context, testing, and HTTP
  lifecycle APIs.
  Sources:
  https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/docs/server.md#lifespan-management
  and
  https://github.com/modelcontextprotocol/python-sdk/releases/tag/v1.28.1
- MCP lifecycle transport boundary: stable v1 enters the lifespan once per
  `Server.run()`. That provides one application context for the stdio run, but
  v1 Streamable HTTP enters it per MCP session (or per request in stateless
  mode). The Mechanical lifecycle is therefore exposed over stdio only in this
  slice.
  Sources:
  https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/lowlevel/server.py
  and
  https://github.com/modelcontextprotocol/python-sdk/blob/v2.0.0b2/docs/migration.md#streamable-http-lifespan-now-entered-once-at-manager-startup
- MCP integration tests: use the official in-memory connected client/server
  helper so context-using tools run inside a real request and lifespan rather
  than calling `FastMCP.call_tool()` without a request context.
  Source: https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/docs/testing.md
- MCP blocking/error boundary: run synchronous PyMechanical operations and
  shielded cleanup through AnyIO worker threads. Return one structured
  `CallToolResult` and set `isError=true` when the internal `ToolResult` fails.
  Sources:
  https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/fastmcp/utilities/func_metadata.py
  and
  https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/docs/server.md#tool-error-handling
- PyAnsys Common MCP remains unadopted. The direct FastMCP context is sufficient
  for the current small product-specific server; adding another server layer
  would not improve this slice.

## Selection Context Decisions

Verified against the official Mechanical 2026 R1 and current PyMechanical
documentation on 2026-07-17. Runtime behavior still requires integration tests
against the exact locally supported Mechanical versions.

- Use native Mechanical as the first authoritative viewer and selection source.
  A neutral viewer or build123d/OpenCascade service remains a later adapter and
  is not required for the Mechanical prototype.
  Rationale: [Selection Context and Semantic CAE Interaction](selection-context-architecture.md)
- The first click-driven selection-context flow requires an interactive
  Mechanical GUI session. In PyMechanical remote mode, launch with
  `batch=False`; embedding is a batch-mode integration and does not provide the
  same interactive GUI selection path.
  Source: https://mechanical.docs.pyansys.com/version/stable/getting_started/choose_your_mode.html
- Read the current graphics selection from
  `ExtAPI.SelectionManager.CurrentSelection` through the Mechanical scripting
  API.
  Source: https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v261/Ansys/ACT/Interfaces/Common/ISelectionManager.html
- In remote mode, query and normalize the selection inside a controlled
  `run_python_script(...)` call, then return only a JSON-compatible snapshot.
  PyMechanical's remote interface exchanges scripts and string results rather
  than exposing the Mechanical object model directly across gRPC.
  Source: https://mechanical.docs.pyansys.com/version/stable/getting_started/choose_your_mode.html
- PyMechanical script scope can persist between calls. Put inspection/capture
  helpers in uniquely named functions that remove their own global binding
  before returning, rather than defining generic helper names at top level.
  Source:
  https://examples.mechanical.docs.pyansys.com/examples/01_tips_n_tricks/example_02_run_python_script_scope.html
- `CurrentSelection` is documented to return the more general `ISelectionInfo`.
  If the runtime object also exposes `IMechanicalSelectionInfo`, its documented
  surface includes the selection type, IDs, entities, and element-face indices.
  The Mechanical script must type-guard or capability-check that richer surface
  and otherwise return a partial snapshot with a warning. Version-specific
  integration tests must determine which interface and fields are populated for
  each supported selection type.
  Source: https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v261/Ansys/ACT/Interfaces/Mechanical/IMechanicalSelectionInfo.html
- The general `ISelectionInfo` surface documents `Id`, `Ids`, `Name`, and
  `SelectionType`. `Id` is the selection object's identifier; selected native
  entity identifiers come from `Ids`. The stable generated page currently
  points to a v242 stub, so runtime capability checks remain necessary.
  Source: https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v242/Ansys/ACT/Interfaces/Common/ISelectionInfo.html
- For `MeshElementFaces`, the official scripting example pairs `Ids[i]` with
  `ElementFaceIndices[i]`. The adapter preserves that positional pair only when
  both source arrays have a verified equal length and the values at the same
  original position are readable. Parse failures never compress the arrays into
  new, false pairs; partial values are retained with warnings.
  Mechanical face indices must not be presented as MAPDL face numbers.
  Source: https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/act_script/act_script_examples_print_selected_element_faces.html
- Capture `Tree.ActiveObjects` separately because graphical geometry selection
  and active tree-object context are related but not identical signals.
  Source: https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v261/Ansys/ACT/Automation/Mechanical/Tree.html
- Use Mechanical named selections to persist accepted scopes where appropriate,
  but never assume they survive a geometry update unchanged. Revalidate their
  contents before applying an action.
  Sources:
  https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v261/Ansys/ACT/Automation/Mechanical/NamedSelection.html
  and
  https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/wb_sim/ds_selection_obj_define.html
- Keep native IDs scoped to the source project, model, and geometry/mesh
  revision. MCP can transport and enrich a reference, but it does not solve
  cross-kernel topological naming.
- Keep observed CAE facts, deterministically derived relationships, semantic
  interpretations, and action intent as separate fields in the MCP contract.
  Inferred engineering roles must include evidence and uncertainty.
- Keep deterministic capture independent from semantic explanation. A caller
  must be able to retrieve and use the native selection snapshot without an LLM
  interpretation step.
- Re-resolve and validate a target in Mechanical immediately before mutation.
  Require a preview and explicit confirmation for consequential actions.
- Start with an explicit `capture_current_selection`-style operation. Do not
  claim event-driven synchronization until a documented stable event has been
  verified.
- If a future custom picking surface is needed, Mechanical documents both
  ray-casting helpers and graphics access. These are research inputs, not
  implemented capabilities. The graphics-wrapper link below is an older
  development/v251 reference, not a verified 2026 R1 contract; find a current
  supported source before relying on it.
  Sources:
  https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v261/Ansys/Mechanical/Selection/SelectionHelper.html
  and
  https://scripting.mechanical.docs.pyansys.com/version/dev/api/ansys/mechanical/stubs/v251/Ansys/ACT/Common/Graphics/MechanicalGraphicsWrapper.html

## Implemented and Validated Boundary

### Returned Windows evidence before this change

The licensed validation machine reported PyMechanical 0.12.12 with Mechanical
2025 R1 revision 251, SP03, build `R251RC2P03`. A configured local UI start on
port 10000 failed before the GUI with `MECHANICAL_SESSION_START_FAILED` and
PyMechanical's message that revision 251 requires SP04+ for secure transport.
This is external live evidence supplied to the Mac development cycle, not a
round trip performed on this Mac. The new transport preflight and explicit
legacy opt-in path still require fresh Windows validation.

Implemented in this repository:

- a lazy, persistent `MechanicalSessionManager` in the FastMCP lifespan;
- explicit start/connect, version, host, port, batch/UI, cleanup, and ownership
  configuration;
- pre-launch `auto` transport selection for an exact local executable, explicit
  legacy-local insecure opt-in, no start retry, remote mTLS default, and
  acknowledged-only insecure remote connect;
- structured runtime transport/preflight/attempt context on both inspection and
  selection results;
- immutable cleanup policy plus idempotent cleanup after success and retained
  session state for retry after a cleanup failure;
- structured `inspect_mechanical_model` and `capture_current_selection` tools;
- a JSON-compatible `SelectionSnapshot` with native IDs, supported normalized
  types, active tree context, nullable model/revision fields, deterministic
  summary, `capture_status`/`is_complete`, warnings, and errors;
- source-position-preserving element-face pairs and a 1,000-item bound applied
  before Mechanical-side JSON serialization. Known source counts remain in the
  snapshot; truncation produces `capture_status="partial"`;
- capability separation between general selection fields and richer
  `Entities`/`ElementFaceIndices` fields;
- opt-in real Mechanical integration tests that are skipped by default.

Validated without Ansys through injected fakes and an in-process MCP round trip:

- explicit configuration, start and connect behavior, session reuse, immutable
  ownership, UI-safe defaults, retryable/idempotent cleanup, concurrent-call
  serialization, async offload, and enforced stdio-only transport;
- compatible auto selection, legacy-SP zero-launch opt-in, explicit local
  insecure selection, unknown-preflight refusal, revision mismatch and
  unsupported-release rejection, loopback/remote policy, remote-insecure
  acknowledgement, one-attempt start failure latching, and retryable connect failures;
- dependency, launch/license-like, connect, script, parse, GUI-mode, and invalid
  native-response failures;
- empty, single, multiple, general-interface, rich-interface, mesh ID,
  element-face, parse-position, bounded/truncated, unknown-type, and active-tree
  selection payloads;
- strict JSON serialization and MCP registration.

Not validated against a real Mechanical runtime:

- whether every supported Mechanical release populates the documented fields in
  the same way;
- GUI selection capture for local and remote connected sessions;
- native proxy type text used for face/edge/vertex/body normalization;
- real license, transport, shutdown, and UI-thread failure behavior;
- exact Windows `builddate.txt` content, 251 SP03 explicit-insecure launch,
  legacy listener binding, WNUA/mTLS handshakes, and post-launch process behavior;
- any model/document/revision identifier beyond the nullable fields currently
  returned by the conservative script.

## Geometry Kernel Boundary

- build123d provides selectors for vertices, edges, wires, faces, and solids in
  its own OpenCascade topology. That makes it a plausible basis for a later
  external picker or independent geometry generator, but does not make its
  topology IDs valid Mechanical IDs.
  Source: https://build123d.readthedocs.io/en/stable/topology_selection.html
- Sharing an OpenCascade-based kernel can reduce geometry conversion work, but
  it does not by itself create stable identity across applications. OpenCascade
  topological naming depends on an application's data framework plus modeling
  operation history and must be recomputed when topology changes. A neutral
  file and similar kernels therefore do not remove the need for target-side
  resolution and ambiguity handling.
  Source: https://dev.opencascade.org/doc/overview/html/occt_user_guides__ocaf.html
- For existing native parametric models, the originating CAD/Workbench pipeline
  remains the parameter authority. A future build123d preprocessor is most
  credible for geometry authored there, independent generated variants, or an
  explicitly accepted lossy import/export workflow.

These findings are architecture inputs only. The project does not currently
depend on build123d or OpenCascade and has not opened the neutral-viewer
implementation track.

## Current Implementation Slice

`check_environment` still avoids importing PyMechanical or PyDPF. The two
Mechanical tools import PyMechanical lazily only when their configured session
must be established. Normal tests therefore remain independent of licensed
Ansys products.

Read-only selection capture is implemented and fake-tested. Semantic
description, target resolution, highlighting, native model mutation, solve
exposure, and DPF exposure are not part of this slice.
