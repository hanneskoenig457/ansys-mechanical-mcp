# Two-Machine Development And Live Validation

## Purpose

This project uses two distinct environments so that ordinary tests remain
independent from Ansys while implemented behavior can still be checked against
a real licensed Mechanical installation.

| Environment | Authority | Allowed evidence |
| --- | --- | --- |
| macOS development machine without Ansys | Source changes, fake/unit tests, documentation, commits, and pushes | Python tests, fake adapters, CLI behavior, and in-process MCP round trips |
| Windows Mechanical validation machine | Licensed interactive read-only integration | Real GUI startup, product version, gRPC round trip, model inspection, selection payloads, and session reuse |

The development machine has no licensed Ansys Mechanical installation. A green
test suite there does not prove that Mechanical starts, that a license is
available, or that native selection proxies have the expected runtime shape.
The Mechanical machine is an integration station, not the normal source-code
workspace.

Every machine-specific chat must identify its environment before acting:

- macOS/Darwin without Mechanical means the **development role**;
- Windows with the prepared licensed Mechanical installation means the
  **validation role**.

If the observed operating system does not match the prompt's declared role,
stop before installing, editing, pulling, or launching anything and ask for the
correct handoff prompt. Operating system alone does not prove that a license or
test project is available; the validation chat must still verify those
preconditions.

## Normal Change Cycle

### 1. Develop without Ansys

On the development machine:

1. Verify that the host is macOS/Darwin and that this is the development role.
2. Read `AGENTS.md` and the relevant architecture and API research.
3. Inspect Git status and preserve unrelated work.
4. Fetch the configured remote and fast-forward the intended branch before
   editing; stop on divergence or local conflicts instead of overwriting work.
5. Verify API-dependent decisions against current official documentation.
6. Implement the smallest relevant change.
7. Add fake-based regression coverage, including negative paths.
8. Run the repository test, lint, environment, and diff checks.
9. State explicitly which behavior remains unvalidated against Mechanical.
10. Commit only the scoped change and push the current branch without force.
11. Produce a handoff prompt containing the exact branch and commit.

The development result is complete as an implementation result, but not as a
licensed integration result.

### 2. Transfer an exact revision

On the Mechanical validation machine:

1. Verify that the host is Windows and that this is the validation role.
2. Read `AGENTS.md`, this document, and the handoff prompt.
3. Check Git status before fetching or changing branches.
4. Preserve unrelated local changes; do not reset or overwrite them.
5. Fetch the remote and use a fast-forward-only update where applicable.
6. Verify that `HEAD` is the exact commit named in the handoff.
7. Use only the repository `.venv`; never install project dependencies globally.
8. Install or refresh the checked-out project and required extras in that
   environment.
9. Change only the registered MCP server configuration required by the tested
   revision.
10. Restart Codex or the relevant MCP client when the server process or its
   configuration must be reloaded.

Do not claim that a newly pulled implementation is live-valid until the MCP
client has restarted and a real tool round trip has completed.

### 3. Validate read-only behavior

Use only an empty project created for testing or an explicitly prepared,
harmless test project. Never repurpose a productive Mechanical project.

The usual sequence is:

1. Confirm that the expected MCP tools are registered.
2. Call `check_environment`.
3. Call `inspect_mechanical_model` and observe whether the intended Mechanical
   GUI starts or the configured server connection succeeds.
4. Record actual product version, service pack when available, start/connect
   mode, GUI/batch mode, ownership, cleanup policy, and transport facts.
5. Call `inspect_mechanical_model` again and verify that no second unnecessary
   Mechanical instance starts.
6. If the GUI contains an empty project, stop and ask the operator to open the
   prepared test project.
7. Capture only the already implemented read-only selection cases. Ask the
   operator before each manual selection change.
8. Run opt-in integration tests only when their preconditions match the
   prepared session.

No live-validation handoff authorizes model mutation, mesh generation, solve,
new physics, named selections, highlighting, or target resolution.

### 4. Return evidence

Report fake-tested and real Mechanical results in separate sections. For a live
failure, retain at least:

- exact Mechanical version and service pack/build when observable;
- PyMechanical version;
- start or connect configuration, excluding secrets;
- requested and effective transport information when available;
- complete error code and message;
- whether a GUI or process was created;
- whether a retry created another process;
- safe structured tool payloads and warnings;
- exact reproduction order.

Do not edit project source on the Mechanical machine in the normal workflow.
Send the evidence back to the development machine, add a fake reproducer there,
implement the smallest correction, and repeat the cycle with a new commit.

## Exceptional Integration Fixes

Some defects depend on native Mechanical behavior and may be impractical to
diagnose remotely. In that case the operator may explicitly authorize a narrow
diagnostic branch on the Mechanical machine. Keep it isolated, add the same
fake regression test, run normal checks, commit and push it, and synchronize it
back to the development machine. This exception must not turn the licensed
installation into an untracked primary workspace.

## Handoff Contract

Every development-to-validation handoff should identify:

- repository and branch;
- exact commit hash;
- purpose and changed behavior;
- fake/unit checks already completed;
- behavior that still needs real validation;
- required dependency or MCP configuration changes;
- whether a Codex restart is required;
- safe test-project preconditions;
- expected tool sequence and data to record;
- explicit prohibition of unrequested mutation;
- instructions for returning evidence rather than silently patching locally.

Use `docs/development-chat-prompt.md` to begin work on the Mac and
`docs/next-chat-prompt.md` for the subsequent Windows validation handoff.
Replace their placeholders with the actual revision and change-specific steps.
