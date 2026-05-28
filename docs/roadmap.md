# Roadmap

## v0.1 Mechanical MVP

Goal: control and postprocess an existing Static Structural Mechanical analysis.

Planned capabilities:

- Check local Python/PyAnsys environment.
- Start or connect to Mechanical through PyMechanical.
- Run controlled Mechanical scripts.
- Inspect model/project state at a basic level.
- Solve an existing Static Structural analysis.
- Extract selected result summaries with PyDPF.

## v0.2 Better Mechanical Tools

Goal: reduce reliance on generic script execution.

Potential capabilities:

- List analyses.
- List named selections.
- List loads and boundary conditions.
- Generate/update mesh.
- Add or modify common Static Structural loads.
- Add or modify common supports.
- Export result images.

## v0.3 Workbench Adapter

Goal: orchestrate prepared Workbench projects and systems.

Potential capabilities:

- Open Workbench projects.
- Locate Mechanical systems.
- Launch Mechanical for a selected system.
- Manage project files and working directories.

## v0.4 Geometry Adapter

Goal: import or create simple geometry inputs.

Potential capabilities:

- Import geometry from supported files.
- Create very simple parameterized demo geometries if official APIs support it cleanly.

## Later

- PyMAPDL/APDL fallback for solver-near workflows.
- Fluent or other product adapters only after the Mechanical path is useful.

