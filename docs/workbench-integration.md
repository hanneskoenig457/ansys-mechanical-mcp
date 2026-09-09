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
Mechanical connection is remapped onto the same local port (`127.0.0.1:50056`)
that `ansys-mechanical-mcp` is already configured for, so **no MCP
reconfiguration is needed** to switch between a standalone and a
Workbench-managed target.

The current local endpoint is `50056`. A previous local default was found to be
owned by an unrelated Codex remote proxy: it accepted TCP but did not serve
Mechanical gRPC. This workflow now uses only the verified endpoint. Earlier
validation wording has been normalized to the current endpoint convention.

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
Mac 127.0.0.1:50056  <-- same endpoint ansys-mechanical-mcp already uses
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
  'C:\Users\<windows-user>\Documents\Mechanical\<project>\GFB_Project.wbpj'
```

The runtime now discovers the system itself. It selects the one system whose
component **display text** contains both `Model` and `Solution`, which excludes
geometry-only systems. Workbench appends numeric suffixes to internal component
names in shared systems (for example, `Model 1`), so those internal names are
not a reliable capability test. If there is exactly one match, no system
argument or preliminary query is needed. For a project with multiple Mechanical
systems, pass the desired **internal** Workbench system name as argument 2:

```bash
scripts/ensure-ansys-workbench-mechanical-runtime \
  'C:\Users\<windows-user>\Documents\Mechanical\<project>\GFB_Project.wbpj' \
  'SYS'
