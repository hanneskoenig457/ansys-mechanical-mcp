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
  'C:\Users\<windows-user>\Documents\Mechanical\<project>\GFB_Project.wbpj' \
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
`-E` itself is a launch-time argument, but `StartServer()` is **not** limited to
launch. The official PyWorkbench user guide says: "You can always start a
Workbench server by running the `StartServer()` command in any Workbench
session." What is unavailable is an *automated* path into a running instance,
for two independent reasons:

1. Chicken-and-egg. PyWorkbench is purely a gRPC client
   (`workbench_client.py` builds a channel via `create_channel()` and speaks
   through `WorkbenchServiceStub`; there is no second transport). Sending
   `StartServer()` through it would require the server it is meant to start.
2. Session isolation. A plain SSH session lands in Windows Session 0, which
   cannot reach the Session 1 desktop at all -- `CopyFromScreen` from Session 0
   fails outright with an invalid-handle error, and `SetForegroundWindow`/UI
   Automation against a Session-1 window from a Session-0 scheduled task do not
   reliably work either.

`RunWB2.exe -R <journal>` is not a way around this either. Tested against a
live session: the journal ran, but reported a PID belonging to neither the
running `RunWB2` nor its `AnsysFWW` -- a fresh instance was started, executed
the journal, and exited, leaving the running session and its gRPC port
untouched. (It did run headless from Session 0, which is worth knowing, but a
fresh instance is exactly what the bootstrap already creates.)

So a project open unsaved in an already-running Workbench GUI does **not** have
to be saved and closed. The user runs `StartServer(PortToUse=51000)` in
Workbench's own Command Window (File -> Scripting -> Open Command Window); the
runtime script then finds the port listening and reuses that session.
`EnvironmentPrefix` is not required -- `workbench_launcher.py` uses it only to
strip a prefix off the port it parses from Workbench's stdout, and
`workbench_client.py` never references it.

## Cold start: licensing must be ready first

Validated by shutting the VM down completely and running the script against it.

SSH answers within seconds of a cold boot, but Ansys is not usable yet. The
Windows services (`ANSYS, Inc. License Manager CVD`, `ANSYS Licensing Tomcat`)
report `Running`/`Automatic` early, while the FlexNet daemons that actually
serve licences -- `lmgrd` and `ansyslmd` -- were observed appearing about
**two minutes after boot**. Starting Workbench before that produces:

1. `ANSYS LICENSE MANAGER ERROR: Connection timed out while reading data`,
2. `Workbench could not connect to a valid licensing server`, a modal dialog
   that blocks GUI initialization, so `-E StartServer(...)` never runs and the
   port never opens, and
3. Mechanical falling back to **read-only** mode if it is opened at all.

`Start-AnsysWorkbenchGrpc.ps1` therefore waits for an interactive console
session, a network adapter that is up, and both FlexNet daemons (confirmed
with `ansysli_util -liclist` when available) before launching anything. That
wait has its own budget, `ANSYS_WORKBENCH_READY_WAIT_SECONDS` (default 300),
so it cannot eat into the time allowed for Workbench itself.

The daemons do **not** come up reliably by themselves on this VM. Observed
twice: over a minute after boot, `lmgrd` and `ansyslmd` were still absent
while the CVD service sat at `Running`. By hand, running
`C:\Program Files\ANSYS Inc\Shared Files\licensing\winx64\ansyslmcenter.exe`
as administrator fixes it. The scripted equivalent, verified to work, is
restarting the service:

```powershell
Restart-Service "ANSYS, Inc. License Manager CVD" -Force
```

`Start-AnsysWorkbenchGrpc.ps1` does this automatically, but only after a 90
second grace period in which the daemons may still appear on their own, and
only once. The delay is deliberate: restarting the service while a running
Ansys application holds a licence throws `Cannot connect to license server
system` dialogs in that application. It needs an elevated session; the SSH
login on this VM already is one.

Readiness is judged by the licence port (`1055` by default, overridable with
`ANSYS_LICENSE_PORT`) accepting connections, plus both daemons being present.
Do not probe `ansysli_util` for this: its option set is not safe to guess at.
An invented `-liclist` returned `Unknown option` with exit code 1 on every
call, so the check reported "not ready" forever and blocked startup even
though licensing was fully working.

### Do not give the launcher task a trigger

The scheduled task that launches Workbench must have **no trigger at all**.
An `-AtLogOn` trigger was tried and is actively harmful: Windows then starts
Workbench roughly 10 seconds after boot, far ahead of licensing, so it comes
up behind the licensing dialog, bypasses every readiness check in this script,
and leaves stray `RunWB2`/`AnsysWBU` processes behind that later runs then
trip over. The task exists purely as an elevation/session vehicle that
`Start-ScheduledTask` invokes once conditions are verified.

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
  same system does not return the existing server's port; it replaces the
  process, and the previous Mechanical process for that system exits.
  `ensure-ansys-workbench-mechanical-runtime` guards against this: if
  `127.0.0.1:50053` already answers a real scripting call, it keeps that
  session and exits without touching it. Pass
  `ANSYS_WORKBENCH_FORCE_RESTART=1` to deliberately replace it.
- **`disconnect_from_mechanical` terminates the Mechanical process**, it does
  not merely close the client connection. Confirmed here: calling it dropped
  the `AnsysWBU` process and its port off the VM entirely, and recovering
  required a full `ANSYS_WORKBENCH_FORCE_RESTART=1` re-run. This is the
  `Mechanical.exit()`-on-shutdown behavior noted in the README, and it costs
  more in the Workbench case, where the only way back is another
  non-idempotent `start_mechanical_server()`. Just stop using the connection
  instead; a stale one is cheap, a destroyed session is not.
- **`stop_mechanical_server()` is a no-op below Workbench framework version
  25.2** (`GetFrameworkVersion()` reports `25.1` here) -- its implementation
  only calls the underlying `StopMechanicalServerOnSystem` journal command on
  25.2+. There is currently no clean way to stop a per-system Mechanical
  server through PyWorkbench on this install; closing Workbench (or the
  Mechanical process directly) is the only way to release it.
- **Run the Windows bootstrap with `-File`, never `powershell -Command -` over
  stdin.** With stdin, PowerShell evaluates the input as independent statement
  groups: a `throw` aborts only its own group, execution continues, and the
  exit status does not reflect the failure. That produced a run whose log
  contained two `throw` messages and still reported success. The script is
  copied over and invoked with `-File`, and its path is passed unquoted (outer
  quotes survive the remote shell and break `-File`) and without a trailing
  `; exit $LASTEXITCODE` (the remote side is `cmd.exe`, which glues the `;`
  onto the preceding argument).
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
