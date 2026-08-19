# Live validation workflow

## Purpose

Validate the official PyMechanical-MCP path without confusing package
installation, TCP reachability, a PyMechanical connection, and an actual MCP
tool round trip.

Each gate proves something different:

| Gate | Evidence | Does not prove |
| --- | --- | --- |
| Installation | package versions, entry point, `pip check` | Mechanical is running |
| Tunnel | `nc` reaches Mac loopback port | gRPC protocol compatibility |
| PyMechanical | `is_alive`, product revision | Codex loaded the MCP server |
| MCP startup | server visible in `/mcp` | a particular tool is safe/correct |
| Tool round trip | structured result from official tool | untested mutations or solves |

## Preconditions

1. Use a harmless project with no unsaved productive work.
2. Keep Parallels in Shared Network mode.
3. Start Mechanical 2025 R1 with gRPC port `50053`.
4. Confirm the Windows listener and firewall posture.
5. Start the SSH tunnel with an explicit Mac loopback bind.
6. Confirm the pinned local package versions and Codex registration.

## Ordered checks

### 1. Installation

```bash
.venv/bin/python -VV
.venv/bin/python -m pip show ansys-mechanical-mcp ansys-mechanical-core ansys-common-mcp
.venv/bin/python -m pip check
.venv/bin/ansys-mechanical-mcp --help
codex mcp get ansys-mechanical
```

### 2. Tunnel

```bash
nc -vz 127.0.0.1 50053
```

Failure here is networking/process state. Do not debug it by changing MCP
packages or model content.

### 3. PyMechanical prerequisite

Use explicit `transport_mode="insecure"`, `cleanup_on_exit=False`, and a
read-only property such as `is_alive` or `version`. Do not call `exit()` from
the diagnostic.

### 4. MCP visibility

Restart Codex/ChatGPT Desktop after MCP configuration changes. In a new task,
inspect `/mcp` and confirm `ansys-mechanical` is active.

### 5. Read-only official tool call

Call connection status first, then model information. State all prohibited
actions in the request:

```text
Use ansys-mechanical to check status and read the current model information.
Do not solve, save, clear, upload, open, disconnect, close, run arbitrary code,
or mutate anything.
```

Record the actual tool name, result, package versions, Mechanical revision,
date, and whether the Mechanical GUI stayed open.

## Consequential validation

For a write, solve, file operation, or arbitrary script:

1. define the engineering objective and explicit non-goals;
2. inspect the current project/model and units;
3. preview exact code, target, file paths, and overwrite behavior;
4. require explicit user authorization for the bounded action;
5. execute once;
6. inspect native state/results;
7. record cleanup and any discrepancy.

Do not retry a possibly mutating failure automatically.

## Shutdown

Official v0.2.0 may close Mechanical when the MCP process exits. Before a
Codex/Desktop restart:

1. save or deliberately discard harmless Mechanical work;
2. expect the GUI to close;
3. restart Mechanical if needed;
4. restart the SSH tunnel if its process changed;
5. re-run the ordered gates rather than assuming the old connection survived.

## Evidence contract

Keep these categories separate:

- installed package and Python facts;
- Windows Mechanical/product facts;
- network/tunnel facts;
- official MCP startup facts;
- exact tool-call results;
- unvalidated assumptions;
- mutations performed, if any;
- process/listener/GUI cleanup.

Never cite the retired prototype's unit or integration tests as validation of
the official package.