```

Discovery still uses Workbench's official `GetAllSystems()` scripting API
internally, but the former manual discovery run has been removed. The script
also validates explicit names and reports all eligible candidates when the
choice is ambiguous.

After the script prints `Mechanical (Workbench system '...') ready at
127.0.0.1:50056 (transport mode: insecure; gRPC verified)`, use the official
MCP tools exactly as with a standalone Mechanical target --
`connect_to_mechanical(ip="127.0.0.1", port=50056,
transport_mode="insecure")`. The `gRPC verified` suffix matters: a TCP listener
alone can appear before the Workbench-owned Mechanical server accepts a real
PyMechanical request. The runtime therefore waits for an insecure,
`cleanup_on_exit=False` connection and a harmless `run_python_script("1")`
round-trip before reporting ready. Its timeout is
`ANSYS_MECHANICAL_GRPC_WAIT_SECONDS` (default `120`).

## External CAD belongs to the Geometry cell

For a Workbench project, attach external CAD to the target system's Geometry
cell or create it in its Workbench-linked geometry editor, then update the
project before starting Mechanical.  Do not use Mechanical's direct CAD import
API to bypass the Project Schematic for a `.wbpj` workflow.  The current
runtime starts a Mechanical server only for a system that already contains
both `Model` and `Solution`; it does not yet create Geometry cells, control
SpaceClaim, or automate CAD import.

The proposed evidence-gated PyAnsys Geometry path reuses this visible
Workbench/gRPC topology but has not yet been validated.  Its boundaries and
work sequence are in [PyAnsys Geometry with Workbench-owned CAD](pyansys-geometry-workflow.md).

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
runtime script then finds the port listening and reuses that session without
requiring the temporary `.wbpj` path to exist on disk. Path validation applies
only when the bootstrap must launch a new Workbench process.
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
session and network, restarts the licensing stack immediately when no Ansys
application can hold a licence, requires `lmgrd`, `ansyslmd`, FlexNet port
`1055`, licensing HTTP port `1084`, and 20 seconds of continuous stability.
It then performs a real one-second `ANS_WB` checkout with the installed
official `ansysli_util.exe`. That wait has its own budget,
`ANSYS_WORKBENCH_READY_WAIT_SECONDS` (default 300), so it cannot eat into the
time allowed for Workbench itself.

The daemons do **not** come up reliably by themselves on this VM. Observed
twice: over a minute after boot, `lmgrd` and `ansyslmd` were still absent
while the CVD service sat at `Running`. By hand, running
`C:\Program Files\ANSYS Inc\Shared Files\licensing\winx64\ansyslmcenter.exe`
as administrator fixes it. The scripted equivalent, verified to work, is
restarting the service:

```powershell
Restart-Service "ANSYS, Inc. License Manager CVD" -Force
```

`Start-AnsysWorkbenchGrpc.ps1` does this automatically as soon as the console
session and network are ready on a clean cold start. It restarts both
`ANSYS, Inc. License Manager CVD` and `ANSYSLicensingTomcat`. Concurrent app
and AI launchers share named licensing and Workbench-launch mutexes, so they
cannot restart the services twice or launch competing Workbench processes. If
an Ansys GUI is already running, the immediate restart is suppressed to avoid
interrupting a licence holder.

The supported probe is `ansysli_util.exe -checkout ANS_WB -wait 1`; success
must contain `ANS_WB OUT`. The utility releases the temporary checkout on
exit. Do not use the nonexistent `-liclist` option.

The 2025 R1 client was observed checking out `ANS_WB` successfully and then
crashing with `C0000005` while fetching cache information through its default
`fnp,web-elastic` path. Workbench then showed modal Client Proxy/licensing
errors even though Mechanical later obtained a writable FlexNet licence. The
interactive launcher now scopes `ANSYS_LICENSING_SERVICE_PRIORITY=fnp` to the
Workbench process. In the validated run, the cache completed in one second,
with no client crash or modal licence dialogs.

### One triggerless launcher, one explicit coordinator

The scheduled task that launches Workbench must have **no trigger at all**.
An `-AtLogOn` trigger was tried and is actively harmful: Windows then starts
Workbench roughly 10 seconds after boot, far ahead of licensing, so it comes
up behind the licensing dialog, bypasses every readiness check in this script,
and leaves stray `RunWB2`/`AnsysWBU` processes behind that later runs then
trip over. The task exists purely as an elevation/session vehicle that
`Start-ScheduledTask` invokes once conditions are verified.

There is deliberately no second Ansys task at Windows logon. The explicit
coordinator is `Ansys MCP Ready.app` (or the equivalent AI runtime command).
It starts the stopped VM, waits for Windows automatic sign-in and SSH, runs the
complete session/network/licensing readiness logic, starts exactly one blank
Workbench, and establishes the loopback tunnel at `127.0.0.1:51000`. It does
not open a project and does not start Mechanical. A named mutex covers the
complete check-and-launch section, so concurrent app/AI invocations converge
on the same Workbench server.

The task needs an interactive Windows console session. Automatic Windows
logon is intentionally separate because it changes the VM's authentication
posture. Accounts with real passwords should use Microsoft's Sysinternals
Autologon interactively so the password never crosses SSH or enters repository
logs.

The VM itself is another layer. In the reference setup Parallels host-start
autostart is off; the app or an AI runtime command starts the VM only on demand.

### Validation evidence, 2026-08-22

- Warm task run completed with Task Scheduler result `0`.
- Workbench and its Mechanical child ran in visible console Session 1.
- Port `51000` opened only after the readiness checks completed.
- Workbench opened
  `C:\Users\hanne\Documents\Mechanical\03_TEG\TEG_Sim.wbpj`.
- Automatic discovery excluded `Geometry` and selected the unique
  Thermal-Electric system `SYS`.
- `start_mechanical_server()` opened Mechanical on Windows port `54229`; the
  Mac runtime remapped it to `127.0.0.1:50056` in 60 seconds total.
- A second runtime invocation reused the live Mechanical session in 3 seconds.
- Sysinternals Autologon produced an active interactive Session 1 after a
  fully stopped VM was started on demand; Parallels VM autostart stayed off.
- The clean post-race cold test completed from VM state `stopped` in 2:05.
  Read-only inspection found exactly one `RunWB2`, one `AnsysFWW`, zero
  `AnsysWBU`, temporary project `wbnew.wbpj`, zero Workbench systems, no
  listener on `50056`, and the managed tunnel on `51000`. Two simultaneous
  follow-up readiness calls both reused it in 1–2 seconds.
- The app's success path is non-modal. A Notification Center timeout (`-1712`)
  was initially misreported as a readiness failure after the log had already
  proved success; the cosmetic completion notification was removed and the
  rebuilt app now exits silently after success.
- The final cold run logged `ANSYS_LICENSING_SERVICE_PRIORITY=fnp`, immediate
  `ANS_WB` checkout, one-second cache retrieval, no `ansyscl` crash, and a
  Mechanical `ansys` checkout.
- A Mac PyMechanical check returned `is_alive=True`, version `251`, and the
  scripting roundtrip `alive` through `127.0.0.1:50056`.

## Known caveats

- **`Security='...'` is unsupported on this install.** This Ansys 251
  Workbench addin's `StartServer()` signature predates the `Security`
  keyword argument; passing it throws `CommandArgumentException: Unknown
  argument: Security` in a blocking GUI dialog (someone has to click OK).
  `Start-AnsysWorkbenchGrpc.ps1` omits it. The resulting server still accepts
  an insecure client connection (`connect_workbench(..., security="insecure")`,
  `connect_to_mechanical(..., transport_mode="insecure")`), matching the rest
  of this deployment.
- **`start_mechanical_server()` is not idempotent.** It requests a fresh
  Workbench-managed Mechanical gRPC server for the system, so treat it as
  capable of interrupting existing clients. The returned port may change: the
  controlled recovery on 2026-09-09 changed from `58263` to `58445`. It is not
  valid to infer a full visible-GUI restart merely from that call, a port change,
  or a brief window resize. `ensure-ansys-workbench-mechanical-runtime` guards
  against the call: only if `127.0.0.1:50056` passes a real scripting call does
  it keep that session and exit without touching it. Pass
  `ANSYS_WORKBENCH_FORCE_RESTART=1` only to deliberately request a replacement.
- **`disconnect_from_mechanical` has a server-stop effect.** The official MCP
  implementation delegates to `Mechanical.exit()`. In the controlled
  Workbench-SYS test on 2026-09-09, calling that exact underlying method after
  a successful harmless round-trip removed the remote gRPC listener, the
  listener-owning `AnsysWBU` PID `7200` exited, and a fresh PyMechanical
  connection failed. A subsequent Workbench `start_mechanical_server()` call
  recovered the system on a new port and the existing `Geom\\ProofBlock` body
  remained present. This proves the gRPC/process boundary; it does not by itself
  prove what a particular interactive window did. Just stop using a connection
  when it need not be torn down.
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
- The local-port remap (`50056 -> <dynamic mechanical port>`) is tracked in
  `${TMPDIR}/ansys-mechanical-mcp-<uid>/last-mech-port-50056` so a re-run can
  cancel the previous, now-stale forward before adding the new one. Deleting
  that file (or the whole control-socket directory) forces a clean forward on
  the next run.

## Extension rule

Same as [architecture.md](architecture.md): add content here only for
reproducible setup, safety-bounded operation, or validation evidence specific
to the Workbench-managed path. Anything that applies equally to standalone
Mechanical belongs in `architecture.md`, not duplicated here.
