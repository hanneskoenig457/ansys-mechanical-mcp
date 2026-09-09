# Official PyMechanical-MCP inventory

## Selected implementation

The workspace uses Ansys's official
[`ansys-mechanical-mcp`](https://github.com/ansys/pymechanical-mcp) package.

Verified local baseline on 2026-08-13:

- `ansys-mechanical-mcp==0.2.0`;
- `ansys-mechanical-core==0.13.2`;
- `ansys-common-mcp==0.3.3`;
- CPython 3.14.2 on macOS arm64;
- installation inside the repository `.venv`;
- console entry point `ansys.mechanical.mcp.__main__:launcher`.

The package requires Python `>=3.12,<4` and is distributed as a pure-Python
`py3-none-any` wheel. Platform/Python wheelhouses on the release page are
offline dependency collections, not different server variants.

## Official tool surface in v0.2.0

The upstream package documents 21 tools:

| Group | Tools |
| --- | --- |
| Connection and lifecycle | `check_mechanical_status`, `check_mechanical_installed`, `launch_mechanical`, `connect_to_mechanical`, `disconnect_from_mechanical`, `list_mechanical_instances` |
| File and project management | `list_files`, `upload_file`, `download_file`, `clear_mechanical`, `save_project`, `open_project` |
| Mechanical scripting and solve | `run_python_script`, `solve_analysis`, `get_model_info`, `export_results` |
| Visualization and diagnostics | `screenshot`, `create_custom_plot`, `get_mechanical_logs` |
| Persistent Python execution | `run_python_code` |
| Workflow guidance | `get_guidelines_for` |

It also exposes the resource
`files://mechanical/working_directory`.

Upstream can hide tools requiring Mechanical dynamically until a connection
exists. This workspace deliberately starts disconnected so loading the global
MCP does not start Parallels or Mechanical, but its wrapper uses
`--static-tools` so Codex receives the complete official surface at its first
handshake. A requested Mechanical workflow still first tries
`connect_to_mechanical`; the separate runtime starter is used only when the
endpoint is unavailable.

## Installed CLI configuration

```text
scripts/start-ansys-mechanical-mcp
  → ansys-mechanical-mcp --static-tools
  --ip 127.0.0.1
  --port 50053
  --transport-mode insecure
```

The MCP transport remains the default stdio transport. `--transport-mode`
selects Mechanical gRPC security; it does not change MCP stdio.

### Initial tool exposure for Codex — validated 2026-09-09

The official v0.2.0 server defaults to dynamic tool exposure: at initialization
it disables every tool tagged `requires_mechanical`, then
`connect_to_mechanical` enables those components server-side. Codex snapshots
the MCP tool list during its initial handshake and does not add those later
components to the active tool registry. The result was a reproducible
six-tool surface (connection/status/guidance only), even though the Mechanical
connection was alive; `run_python_script`, `solve_analysis`, and model/result
tools were absent from Codex.

The repository launcher now always supplies the upstream `--static-tools`
option. An isolated stdio MCP handshake, with no Mechanical connection or
launch, returned all 21 documented v0.2.0 tools, including
`run_python_script` and `solve_analysis`. Run the version-pinned regression
check after installation or upgrade:

```bash
.venv/bin/python scripts/check-mechanical-mcp-tool-surface.py
```

This changes availability in Codex only after a new MCP handshake. It merely
exposes powerful tools; the project safety rules still require explicit scope
before script execution, saving, or solving. Never restart the MCP to obtain
the new list while an unsaved Mechanical session is open, because the v0.2.0
server cleanup calls `Mechanical.exit()`.

## Consequence levels

Tool names alone do not guarantee read-only behavior. Use this operating
classification:

| Level | Typical operations | Default handling |
| --- | --- | --- |
| Observe | status, installation check, model info, logs, resource reads | May run when requested; report exact target |
| Generate local output | screenshot, plot, export results, download | Confirm destination and overwrite policy |
| Change session/files | upload, open, save, clear, launch, disconnect | Require explicit scope and lifecycle awareness |
| Change/solve model | arbitrary Mechanical script, persistent Python, solve | Require explicit engineering intent, target, units, validation, and expected effects |

`run_python_script` and `run_python_code` are powerful fallback interfaces, not
automatically safe tools. Inspect code and target state before execution.

## Known local compatibility facts

- The live Mechanical server identifies itself as revision `251` (2025 R1).
- The installation has no service pack.
- Official PyMechanical security guidance requires SP04+ for secure gRPC on
  2025 R1; the current instance therefore requires explicit `insecure`.
- A direct PyMechanical check through the SSH tunnel returned `is_alive=True`.
- Codex successfully loaded the official MCP server from the registered path.

## Lifecycle finding from installed v0.2.0

The installed source connects with `cleanup_on_exit=False`, but
`PyMechanicalMCP.product_cleanup()` calls `context.mechanical.exit()` when the
MCP process shuts down. Treat a Desktop restart, MCP reload, or task host
shutdown as capable of ending the Mechanical gRPC service; do not infer the
interactive GUI outcome from that fact alone.

### Live Workbench-managed verification — 2026-09-09

This lifecycle behavior was retested against the live Workbench-managed
Mechanical session rather than inferred solely from the installed source. The
active official MCP process held the only client connection to the temporary
loopback forward at `127.0.0.1:50056`. It was stopped with `SIGINT`; no model
script, save, mesh, or solve was requested. Afterwards, a new direct
PyMechanical connection to `50056` failed, while Workbench (`AnsysWBU`) and
its gRPC listener at `51000` remained reachable.

The interactive Windows user then observed that the Mechanical GUI remained
open. The Mac application inventory independently still reported
`Mechanical 2025 R1` as running. Windows Session 0 process inspection did not
reliably expose the interactive window, so it cannot override that observation.
The validated conclusion is therefore narrower: ending this MCP process stops
its Mechanical gRPC service but does **not** prove that the Workbench-managed
Mechanical GUI has closed. An API client must treat the now-gRPC-less GUI as
unreachable; do not restart or replace it without explicit authorization.

This behavior should be rechecked after every package upgrade. If preserving an
interactive GUI across MCP restarts becomes important, open an upstream issue
or validate an official detach mechanism rather than patching site-packages.

## Upgrade procedure

Do not upgrade during an active Mechanical session. First record current
versions and release notes, stop work safely, update the pinned requirements,
rebuild or upgrade `.venv`, inspect `--help`, run `pip check`, and repeat the
read-only tunnel/MCP validation.

Never claim a new release is compatible merely because installation succeeds.

## Sources

- [Official repository](https://github.com/ansys/pymechanical-mcp)
- [v0.2.0 release](https://github.com/ansys/pymechanical-mcp/releases/tag/v0.2.0)
- [Official documentation](https://mechanical-mcp.docs.pyansys.com/)
- [PyMechanical gRPC security](https://mechanical.docs.pyansys.com/version/stable/user_guide/remote_session/grpc_security.html)
