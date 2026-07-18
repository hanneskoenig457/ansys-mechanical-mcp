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

Early public alpha. The public MCP surface currently contains three structured
tools:

- `check_environment`, which runs without Ansys installed;
- `inspect_mechanical_model`, which uses one persistent, lazily established
  Mechanical session;
- `capture_current_selection`, which captures read-only graphics selection and
  active-tree context from an explicitly GUI-capable session.

The session lifecycle, model inspection, and selection path are unit-tested
with injected fakes, including an in-process MCP client/server round trip. They
have not yet been validated end-to-end against a licensed Mechanical
installation. Internal, fake-tested helpers for a controlled script fallback,
an existing Static Structural solve, and PyDPF result metadata remain
unexposed. The project does not simulate solver behavior.

Mechanical access is opt-in: omitting `--mechanical-mode` leaves the server
unconfigured, and either Mechanical tool returns a structured configuration
error instead of choosing start or connect on the user's behalf.

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
independent-geometry need. Which physical phenomena and engineering actions are
implemented first is deliberately not decided yet.

See
[Selection Context and Semantic CAE Interaction](docs/selection-context-architecture.md)
for the architecture decision and [the roadmap](docs/roadmap.md) for the staged
implementation path.

## v0.1 Scope

The initial prototype is intentionally narrow:

- Check the local Python, MCP, PyMechanical, PyDPF, executable, and Ansys
  environment state.
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

Real read-only integration tests are opt-in. With an explicitly prepared
Mechanical gRPC session, set connection variables and run:

```bash
ANSYS_MECHANICAL_MCP_RUN_INTEGRATION=1 \
ANSYS_MECHANICAL_MCP_MODE=connect \
ANSYS_MECHANICAL_MCP_HOST=127.0.0.1 \
ANSYS_MECHANICAL_MCP_PORT=10000 \
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
