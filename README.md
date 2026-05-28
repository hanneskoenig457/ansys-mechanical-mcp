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

Early public alpha. The repository currently implements the first v0.1 slice:
a structured `check_environment` MCP tool that runs without Ansys installed.

Mechanical session control, Static Structural solve tools, and PyDPF result
summary tools are intentionally not exposed yet. They will be added only when
they call real official APIs. The project does not simulate solver behavior.

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

## Development

Run checks:

```bash
.venv/bin/ruff check .
.venv/bin/python -m pytest
```

The basic unit tests are independent from licensed Ansys installations.

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
