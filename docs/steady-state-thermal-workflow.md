# Steady-state thermal application roadmap

## New role of this roadmap

This is an engineering application project built **with** the official
PyMechanical-MCP server. It is not a plan to add tools to a custom MCP server.

Repository deliverables should be reviewed requirements, prompts/scripts,
safe input/output conventions, validation records, and upstream issue reports
where the official package has a reproducible gap.

## Physical boundary

A steady-state analysis solves the temperature field after storage effects
have disappeared. It can return temperatures, heat fluxes, and heat flow rates
for declared boundary conditions. It does not predict warm-up time; transient
analysis would additionally require density, heat capacity, initial conditions,
and time-dependent loads.

The initial ring-only model uses deliberately idealized boundaries:

- a known inner-ring temperature may be prescribed;
- conducted heat rate is then an output;
- an outer prescribed temperature represents an idealized heat sink;
- this does not prove the real bearing-seat or machine-bed temperature;
- no TEG constants may be invented without a concrete datasheet.

## Delivery principles

Every consequential stage follows:

1. inspect current Mechanical/project state;
2. define target, units, assumptions, and non-goals;
3. review the exact official MCP tool calls and any Mechanical script;
4. explicitly authorize the bounded mutation;
5. execute once without automatic mutating retry;
6. read back native state/results;
7. record versions, evidence, discrepancy, and cleanup in the GitHub issue.

Use harmless local models. Keep CAD, `.mechdb`, Workbench hierarchies, solver
databases, and confidential screenshots outside Git under ignored local roots.

## Stages

| Stage | Outcome | Evidence gate |
| --- | --- | --- |
| 0 | Inventory official v0.2.0 tools against Mechanical 2025 R1 | Status/model info and lifecycle behavior recorded without mutation |
| 1 | Review and import one harmless ring CAD file | File identity, units, body count, and project state verified |
| 2 | Create/read back one Steady-State Thermal analysis | Analysis type and identity verified; no loads or solve |
| 3 | Assign explicit isotropic conductivity | Material, value, unit, source, and body read back |
| 4 | Apply fixed temperature to revalidated inner-ring scope | Target, value, unit, and scope read back |
| 5 | Apply explicitly idealized outer-temperature sink | Assumption and scope visible in evidence |
| 6 | Generate controlled mesh and diagnostics | Mesh state and available quality/count evidence recorded |
| 7 | Solve and summarize thermal results | Solver state, extrema/units, location, flux, and energy-balance evidence |
| 8 | Add aluminium bearing seat and contact | Perfect-contact baseline compared with explicit conductance |
| 9 | Add coating and local TEG region | Geometry and thermal resistance use documented data |
| 10 | Optional electrical estimate/coupling | Only named module and datasheet-backed properties used |

Later stages may split further when a smaller review boundary is safer. Never
collapse multiple unvalidated mutations merely because the official MCP exposes
general scripting.

## GitHub contract

Track the initiative as a parent issue and each stage as a child issue using
the general method in
[github-development-workflow.md](github-development-workflow.md).

Each child issue must contain:

- objective, dependency, and non-goals;
- exact input/confidentiality boundary;
- expected official MCP tools;
- reviewed script if a general scripting tool is required;
- units and modeling assumptions;
- read-back and cleanup evidence;
- exact environment/package/Mechanical versions;
- result: passed, failed, or blocked;
- next-stage decision.

## First next action

Open a Stage 0 issue to inventory the official tool surface in the current
Mac/Parallels setup. Do not begin CAD import or model creation until lifecycle,
file paths, working-directory resource behavior, and harmless model-info calls
are understood on Mechanical 2025 R1.
