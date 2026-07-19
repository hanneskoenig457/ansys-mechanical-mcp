# Steady-State Thermal Workflow

## Status And Scope

Steady-state thermal analysis is the next explicitly selected engineering
workflow for this repository. It is a tracked roadmap, not an implemented or
validated capability. The public MCP surface still contains only the tools
listed in `README.md`.

The first engineering model is deliberately a ring-only baseline. It proves
the safe CAD-to-result pipeline before adding the aluminium bearing seat,
machine bed, coating, or thermoelectric generator (TEG). It must not be used as
a final design statement.

## Physical Model

A steady-state analysis solves the temperature field after storage effects have
disappeared. It returns actual temperatures, heat fluxes, and heat flow rates
for the declared boundary conditions. It does not answer how long the system
takes to reach that state or what the temperature is after a particular time.
Those questions require a transient analysis with density, heat capacity,
initial temperature, and time-dependent loads.

For the proposed baseline:

- a known inner-ring temperature is a valid prescribed-temperature boundary;
- the conducted heat rate is then an output, not a required input;
- an outer prescribed temperature can represent an idealized, effectively
  infinite heat sink for the first ring-only calculation;
- this outer boundary is a strong modelling assumption, not proof of the real
  bearing-seat or machine-bed temperature;
- thermal capacity is irrelevant in steady state and becomes necessary only
  for transient work.

A TEG does not create useful electrical power from heat flow alone. A concrete
module produces a voltage from a temperature difference through the Seebeck
effect, while its own thermal resistance changes that temperature difference.
Electrical power also depends on the module's internal resistance and external
load. No generic TEG constants may be invented.

## Staged Delivery Contract

Each stage is developed on the macOS development machine, fake/unit tested,
reviewed, committed, and pushed. The exact commit is then validated on the
licensed Windows Mechanical machine before the next stage begins. A stage is
not `Done` until both evidence gates pass.

| Stage | Deliverable | Windows gate |
| --- | --- | --- |
| 1 | Local CAD intake, deterministic import preview, explicit confirmation, and controlled import into a new or proven-empty test project | One harmless local CAD file imports once; actual bodies, units, project state, process count, and listener are recorded |
| 2 | Create and read back one unambiguous Steady-State Thermal analysis | Analysis type and identity are verified; no loads, mesh, or solve |
| 3 | Explicit constant isotropic conductivity contract and material assignment | Material name, conductivity, unit, source, and assigned body are read back |
| 4 | Preview, confirm, and apply a fixed temperature to a re-resolved inner-ring face | Scope, value, and unit are read back from Mechanical |
| 5 | Apply an explicitly idealized fixed-temperature sink to a re-resolved outer face | Scope and assumption are visible in the structured result |
| 6 | Controlled mesh creation and diagnostics | Mesh status, node/element counts, and available quality evidence are recorded |
| 7 | Solve the selected analysis and summarize thermal results | Solver state, temperature extrema and units, hotspot location, available heat-flux results, and a defensible energy-balance check are returned |
| 8 | Add the aluminium bearing seat and thermal contact | Perfect-contact baseline is compared with an explicit contact-conductance parameter |
| 9 | Add a separately selectable coating region and local TEG patch | Coating/TEG thermal resistance uses documented geometry and concrete material/module data |
| 10 | Optional thermal-electric estimate or coupling | Only a named TEG and datasheet-backed Seebeck, resistance, conductance, temperature dependence, and load are used |

Later stages may be split further when API research or live evidence shows that
a smaller review boundary is safer. They must not be collapsed into a single
unvalidated implementation jump.

## Local CAD And Result Boundary

Real or potentially confidential CAD and solver artifacts stay outside Git.
The conventional repository-local paths are:

```text
local-validation/
  inputs/
  outputs/
```

Both content directories are gitignored. Do not commit CAD, `.mechdb`, Workbench
hierarchies, result databases, screenshots containing confidential geometry, or
exported solver data.

Stage 1 must introduce an explicitly configured allowed input root and a
separate output root. Public tools accept only relative paths inside those
roots. Canonical resolution must reject absolute paths, `..`, symlink/alias
escapes, unsupported types, and overwrite attempts. The read-only intake result
contains only safe metadata such as normalized relative path, file type, size,
and SHA-256; it never embeds file contents.

## Preview, Confirm, Apply, Inspect

Every consequential mutation follows the same protocol:

1. **Inspect** the current project, analysis, model revision, and proposed
   target without mutation.
2. **Preview** a canonical plan containing inputs, units, target evidence,
   prerequisites, assumptions, warnings, and a deterministic plan ID.
3. **Confirm** by supplying that exact plan ID. A conversational “yes” alone is
   not an executable authorization token.
4. **Apply** at most once after rechecking file hashes, target identity,
   project state, and output non-existence. Never retry a possibly mutating
   Mechanical failure automatically.
5. **Inspect** the native result and return structured evidence of what
   Mechanical actually contains.

Preview calls never mutate. Apply fails closed on changed inputs, stale or
ambiguous selections, non-empty/unknown project state, existing outputs, or
missing prerequisites.

## Per-Stage Evidence

The GitHub issue is the handoff record. It must contain:

- exact branch and commit;
- macOS fake/unit/MCP checks and their commands;
- assumptions that still require Mechanical;
- precise Windows setup and allowed mutation scope;
- actual Mechanical/PyMechanical version and safe configuration;
- exact tool order and structured results;
- GUI/process/listener evidence before and after the test;
- discrepancies, reproduction order, and the next responsible machine.

Fake tests never count as a Mechanical round trip. Windows evidence never
justifies an ad hoc source change in the normal validation checkout. See
`docs/github-development-workflow.md` and
`docs/live-validation-workflow.md` for the operational handoff.
