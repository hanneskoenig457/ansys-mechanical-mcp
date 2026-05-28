# AGENTS.md

## Project Goal

Build an unofficial MCP server for practical Ansys Mechanical/FEM automation
using PyMechanical and PyDPF.

The goal is not to expose the full Ansys API blindly. The goal is to provide
small, structured, reliable MCP tools that let AI assistants inspect, run, and
postprocess real Ansys Mechanical workflows.

## v0.1 Scope

Focus only on:

- Ansys Mechanical
- PyMechanical
- PyDPF
- Static Structural workflows
- Existing or prepared Mechanical/Workbench projects
- Structured MCP tool responses

Out of scope for v0.1:

- Fluent
- AEDT
- Lumerical
- MAPDL-first workflows
- Full Workbench project creation
- CAD or geometry generation from scratch
- Fake solver responses
- Huge unimplemented tool lists
- Arbitrary remote code execution as a primary interface

## Engineering Rules

- Prefer official Ansys, PyMechanical, PyDPF, and MCP APIs.
- Check official documentation before implementing API-dependent behavior.
- Do not claim support for workflows that are not implemented.
- Do not simulate solver behavior or invent result data.
- Keep the implementation small, real, and testable.
- Prefer structured MCP tools over arbitrary code execution.
- Allow Mechanical script execution only as a controlled fallback.
- Return JSON-compatible results with clear status, errors, and logs.
- Include useful failure modes instead of hiding API or license errors.
- Keep unit tests independent from a licensed Ansys installation.
- Make integration tests that require Ansys opt-in and skipped by default.

## Development Environment

Use a local repository virtual environment at `.venv`.

If `.venv` does not exist, create it before installing development dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Do not install Python packages globally.

Prefer these commands:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/python -m ansys_mechanical_mcp.server --check-environment
```

## Architecture Direction

Use the modular layout:

```text
src/ansys_mechanical_mcp/
  server.py
  core/
    environment.py
    errors.py
    tool_result.py
  products/
    mechanical/
    dpf/
  workflows/
    static_structural.py
tests/
docs/
examples/
```

Keep product-specific low-level code under `products/`.
Keep higher-level workflow orchestration under `workflows/`.
Do not put everything into `server.py`.
Do not add empty product adapters for future scope unless a real workflow needs
them.

## Initial Target Workflow

The first real workflow should support:

1. Check the local environment.
2. Start or connect to Ansys Mechanical.
3. Inspect the current project/model.
4. Execute a controlled Mechanical script when needed.
5. Solve an existing Static Structural analysis.
6. Extract selected result metadata and summaries with PyDPF.
7. Return structured status, errors, and result summaries.

## Documentation Requirements

Before implementing API-dependent behavior, verify and reference official docs
for:

- PyMechanical
- Mechanical Scripting API
- PyDPF
- MCP Python SDK
- ansys-common-mcp, if adopted

Update `docs/api-research.md` when making API decisions.

## Publishing Notes

This is an unofficial project. Do not imply endorsement by Ansys.

Use wording like:

> An unofficial MCP server for practical Ansys Mechanical automation using
> PyMechanical and PyDPF.

Avoid wording like:

- The Ansys MCP server
- Official Ansys Mechanical MCP
- Ansys-supported MCP server
