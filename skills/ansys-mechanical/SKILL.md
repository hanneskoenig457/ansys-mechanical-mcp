---
name: ansys-mechanical
description: Operate Ansys Mechanical through the globally configured official PyMechanical-MCP server and the Mac-to-Parallels runtime. Use for Ansys Mechanical, PyMechanical, PyWorkbench, Mechanical gRPC, .mechdb projects, Workbench .wbpj projects and their Project Schematic systems, CAD/NX geometry import into Mechanical, model inspection, meshing, analyses, solving, results, screenshots, or troubleshooting this Mechanical connection. Do not use for Fluent, AEDT, Lumerical, or unrelated Ansys products.
---

# Ansys Mechanical

Use the official `ansys-mechanical` MCP as the primary interface. It runs on
the Mac and connects through a loopback-only SSH tunnel to Mechanical 2025 R1
in the Parallels Windows VM.

## Pick the right runtime first

Two different runtimes serve the same MCP endpoint `127.0.0.1:50053`. Decide
which one the task needs **before** starting anything:

| The user's target | Runtime to use |
| --- | --- |
| A standalone `.mechdb`, or no project named yet | `ensure-ansys-mechanical-runtime` (see below) |
| A Workbench `.wbpj` project, or a system inside a Project Schematic | `ensure-ansys-workbench-mechanical-runtime` (see "Workbench-managed projects") |

A `.wbpj` project's per-system Mechanical database is **not** a portable
standalone `.mechdb`. Never try to open it directly with `open_project`; use
the Workbench runtime so Workbench itself manages that folder structure.

## Establish the connection

1. Do not create another virtual environment or install another MCP copy in the
   current task's project. The global MCP is already registered.
2. First call `connect_to_mechanical` with `127.0.0.1`, port `50053`, and
   transport mode `insecure`. If it succeeds, verify with
   `check_mechanical_status` that the reported `project_directory` is the one
   the user actually means — the endpoint may still serve a *different*,
   earlier target. If it is the wrong project, do not reuse it; start the
   correct runtime instead.
3. Only if the connection is unavailable and the user actually requested a
   Mechanical operation, run this explicit prerequisite command:

   ```text
   /Users/hanne/Documents/Developer/ANSYS_Doku/ansys-mechanical-mcp/scripts/ensure-ansys-mechanical-runtime
   ```

   This command starts or reuses the VM, verifies SSH, starts or reuses the
   dedicated Mechanical gRPC session, and establishes the SSH tunnel. It may
   open the visible Parallels console so the user can sign in to Windows.
4. Call `connect_to_mechanical` again and verify the reported Mechanical
   version and connection state before doing model work.
5. If startup fails, report the failing layer precisely: MCP, VM, SSH,
   Mechanical/gRPC, tunnel, connection, license, API operation, or CAD import.
   Do not silently switch to GUI automation.
6. The VM/tunnel/Mechanical session does not stay up indefinitely across a
   long chat. Before any action later in the same conversation (not just at
   the start), call `check_mechanical_status` first rather than assuming a
   connection from earlier in the chat is still alive; if it is not, redo
   steps 2-4 instead of letting a mid-task tool call fail first.

## Workbench-managed projects (`.wbpj`)

For a Mechanical system that lives inside a Workbench project, run:

```text
/Users/hanne/Documents/Developer/ANSYS_Doku/ansys-mechanical-mcp/scripts/ensure-ansys-workbench-mechanical-runtime '<windows-wbpj-path>' '<system-name>'
```

Example:

```text
.../scripts/ensure-ansys-workbench-mechanical-runtime 'C:\Users\hanne\Documents\Mechanical\02_GFB\01_Workbench\GFB_Project.wbpj' 'SYS'
```

It starts the Workbench GUI with its own gRPC server, opens the project,
starts a Mechanical server for that one system, and remaps it onto the usual
`127.0.0.1:50053`. Then call `connect_to_mechanical` exactly as normal — no
MCP reconfiguration.

Rules specific to this path:

- The system name is the **internal** name from `GetAllSystems()`, not the
  schematic display letter. Mechanical's own outline may show
  `B: Steady-State Thermal` while the correct argument is `SYS`. If unknown,
  see `docs/workbench-integration.md` for the one-line query.
- **Do not re-run the script against a system that already has a live
  Mechanical server** unless the user accepts losing it.
  `start_mechanical_server()` is not idempotent: it replaces the process, and
  the previous Mechanical session for that system exits. Prefer
  `check_mechanical_status` and reuse.
