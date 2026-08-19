# Mac-to-Parallels PyMechanical-MCP setup template

Use this tracked template to recreate the official Ansys PyMechanical-MCP setup
without copying private usernames, VM addresses, credentials, or keys.

## Variables to determine

```text
<PROJECT_ROOT>       absolute local workspace path
<PYTHON_3_14>        absolute CPython 3.14 executable
<WINDOWS_USER>       SSH-capable Windows account
<WINDOWS_VM_IP>      current Parallels Shared Network address
<MECHANICAL_EXE>     Windows AnsysWBU.exe path
<GRPC_PORT>          dedicated Mechanical gRPC port, for example 50053
<TRANSPORT_MODE>     mode supported by the exact Mechanical/SP version
```

Do not store the Windows password or private SSH key in this file or Codex MCP
arguments.

## 1. Create the Mac environment

```bash
cd <PROJECT_ROOT>
<PYTHON_3_14> -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-mac.txt
.venv/bin/python -m pip check
.venv/bin/ansys-mechanical-mcp --help
```

Confirm that `pip show ansys-mechanical-mcp` reports the official Ansys package
and that its import lives under `ansys/mechanical/mcp` inside `.venv`.

For online installations the standard package-index install is simplest. Use
the release's matching macOS/Python wheelhouse only for offline installation.
A wheelhouse is the same release plus its dependency wheels.

## 2. Enable Windows OpenSSH once

In an elevated PowerShell:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service sshd -StartupType Automatic
Get-Service sshd
```

Use Parallels Shared Network. Do not expose the Mechanical gRPC port through a
Windows firewall rule or bridged network.

## 3. Start a dedicated Mechanical gRPC session

In Windows PowerShell:

```powershell
& "<MECHANICAL_EXE>" -DSApplet -AppModeMech -grpc <GRPC_PORT>
netstat -ano | findstr :<GRPC_PORT>
```

Determine the exact product revision/service pack and select its supported
transport from official PyMechanical security documentation. Never assume
`insecure` is required for a newer patched release.

## 4. Start an explicitly loopback-bound tunnel

On the Mac:

```bash
ssh -N \
  -L 127.0.0.1:<GRPC_PORT>:127.0.0.1:<GRPC_PORT> \
  <WINDOWS_USER>@<WINDOWS_VM_IP>
```

Keep this terminal running. In another terminal:

```bash
nc -vz 127.0.0.1 <GRPC_PORT>
```

The first `127.0.0.1` is the Mac tunnel entrance. The second is the Windows
destination evaluated by SSH.

### Explicit runtime preparation

Create a concrete OpenSSH host alias with a dedicated key and keep all
forwarding loopback-bound. Run `scripts/ensure-ansys-mechanical-runtime` only
when a requested Mechanical workflow cannot connect. The runtime starter:

1. starts the named Parallels VM if needed;
2. waits for passwordless SSH;
3. sends `scripts/windows/Start-AnsysMechanicalGrpc.ps1` to Windows;
4. uses an interactive Windows scheduled task so the Mechanical GUI appears in
   the signed-in desktop session;
5. creates or reuses the SSH tunnel; and
6. returns after the Mac loopback endpoint is ready.

Do not put a password or private-key material in the starter, Codex arguments,
or this repository. `scripts/start-ansys-mechanical-mcp` is deliberately a
separate, side-effect-free launcher for the official stdio server.

## 5. Register the official stdio server

```bash
codex mcp add ansys-mechanical -- \
  <PROJECT_ROOT>/scripts/start-ansys-mechanical-mcp \
  --ip 127.0.0.1 \
  --port <GRPC_PORT> \
  --transport-mode <TRANSPORT_MODE>

codex mcp get ansys-mechanical
```

Restart Codex/ChatGPT Desktop and inspect `/mcp` in a new task.

## 6. Validate in increasing depth

1. Package/entry point: versions, `pip check`, CLI help.
2. TCP tunnel: `nc` to Mac loopback.
3. PyMechanical: explicit matching transport, `is_alive`, and revision only.
4. MCP: status tool.
5. MCP: read-only model-information tool.

Do not begin with file transfer, arbitrary scripts, solve, save, clear,
disconnect, or model mutation.

## 7. Persistence and shutdown

- `.venv` and Codex registration persist on disk.
- Mechanical, SSH, and the stdio MCP server are processes and do not persist as
  a usable connection after they stop.
- Verify the installed MCP version's cleanup behavior. In official v0.2.0,
  stopping a connected MCP process can close Mechanical.

## 8. Record a private local inventory

Create an ignored private guide containing:

- exact installation paths and versions;
- current VM address and Windows username;
- exact Mechanical executable/revision/SP;
- gRPC port and transport;
- Codex MCP registration;
- successful validation date/evidence;
- lifecycle caveats;
- no secrets.

Use `docs/private-mac-parallels-mechanical-mcp-setup.md` as the conventional
ignored filename.
