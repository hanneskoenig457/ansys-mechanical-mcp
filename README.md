# Ansys Mechanical MCP

An unofficial MCP server for practical Ansys Mechanical and FEM automation using
PyMechanical and PyDPF.

This project focuses on controlled, structured automation for existing or
prepared Ansys Mechanical workflows. The first target is Static Structural
analysis inspection, solve orchestration, and result summarization through the
Model Context Protocol.

This is not an official Ansys product and is not affiliated with, endorsed by,
or supported by Ansys.

## Status

Early experimental public alpha, not a production-ready business product. The
public MCP surface currently contains three structured
tools:

- `check_environment`, which runs without Ansys installed;
- `inspect_mechanical_model`, which uses one persistent, lazily established
  Mechanical session;
- `capture_current_selection`, which captures read-only graphics selection and
  active-tree context from an explicitly GUI-capable session.

The session lifecycle, model inspection, and selection path are unit-tested
with injected fakes, including an in-process MCP client/server round trip. A
licensed Windows check at commit `90ec822` confirmed one explicitly accepted
insecure Mechanical 2025 R1 SP03 GUI session, session reuse with one launch
attempt, and real snapshots for empty, single-face, multi-face, active-tree,
mesh-node, mesh-element, and element-face selections. Both connect-only opt-in
integration tests passed. The listener was again observed on `::`, so this
remains an experimental harmless read-only path with per-session risk
acceptance, deliberate GUI shutdown, and zero-process/zero-listener cleanup.
Internal, fake-tested helpers for a controlled script fallback, an existing
Static Structural solve, and PyDPF result metadata remain unexposed. The
project does not simulate solver behavior.

Mechanical access is opt-in: omitting `--mechanical-mode` leaves the server
unconfigured, and either Mechanical tool returns a structured configuration
error instead of choosing start or connect on the user's behalf. Once start or
connect is explicit, the gRPC transport defaults to the safety-bounded `auto`
policy described below.

## Project Direction

The implemented prototype architecture is native-first: a user selects an
entity in interactive Mechanical and `capture_current_selection` returns a
deterministic structured snapshot. The snapshot keeps Mechanical IDs scoped to
their model and revision, reports unavailable revision data as `null`, and does
not perform semantic interpretation or mutation.

An optional later semantic layer may separate observed facts from engineering
interpretations, while Mechanical must resolve and validate the target again
before any action is applied.

This can eventually support a workflow such as select, explain, preview, apply,
solve, and summarize. Only read-only capture is currently implemented; the
larger workflow remains a design target.

A neutral viewer or build123d/OpenCascade adapter remains an optional research
path if the Mechanical prototype later demonstrates a real cross-CAE or
independent-geometry need. Steady-state thermal analysis is now the explicitly
selected next staged workflow. It remains unimplemented: the ring-only
baseline, bearing seat, contact, coating, and TEG path are ordered roadmap
items with separate development and licensed-validation gates.

See
[Selection Context and Semantic CAE Interaction](docs/selection-context-architecture.md)
for the architecture decision and [the roadmap](docs/roadmap.md) for the staged
implementation path.

See the [steady-state thermal workflow](docs/steady-state-thermal-workflow.md)
for the engineering boundary and
[GitHub development workflow](docs/github-development-workflow.md) for the
two-machine issue and evidence contract.

## v0.1 Scope

The initial prototype is intentionally narrow:

- Check the local Python, MCP, PyMechanical, PyDPF, PyMechanical CLI, and Ansys
  environment state. CLI discovery is not a Mechanical-product or license
  check.
- Start or connect to Ansys Mechanical through PyMechanical.
- Execute controlled Mechanical scripts as a fallback.
- Inspect the current Mechanical model and analyses at a basic level.
- Solve an existing Static Structural analysis.
- Extract basic result metadata and summaries with PyDPF.

Out of scope for v0.1:

- Fluent, AEDT, Lumerical, or other Ansys products.
- Full Workbench project creation.
- CAD or geometry generation from scratch.
- Fake solver responses.
- Broad unimplemented tool lists.

## Install For Development

Use a local virtual environment in the repository:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Optional Ansys workflow dependencies:

```bash
.venv/bin/python -m pip install -e ".[ansys]"
```

## Run

Print a local JSON environment diagnostic:

```bash
ansys-mechanical-mcp --check-environment
```

Run the MCP server over stdio:

```bash
ansys-mechanical-mcp
```

The current persistent Mechanical lifecycle is deliberately limited to stdio
with the stable MCP Python SDK v1; unsupported HTTP entry points are rejected.
Running without Mechanical options still exposes environment diagnostics, but
`--mechanical-mode start` or `--mechanical-mode connect` is required before a
Mechanical tool can establish a session. For example, connect to an existing
GUI-capable Mechanical gRPC server without owning its shutdown:

```bash
ansys-mechanical-mcp \
  --mechanical-mode connect \
  --mechanical-host 127.0.0.1 \
  --mechanical-port 10000 \
  --mechanical-ui \
  --no-mechanical-cleanup-on-exit
```

For a new UI process, use `--mechanical-mode start --mechanical-ui`. Started UI
sessions are deliberately left running by default because force-closing them
could discard unsaved edits. Pass `--mechanical-cleanup-on-exit` only when that
is explicitly acceptable. Started headless sessions are cleaned up by default;
connected sessions are left running by default.

Mechanical gRPC transport defaults to `--mechanical-transport-mode auto`:

- A local start resolves the exact Mechanical executable, checks its revision
  and official PyMechanical service-pack compatibility before launching, and
  makes at most one launch call. It uses WNUA on compatible Windows installs,
  and mTLS on compatible Linux installs.