- There is no clean programmatic stop on this install (`stop_mechanical_server()`
  is a no-op below Workbench framework 25.2; this one reports 25.1). Releasing
  a system's Mechanical server means closing Workbench or Mechanical itself —
  warn the user before doing that.
- Workbench cannot be attached to after the fact. If the user has an unsaved
  project open in an already-running Workbench GUI, they must save and close it
  first; `StartServer()` only takes effect at launch. Do not attempt GUI
  automation, scheduled-task desktop tricks, or UI Automation to work around
  this — it was tried and does not work (Windows Session 0 isolation).

Full architecture, the source-verified `-E` launch mechanism, and all known
caveats are in
`/Users/hanne/Documents/Developer/ANSYS_Doku/ansys-mechanical-mcp/docs/workbench-integration.md`.

## Windows-only file paths

Mechanical always runs on the remote Windows VM. Any `.mechdb`, CAD, or
working-directory path you pass to a Mechanical tool is a **Windows path on
that remote machine** (e.g. `C:\Users\...`), never a path on the Mac running
the MCP server. Only `upload_file` takes a genuine local Mac path (it copies
that file into Mechanical's remote working directory).

The official `open_project` and `save_project` tools historically ran a
local `pathlib.Path(file_path).exists()`/`.parent.exists()` check before
contacting Mechanical, which always failed for a `C:\...` path since that
path never exists on the Mac. Since every path these two tools ever receive
is on the remote Windows machine, that check was always wrong here, not just
sometimes — so it has been removed outright (not made conditional) in this
machine's local `ansys-mechanical-mcp/.venv`. Mechanical itself now reports
a real error if the path is actually invalid. The patch lives in
`site-packages` and will be lost on a `pip install --upgrade` of
`ansys-mechanical-mcp`. If `open_project` or `save_project` reports a false
"not found"/"directory does not exist" error for a path you already verified
exists (e.g. via `os.path.exists(...)` inside `run_python_script`), do not
retry the tool — reapply the patch, or bypass it directly via
`run_python_script`:

```python
ExtAPI.DataModel.Project.Open(r"C:\path\to\file.mechdb")
# or
ExtAPI.DataModel.Project.SaveAs(r"C:\path\to\file.mechdb")
```

## Choose the narrowest interface

Use this order:

1. A dedicated official MCP tool.
2. `get_guidelines_for` for the relevant topic followed by MCP
   `run_python_script` using the Mechanical scripting API.
3. Direct PyMechanical only for diagnostics or a demonstrated MCP gap. Use the
   existing repository `.venv`, explicit `insecure` loopback transport, and
   `cleanup_on_exit=False`; do not install packages elsewhere.
4. GUI/computer control only when the user explicitly requests it or approves
   it after the API paths are shown to be unavailable.

The official MCP itself uses PyMechanical underneath. `run_python_script` is
therefore an MCP-supported way to reach Mechanical features that do not yet
have a dedicated high-level MCP tool.

For CAD import, request the `geometry` guideline. `open_project` is for
`.mechdb`, not `.prt`, STEP, or other CAD files.

## Preserve state and evidence

- Begin with status, metadata, and other read-only checks.
- Do not save, solve, clear, upload, open, close, disconnect, run arbitrary
  code, or mutate the model unless the user placed that action in scope.
- Keep `insecure` Mechanical gRPC limited to `127.0.0.1:50053` and the SSH
  tunnel. Never expose port `50053` to the LAN.
- Do not change licensing, server, SSH, firewall, or MCP configuration during
  an engineering task without explicit user authorization.
- After any interrupted MCP call, server restart, lost connection, modal
  dialog, or timeout, reconnect and re-check Mechanical and the model before
  claiming that an operation is still running or succeeded.
- Treat tool completion, returned model state, and screenshots as evidence.
  Never infer successful CAD translation, solving, saving, or results merely
  from the absence of an immediate error.
- Do not call `disconnect_from_mechanical`, restart the MCP, or terminate its
  process when Mechanical may contain unsaved work without warning the user.
  Keep the installed MCP's existing exit behavior unchanged.

For setup diagnosis or reconstruction, consult
`/Users/hanne/Documents/Developer/ANSYS_Doku/ansys-mechanical-mcp/README.md`
and the private setup guide referenced there.
