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

## Two-Machine Development And Validation

The normal project workflow deliberately separates implementation from licensed
Mechanical validation:

- The **development machine** is a Mac without a licensed Ansys Mechanical
  installation. It is the normal source-code workspace. Implement changes
  there, run unit, fake, CLI, and in-process MCP tests, update documentation,
  then commit and push the tested change.
- The **Mechanical validation machine** is Windows with the licensed interactive
  Mechanical installation. Pull the exact reviewed commit there, update only
  the repository virtual environment and MCP registration as needed, restart
  the MCP client, and perform the opt-in read-only live checks against a
  harmless test project.

At the start of a machine-specific task, verify the operating system and stated
role. Do not run Windows/Mechanical validation instructions on the Mac, and do
not silently turn the Windows validation checkout into the primary development
workspace.

Never present fake or in-process MCP coverage from the development machine as a
real Mechanical round trip. Conversely, do not make ad hoc source changes on
the validation machine during the normal workflow. When live behavior disproves
an assumption, capture the exact version, configuration, error, and safe
structured payload, then return that evidence to the development machine for
the next regression-tested change. An explicitly requested emergency or
diagnostic branch on the validation machine is an exception, not the default.

See `docs/live-validation-workflow.md` for the handoff procedure and
`docs/development-chat-prompt.md` and `docs/next-chat-prompt.md` for the reusable
development and validation prompts.

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

## Native Selection Direction

The current prototype implements Mechanical-native, read-only selection capture
through a persistent stdio MCP application context. This path is fake-tested but
still requires opt-in validation against a licensed interactive Mechanical
installation.

- Keep deterministic selection capture separate from optional semantic or LLM
  explanation.
- Keep selection explanation separate from any mutating engineering action.
- Treat native entity IDs as model- and revision-scoped, not as portable IDs.
- Resolve and validate targets again in the native CAE application immediately
  before mutation.
- Treat a build123d/OpenCascade viewer and a build123d-based CAD preprocessor as
  two distinct optional future roles, neither of which is an MVP dependency.
- Do not choose or imply the first supported physical phenomenon until that
  scope is decided explicitly.

See `docs/selection-context-architecture.md` for the full decision and safety
boundary.

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
