# Workbench-managed Mechanical access

## Decision

`ensure-ansys-mechanical-runtime` starts Mechanical **standalone**: a bare
`.mechdb` with no Workbench Project Schematic around it. Many real projects on
this VM are Workbench projects instead (`.wbpj` + a `<project>_files/dp0/...`
folder tree). Their per-system Mechanical database is not a portable
standalone `.mechdb` and should not be opened outside Workbench's own
management of that folder structure.

`ensure-ansys-workbench-mechanical-runtime` covers that case: it launches the
Workbench GUI itself (visible, interactive, on the Windows console), opens a
named `.wbpj`, and starts a PyMechanical gRPC server for one system inside it,
using the official `ansys-workbench-core` (PyWorkbench) package. The resulting
Mechanical connection is remapped onto the same local port (`127.0.0.1:50053`)
that `ansys-mechanical-mcp` is already configured for, so **no MCP
reconfiguration is needed** to switch between a standalone and a
Workbench-managed target.

## Runtime topology

```text
ensure-ansys-workbench-mechanical-runtime (Mac)
        |
        | SSH exec: Start-AnsysWorkbenchGrpc.ps1
        v
Windows: RunWB2.exe -I -E "StartServer(EnvironmentPrefix=...,PortToUse=51000)"
        |   (interactive scheduled task -> Session 1, GUI visible)
        v
Workbench project-schematic gRPC server, Windows 127.0.0.1:51000
        |
        | SSH forward (shared ControlMaster socket)
        v
Mac 127.0.0.1:51000  --[ansys.workbench.core.connect_workbench, security="insecure"]-->
        |
        | wb.run_script_string('Open(FilePath=r"...")')
        | wb.start_mechanical_server(system_name="SYS")
        v
Windows: a fresh Mechanical gRPC server for that one system, random port (e.g. 55451)
        |
        | SSH forward, remapped local port (same ControlMaster socket)
        v
Mac 127.0.0.1:50053  <-- same endpoint ansys-mechanical-mcp already uses
```

One SSH TCP connection (the `ansys-mechanical-mcp-<uid>/ssh-control` master
socket) carries all of it: the Workbench port, the Mechanical port, and
(when used) the standalone-Mechanical port from
`ensure-ansys-mechanical-runtime`. Forwards are added to and removed from that
single master with `ssh -S <socket> -O forward|cancel`, never a second SSH
process.

## Usage

```bash
scripts/ensure-ansys-workbench-mechanical-runtime \
  'C:\Users\hanne\Documents\Mechanical\02_GFB\01_Workbench\GFB_Project.wbpj' \
  'SYS'
```

The system name is the **internal** Workbench name from `GetAllSystems()`,
not the schematic display letter (e.g. Mechanical's own outline may show
`B: Steady-State Thermal`, while `GetAllSystems()` for the same system
returns `SYS`). If it's unknown, run the script once with any placeholder
name to get the Workbench server up, then query it directly:

```python
from ansys.workbench.core import connect_workbench
wb = connect_workbench(port=51000, host="127.0.0.1", security="insecure")
wb.run_script_string(
    'import json\n'
    'wb_script_result = json.dumps([s.Name for s in GetAllSystems()])'
)
```

After the script prints `Mechanical (Workbench system '...') ready at
127.0.0.1:50053`, use the official MCP tools exactly as with a standalone
Mechanical target -- `connect_to_mechanical(ip="127.0.0.1", port=50053,
transport_mode="insecure")`.

## How the `-E` launch was found

`ansys.workbench.core.launch_workbench()` (PyWorkbench) builds this exact
command line internally
(`.venv/lib/python3.14/site-packages/ansys/workbench/core/workbench_launcher.py`):

```text
RunWB2.exe -I -E "StartServer(EnvironmentPrefix='<uuid>', PortToUse=<port>, Security='<mode>') if <addin version check> else StartServer(EnvironmentPrefix='<uuid>', PortToUse=<port>)"
```

`-E "<command>"` executes an IronPython command at Workbench startup -- this
is the officially used, source-verified way to start the project-schematic
gRPC server without typing `StartServer()` into the Command Window by hand.
It is a **launch-time argument only**: there is no supported way to inject a
command into an already-running interactive Workbench process (confirmed
independently: a plain SSH session lands in Windows Session 0, which cannot
reach the Session 1 desktop at all -- `CopyFromScreen` from Session 0 fails
outright with an invalid-handle error, and `SetForegroundWindow`/UI Automation
against a Session-1 window from a Session-0 scheduled task do not reliably
work either). If a relevant project is open unsaved in an already-running
Workbench GUI, save and close it first; there is no way to attach to it
without that step.

## Known caveats

- **`Security='...'` is unsupported on this install.** This Ansys 251
  Workbench addin's `StartServer()` signature predates the `Security`
  keyword argument; passing it throws `CommandArgumentException: Unknown
  argument: Security` in a blocking GUI dialog (someone has to click OK).
  `Start-AnsysWorkbenchGrpc.ps1` omits it. The resulting server still accepts
  an insecure client connection (`connect_workbench(..., security="insecure")`,
  `connect_to_mechanical(..., transport_mode="insecure")`), matching the rest
  of this deployment.
- **`start_mechanical_server()` is not idempotent.** Calling it again for the
  same system does not return the existing server's port; it appears to
  replace the process, and the previous Mechanical process for that system
  was observed to exit. Re-running `ensure-ansys-workbench-mechanical-runtime`
  against a system that already has a live Mechanical server should be
  avoided if an existing MCP connection to it must survive -- reconnect the
  MCP client after any re-run.
- **`stop_mechanical_server()` is a no-op below Workbench framework version
  25.2** (`GetFrameworkVersion()` reports `25.1` here) -- its implementation
  only calls the underlying `StopMechanicalServerOnSystem` journal command on
  25.2+. There is currently no clean way to stop a per-system Mechanical
  server through PyWorkbench on this install; closing Workbench (or the
  Mechanical process directly) is the only way to release it.
- The local-port remap (`50053 -> <dynamic mechanical port>`) is tracked in
  `${TMPDIR}/ansys-mechanical-mcp-<uid>/last-mech-port-50053` so a re-run can
  cancel the previous, now-stale forward before adding the new one. Deleting
  that file (or the whole control-socket directory) forces a clean forward on
  the next run.

## Extension rule

Same as [architecture.md](architecture.md): add content here only for
reproducible setup, safety-bounded operation, or validation evidence specific
to the Workbench-managed path. Anything that applies equally to standalone
Mechanical belongs in `architecture.md`, not duplicated here.
