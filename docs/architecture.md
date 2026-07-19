# Architecture

The server should be organized as a small set of product adapters plus workflow tools.

## Layers

```text
MCP client
  |
  v
MCP server entrypoint
  |
  +-- FastMCP v1 lifespan: one lazy Mechanical application context (stdio)
  |     |
  |     +-- existing MechanicalSessionManager: start/connect, ownership, cleanup
  |
  +-- core: errors, tool results, product-neutral SelectionSnapshot
  |
  +-- products/mechanical: PyMechanical session, inspection, selection capture
  |     |
  |     +-- exact-executable gRPC transport preflight and safety policy
  |
  +-- products/dpf: PyDPF result extraction
  |
  +-- workflows/static_structural: higher-level workflow operations
  |
  +-- later selection stages: optional describe, then resolve/validate before mutation
```

## Design Intent

Use product-specific adapters for low-level operations and workflow modules for higher-level actions. This keeps later Workbench, Geometry, MAPDL, or Fluent support possible without turning the server into one large file.

For selection-aware interaction, the native CAE adapter remains the source of
truth. Mechanical supplies entity IDs and model relationships, and the MCP
layer normalizes that context into a revision-scoped snapshot. Semantic
explanation is an optional consumer of that snapshot, not a requirement for
selection capture. Mechanical resolves and validates the target again before
any later change is applied.

The responsibility boundaries are:

| Concern | Authority |
| --- | --- |
| Existing native CAD parameters and feature history | The originating CAD or prepared Workbench parameter pipeline |
| Executable CAE selection, model objects, mesh, loads, solve, and results | The target CAE application; Mechanical first |
| Structured transport of selection facts and action intent | Product-neutral MCP contracts |
| Engineering interpretation and proposals | Optional semantic orchestration, clearly separated from facts |
| Independent geometry generation or external picking | Optional later build123d/OpenCascade service |

An external viewer can therefore become another selection input, but it does
not become the authority for Mechanical topology. Its selection intent must be
resolved, highlighted, and validated by the Mechanical adapter.

The contracts, safety rules, and native-first decision are described
in [Selection Context and Semantic CAE Interaction](selection-context-architecture.md).

## Implemented Mechanical Application Context

The stable MCP Python SDK v1 lifespan yields one
`MechanicalApplicationContext` for the stdio server run. It owns the existing
`MechanicalSessionManager`, not a second session mechanism. Session creation is
lazy so `check_environment` never imports or starts PyMechanical. Mechanical
operations are serialized because MCP request handlers can run concurrently and
the Mechanical scripting API is not treated as thread-safe. Blocking
PyMechanical calls and cleanup run in worker threads so they do not block the
MCP event loop; shutdown cleanup is cancellation-shielded.

`inspect_mechanical_model` may establish an explicitly configured start/connect session.
`capture_current_selection` reuses it; in connect mode it may establish only the
connection to a server explicitly declared GUI-capable. In start mode capture
never launches a new empty instance. Shutdown follows the configured ownership
policy and the manager's `close()` path is idempotent after success and retains
the handle for a retry after failure. Configuration is immutable. Started UI
sessions and connected sessions remain running by default; only started
headless sessions default to force-cleanup.

The Mechanical gRPC policy is separate from the MCP stdio transport. Start and
connect remain explicit; `auto` only decides the Mechanical gRPC mode after that
product/session choice is known. For a local start, the manager resolves the
exact executable, derives its revision, checks PyMechanical's documented
service-pack capability against that executable's build metadata, and then
makes at most one `launch_mechanical()` call. Confirmed compatible Windows/Linux
starts use WNUA/mTLS respectively. A confirmed incompatible local legacy SP
returns a structured insecure-opt-in error with zero launch calls. The operator
may persist an explicit local `insecure` choice; its unverified legacy listener
binding remains visible and requires an OS-level live check. Unknown or
conflicting evidence stops auto mode before launch. Every local start requires
a validated exact executable, so this path cannot delegate implicitly to PyPIM.

There is no exception-driven start fallback. PyMechanical reserves its port
before the known compatibility exception and other exceptions can occur after
process creation. A failed start is therefore latched for the MCP process; a
second inspection returns the same structured error without another launch.
An operator resolves the cause and restarts MCP. Successful sessions retain the
existing reuse semantics. Connect failures can retry because connect mode does
not create a Mechanical process.

Connect mode cannot inspect the remote server's version/SP before agreeing on a
transport. It never changes from secure to insecure automatically. Explicit
loopback hosts use the secure platform default; other hosts default to mTLS.
WNUA is Windows-only and restricted to PyMechanical's accepted localhost
endpoints. Insecure non-loopback transport requires a separate explicit
acknowledgement. Hostnames are not resolved through DNS to justify an insecure
classification. An omitted connect host is pinned explicitly rather than
inherited from `PYMECHANICAL_IP`.

The manager exposes immutable configuration plus dynamic preflight, selected
versus established transport/host, security, connection scope, listener-binding
evidence, warnings, attempt count, and retry state as JSON-compatible session
context. Inspection adds this context to its result; selection obtains it after
any first connection so it is not stale.

Mechanical tool failures retain the common structured `ToolResult` payload and
set MCP `CallToolResult.isError=true`. The controlled scripts execute their
helpers in a uniquely named self-cleaning function scope, and selection arrays
are bounded before JSON serialization.

Stable MCP v1 HTTP lifespans are scoped per session (or per request in stateless
mode), so this process-wide Mechanical lifecycle is currently supported only
over stdio. Both CLI and programmatic HTTP/SSE entry points reject unsupported
transports. Expanding transport support requires a separate lifecycle decision,
not silent per-request Mechanical creation.

## Extension Path

Future adapters can be added under `products/`:

```text
products/workbench/
products/geometry/
products/mapdl/
products/fluent/
```

These should not be added as empty fake tool modules. Add them only when a real workflow needs them.

A neutral geometry viewer and a build123d-based CAD preprocessor are two
different optional extensions, neither of which is a prerequisite for
Mechanical selection context. Introduce either role only after the native
prototype demonstrates a concrete cross-tool, offline-geometry, or
geometry-generation need.