- A confirmed legacy service pack does not auto-downgrade. Auto mode returns
  `MECHANICAL_INSECURE_TRANSPORT_OPT_IN_REQUIRED` without launching. Persist
  `--mechanical-transport-mode insecure` only after accepting the local risk;
  the result then carries an insecure-transport warning and an unverified
  listener-binding warning.
- If executable or build evidence is unknown, auto mode does not downgrade or
  launch. It returns a structured preflight error.
- A connect operation never falls back from secure to insecure. Loopback uses
  the secure platform default; non-loopback defaults to mTLS. The client mode
  must match the already-running server.
- An insecure non-loopback connection requires both
  `--mechanical-transport-mode insecure` and
  `--mechanical-allow-insecure-remote`. Its session context carries an explicit
  warning.

## Mechanical gRPC Support And Legacy Listener Risk

The `host` selected by the Python client is not proof of the address on which
Mechanical actually listens. This distinction matters for insecure releases:

| Mechanical release | Current project position |
| --- | --- |
| 2025 R1 revision 251 SP04+ | SP04 is PyMechanical's documented threshold for secure gRPC. This is the preferred path, but its WNUA behavior still needs a separate live check in this project. |
| 2025 R1 SP03, build `R251RC2P03` | Explicit `insecure` started one GUI and the first real inspect succeeded on the Windows validation machine. Windows then reported port 10000 bound to `::`, so the validation stopped. Treat this path as experimental and never use it for productive or confidential models. |
| Older or other releases below their documented secure threshold | A comparable broad-listener risk is possible, but has not been live-proven for every release. Keep `auto` fail-closed and require explicit `insecure` opt-in. |

PyMechanical 0.12.12 offers no documented, version-compatible SP03 start option
that reliably binds this listener to `127.0.0.1` or `::1`. Its newer
`--grpc-host` mechanism is not passed to Mechanical 2025 R1 below SP04. Direct
PyMechanical CLI launch follows the same rule, while connect mode only chooses
the client destination of a server whose binding already exists.

The normal validation rule is therefore to inspect the exact listener address
and owning process after every insecure start and stop when it is not
loopback-only. A narrowly bounded experimental read-only session may continue
only after the operator is shown that exact evidence and explicitly accepts the
risk for that one session. Use only an empty or harmless test project on a
trusted or isolated development computer; do not mutate the model, change the
firewall or Registry, or silently carry consent into another start. Close
Mechanical deliberately afterward and verify that both process and listener
are gone.

Terms used here:

- **Loopback:** reachable only inside the same computer, normally `127.0.0.1`
  or `::1`.
- **Listener:** the network endpoint on which Mechanical waits for connections.
- **Unauthenticated:** the client identity is not reliably verified.
- **Unencrypted:** network traffic is not encrypted.
- **`::`:** all IPv6 network interfaces, not only IPv6 loopback `::1`; actual
  external reachability also depends on firewall and network configuration.
- **Opt-in:** deliberate, explicit activation by the operator.
- **Fail-closed:** stop by default when the security state is unknown.

Use `--mechanical-exec-file` when path discovery does not select the desired
local installation; a mismatch between the requested revision and resolved
executable blocks launch. Local start always requires a validated exact
executable and never falls through to implicit PyPIM. mTLS certificates can be
supplied with `--mechanical-certs-dir`. A failed local start is not retried
inside the same MCP process, because a late PyMechanical failure can leave a
process behind; restart the MCP server after resolving the cause.

A selection capture never starts a new process implicitly: first establish a
configured GUI session with `inspect_mechanical_model`, select entities in
Mechanical, and then call `capture_current_selection`. Native arrays are bounded
to 1,000 returned items; the snapshot retains the observed source count where
available and emits a truncation warning.

## Development

Run checks:

```bash
.venv/bin/ruff check .
.venv/bin/python -m pytest
```

The basic unit tests are independent from licensed Ansys installations.

Project development and licensed validation normally happen on separate
machines. Code changes, fake tests, commits, and pushes are made on the macOS
development machine without Ansys. The licensed Windows Mechanical machine
pulls an exact commit and performs the opt-in read-only round trip. Results from
these two environments are always reported separately. See the
[live-validation workflow](docs/live-validation-workflow.md), the reusable
[development prompt](docs/development-chat-prompt.md), and the reusable
[validation handoff prompt](docs/next-chat-prompt.md).

Real read-only integration tests are opt-in. With an explicitly prepared
Mechanical gRPC session, set connection variables and run:

```bash
ANSYS_MECHANICAL_MCP_RUN_INTEGRATION=1 \
ANSYS_MECHANICAL_MCP_MODE=connect \
ANSYS_MECHANICAL_MCP_HOST=127.0.0.1 \
ANSYS_MECHANICAL_MCP_PORT=10000 \
ANSYS_MECHANICAL_MCP_TRANSPORT=auto \
.venv/bin/python -m pytest tests/integration
```

Also set `ANSYS_MECHANICAL_MCP_RUN_SELECTION_INTEGRATION=1` only for a
GUI-capable session prepared for current-selection capture. Connected sessions
are left running by default.

## Project Layout

```text
src/ansys_mechanical_mcp/
  server.py
  core/
  products/
    mechanical/
    dpf/
  workflows/
tests/
docs/
examples/
```

## References

- [PyAnsys documentation](https://docs.pyansys.com/)
- [PyMechanical documentation](https://mechanical.docs.pyansys.com/)
- [Mechanical Scripting API documentation](https://scripting.mechanical.docs.pyansys.com/)
- [PyDPF documentation](https://dpf.docs.pyansys.com/)
- [Ansys Common MCP](https://github.com/ansys/pyansys-common-mcp)
- [Model Context Protocol Python SDK](https://modelcontextprotocol.github.io/python-sdk/server/)

## License

MIT. See [LICENSE](LICENSE).
