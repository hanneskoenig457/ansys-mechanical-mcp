# Architecture

The server should be organized as a small set of product adapters plus workflow tools.

## Layers

```text
MCP client
  |
  v
MCP server entrypoint
  |
  +-- core: configuration, logging, errors, result schemas
  |
  +-- products/mechanical: PyMechanical sessions and Mechanical scripting tools
  |
  +-- products/dpf: PyDPF result extraction
  |
  +-- workflows/static_structural: higher-level workflow operations
```

## Design Intent

Use product-specific adapters for low-level operations and workflow modules for higher-level actions. This keeps later Workbench, Geometry, MAPDL, or Fluent support possible without turning the server into one large file.

## Extension Path

Future adapters can be added under `products/`:

```text
products/workbench/
products/geometry/
products/mapdl/
products/fluent/
```

These should not be added as empty fake tool modules. Add them only when a real workflow needs them.

