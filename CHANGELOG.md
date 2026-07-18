# Changelog

## Unreleased

- Add a stable-MCP-v1 lifespan context around the existing
  `MechanicalSessionManager`, including explicit start/connect configuration,
  serialized session use off the async event loop, immutable ownership policy,
  retryable/idempotent cleanup, and an enforced stdio-only boundary.
- Expose structured, read-only `inspect_mechanical_model` and
  `capture_current_selection` MCP tools alongside `check_environment`.
- Add the JSON-compatible `SelectionSnapshot` contract and a capability-checked
  Mechanical adapter for current graphics selection, native IDs, supported
  entity types, element-face pairs, active tree objects, warnings, and errors.
- Mark failed captures as unknown rather than empty, preserve source positions
  for element-face pairs, bound large native arrays, isolate Mechanical script
  helper names, and report MCP application failures with `isError=true`.
- Require an explicit start/connect choice. Leave started GUI sessions running
  by default; automatic force-cleanup remains the default only for started
  headless sessions.
- Add fake-based unit and in-process MCP round-trip coverage plus opt-in,
  default-skipped real Mechanical integration tests. No licensed Mechanical
  runtime has been validated yet.
- Retain internal fake-injectable helpers for controlled scripting, an existing
  Static Structural solve, and PyDPF result metadata; these remain unexposed and
  not live-validated.
- Keep semantic explanation, physical actions, and build123d/OpenCascade
  integration separate from the implemented native read-only capture slice.

## 0.1.0a1 - 2026-05-28

Initial public alpha.

- Add a minimal MCP server entrypoint.
- Add the `check_environment` MCP tool and CLI diagnostic.
- Add project structure for Mechanical, DPF, and Static Structural workflow code.
- Document the v0.1 scope, architecture, roadmap, and verified API decisions.
- Keep Mechanical solve and DPF result tools intentionally unimplemented until
  they can call real Ansys APIs.
