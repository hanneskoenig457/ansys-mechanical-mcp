# Productive Mechanical-MCP test runbook

This runbook moves from a cold-start transport check to a controlled NX
geometry import. It targets the verified local setup: Mechanical 2025 R1,
official PyMechanical-MCP 0.2.0, gRPC port `50053`, and explicit insecure gRPC
inside the SSH tunnel.

## What the installed MCP can actually do

The installed server exposes 21 tools. Relevant to this test:

- `check_mechanical_status` verifies the connected product and project;
- `get_guidelines_for` returns the official package's built-in Mechanical
  scripting guidance, including the `geometry` topic;
- `run_python_script` executes Mechanical/ExtAPI scripting;
- `get_model_info` inspects the resulting model;
- `screenshot` captures the Mechanical graphics view;
- `open_project` opens only `.mechdb`, not CAD files;
- `upload_file` transfers a Mac-local file into Mechanical's working directory.

The built-in `geometry` guidance explicitly lists NX `.prt` and uses
`Model.GeometryImportGroup.AddGeometryImport()` followed by `Import(...)`.
Therefore NX import is a supported scripted workflow, although the actual CAD
translation can still fail for file-version, installation, or licensing
reasons. Such a failure is a real integration result, not an unknown MCP
capability.

## Automation timing and login behavior

The MCP itself now starts without opening Parallels. Only the explicit
`scripts/ensure-ansys-mechanical-runtime` command uses these defaults,
overrideable through the named environment variables:

1. starts the Parallels VM if it is stopped and opens its visible console;
2. waits **180 seconds** for passwordless SSH
   (`ANSYS_MECHANICAL_SSH_WAIT_SECONDS`);
3. asks Windows to create/update the Mechanical task and start it;
4. the Windows script waits **180 seconds** for gRPC port `50053`
   (`ANSYS_MECHANICAL_START_WAIT_SECONDS`);
5. the runtime starter waits **30 seconds** for the Mac tunnel endpoint
   (`ANSYS_MECHANICAL_TUNNEL_WAIT_SECONDS`).

The Windows task has an **At logon** trigger for the configured user. If the
user is not logged in before the runtime command times out, the task starts
Mechanical when the user later logs in. The MCP remains loaded but disconnected;
rerun the request so the skill can connect after Mechanical appears.

No Windows automatic login was configured. During the first cold-start test,
the operator entered the Windows password manually. The At-logon trigger then
started Mechanical in that interactive desktop.

SSH is independent of the GUI login. Windows OpenSSH starts as a system service
and normally becomes reachable before desktop login. The Mechanical task needs
the interactive login because it launches a visible GUI.

## Test 1: clean cold start

1. Close ChatGPT/Codex Desktop completely.
2. Shut down the Windows VM, not merely suspend it.
3. Open ChatGPT/Codex Desktop and create a new **local Mac** chat.
4. Send:

```text
Use the official ansys-mechanical MCP. Check only the Mechanical connection
status and report the version, project directory, and whether the connection is
alive. Do not open/import files, run arbitrary scripts, save, solve, clear,
disconnect, or close Mechanical.
```

Expected result: the global skill first tries the MCP connection. If unavailable,
it explicitly starts Parallels, waits for SSH, starts Mechanical and the tunnel,
then connects the already-loaded MCP. Status reports revision `251` and an alive
connection.

This setup-level cold-start path has been verified through a direct read-only
PyMechanical round trip. The final acceptance test from a fully restarted
ChatGPT/Codex app and an unrelated new local chat remains intentionally open.

If Windows stops at the login screen, log in. Mechanical then starts through
the At-logon task. Repeat the same status request after Mechanical appears.

## Test 2: prove the NX file and import API without mutation

Send:

```text
Use ansys-mechanical. First call the geometry guideline. Then perform
only read-only prerequisite checks for the Windows-visible NX file
\\Mac\SPP2305_Hannes\00_TEG_Energy_Harvesting\98_Ansys\00_CAD_NX\easy_2_body_contact.prt:
confirm that the path exists and report its size, confirm the connected
Mechanical version, and state the exact Mechanical scripting API you would use
to import it. Do not import, upload, open, save, mesh, solve, clear, disconnect,
or modify the model yet.
```

Pass criteria:

- Windows/Mechanical can see the UNC path;
- the server returns the geometry-import guidance;
- the proposed operation uses `GeometryImportGroup.AddGeometryImport()` and
  automatic format detection;
- no geometry appears yet.

## Test 3: controlled NX import

Only after Test 2 passes, send:

```text
Import exactly this NX geometry into the currently empty Mechanical model:
\\Mac\SPP2305_Hannes\00_TEG_Energy_Harvesting\98_Ansys\00_CAD_NX\easy_2_body_contact.prt

Use the installed MCP's geometry guideline and Mechanical scripting
API. Process named selections and coordinate systems when supported. After the
import, call get_model_info and take a screenshot. Report body count, body
names, materials currently assigned, and any import messages or errors. Do not
mesh, create an analysis, define contacts or boundary conditions, solve, or
save the project.
```

This test intentionally mutates only the unsaved, empty Mechanical session by
adding geometry. A CAD translator/license/file-version failure is reported
verbatim and must not be hidden or replaced with invented geometry.

## Test 4: stop before engineering decisions

Review the screenshot and model information. Do not proceed automatically to
contact detection, materials, meshing, loads, or solving. Those are separate
engineering stages with explicit units, assumptions, and validation evidence.
