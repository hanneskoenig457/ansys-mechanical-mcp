# Ansys Mechanical MCP workspace

This repository is the local operating and project workspace for the official
[PyMechanical-MCP](https://github.com/ansys/pymechanical-mcp) server. It no
longer develops a competing MCP server.

The earlier unofficial prototype remains recoverable from Git history up to
commit `26a270a`. Its active source tree and prototype-specific documentation
were retired after Ansys published the official server with the required
session, scripting, solve, file, visualization, and workflow tools.

## Current purpose

This workspace now owns five things:

1. the reproducible local Python environment for the official MCP server,
   including a one-shot workstation bootstrap;
2. a side-effect-free MCP launcher, two explicit runtime starters (standalone
   Mechanical and Workbench-managed), and the private Mac-to-Parallels
   connection guide alongside a public architecture description;
3. safe validation and operating procedures for Mechanical workflows;
4. the agent skill that drives all of the above, shared by Claude Code and
   Codex from a single file;
5. reusable GitHub project-management conventions for human/AI collaboration.

It does **not** vendor or maintain the official Ansys package. The package is
installed into the local `.venv` and stays excluded from Git.

## Installed local baseline

Verified on 2026-08-13:

| Component | Installed value |
| --- | --- |
| Host | macOS 26.5.2, Apple Silicon (`arm64`) |
| Python | CPython 3.14.2 |
| Virtual environment | `<repository>/.venv` |
| Official MCP package | `ansys-mechanical-mcp==0.2.0` |
| PyMechanical | `ansys-mechanical-core==0.13.2` |
| PyWorkbench (Workbench-managed path only) | `ansys-workbench-core==0.14.0` |
| Codex MCP name | `ansys-mechanical` |
| Mechanical target seen by the Mac | `127.0.0.1:50056` |
| Mechanical runtime | Ansys Mechanical 2025 R1 (`251`) in Parallels Windows |
| gRPC mode | Explicit `insecure`, carried only through loopback and an SSH tunnel |

The official MCP package is a universal `py3-none-any` wheel. The v0.2.0
release also provides platform/Python-specific wheelhouse archives. A
wheelhouse is an offline bundle of this same server plus compatible
dependencies; it is not a different MCP implementation. This installation was
resolved by `pip` in the virtual environment and did not use a downloaded
wheelhouse archive. For an offline recreation on this Mac, use the official
`macos-latest-3.14` wheelhouse.

The exact paths, setup commands, persistence rules, release assets, Codex
registration, SSH tunnel, and validation evidence are recorded in the private
guide:

- `docs/private-mac-parallels-mechanical-mcp-setup.md` (local/private and
  intentionally ignored by Git)
- [Reusable Mac/Parallels setup template](docs/mac-parallels-mechanical-mcp-setup-template.md)

## Recreate the Python environment

On a fresh machine, clone the repository and run the bootstrap script. It is
idempotent, so it also repairs a partial or broken setup:

```bash
scripts/bootstrap-workstation
```

It creates `.venv`, installs the pinned requirements from
[requirements-mac.txt](requirements-mac.txt), reapplies the local MCP patch
(see below), and symlinks the repository skills into `~/.agents/skills`
(current Codex discovery), `~/.codex/skills` (legacy Codex location), and
`~/.claude/skills`. It then prints the two steps it cannot do for you: the SSH
key/host alias (private material) and the agent's MCP registration.

The equivalent manual sequence:

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-mac.txt
.venv/bin/python -m pip check
.venv/bin/python scripts/patch-mcp-remote-paths.py
```

### The MCP remote-path patch

`scripts/patch-mcp-remote-paths.py` removes the local `Path(...).exists()`
checks from the official server's `open_project` and `save_project`. Mechanical
runs on the remote Windows VM, so every path those two tools receive is a
`C:\...` path that never exists on the Mac; upstream's check rejects them all
before Mechanical is contacted. The patch edits `site-packages`, so **pip
overwrites it on any reinstall or upgrade** — rerun the script (or
`bootstrap-workstation`) afterwards. It is idempotent and verifies its own
result.

Register the side-effect-free launcher after the one-time SSH key setup
described in the private guide. Loading the MCP starts only the official stdio
server; it does not open Parallels or connect to Mechanical:

```bash
codex mcp add ansys-mechanical -- \
  "$PWD/scripts/start-ansys-mechanical-mcp"
```

The wrapper supplies `--ip 127.0.0.1 --port 50056 --transport-mode insecure`
unless a caller explicitly overrides one of those options.

Confirm the stored registration with:

```bash
codex mcp get ansys-mechanical
```

The tracked launcher passes the official server's `--static-tools` option.
Codex receives its tool list during the initial MCP handshake, while the
official server's default dynamic mode reveals Mechanical-dependent tools only
after a later connection.  Static exposure makes the full official surface
available to Codex without starting or connecting to Mechanical; it does not
authorize scripts, saves, or solves. Validate this after package upgrades with:

```bash
.venv/bin/python scripts/check-mechanical-mcp-tool-surface.py
```

The changed launch option takes effect only in a new MCP handshake. Do not
restart the MCP while an unsaved Mechanical session is open: the installed
v0.2.0 cleanup path can close Mechanical.

For an actual Mechanical task, first try the MCP connection. If the runtime is
not reachable, start the runtime that matches the target and then call
`connect_to_mechanical`:

| Target | Runtime starter |
| --- | --- |
| Standalone `.mechdb` | `scripts/ensure-ansys-mechanical-runtime` |
| Workbench `.wbpj` system | `scripts/ensure-ansys-workbench-mechanical-runtime '<wbpj>' ['<system>']` |

Both serve the same MCP endpoint `127.0.0.1:50056`, so the MCP registration
never changes. See
[Workbench-managed Mechanical access](docs/workbench-integration.md) for the
second one.

For a Workbench `.wbpj`, Workbench owns external CAD: attach or create it in
the target system's **Geometry** cell, update the project, and then use
Mechanical.  Do not directly import external CAD into a Workbench-managed
Mechanical session.  The proposed PyAnsys Geometry/visible-SpaceClaim path is
tracked in [PyAnsys Geometry with Workbench-owned CAD](docs/pyansys-geometry-workflow.md).
Direct Mechanical CAD import remains an explicitly standalone compatibility
workflow only.

For a Workbench project with exactly one system containing both `Model` and
`Solution`, the system argument is optional. The runtime discovers and
validates that system after opening the project. An explicit internal system
name is required only when a project contains multiple Mechanical systems.
There is no longer a manual `GetAllSystems()` discovery step.

### On-demand MCP readiness

For a project-neutral warm state, double-click
`~/Applications/Ansys MCP Ready.app`. It starts the otherwise stopped VM on
demand, relies on the configured Windows autologon, prepares licensing and a
blank visible Workbench, and establishes the managed SSH connection plus the
Workbench tunnel at `127.0.0.1:51000`. It deliberately opens no user project,
starts no Mechanical system, and therefore does not bind the Mechanical MCP
endpoint `50056` yet. The AI performs those model-specific steps when an actual
task arrives. Neither Parallels nor the VM is configured to start with macOS.
Detailed app output is stored in `~/Library/Logs/Ansys MCP Ready.log`.
Success is non-modal: the app exits by itself after readiness is proven. Only
a genuine launcher failure opens an error dialog.

The app is the only coordinator. Windows has no Ansys task triggered at
logon; only the automatic Windows sign-in occurs when the app starts the VM.
The app then immediately restarts the Ansys CVD and Licensing Tomcat services
on a cold start, waits for `lmgrd`, `ansyslmd`, ports `1055`/`1084`, and a
stability window, and performs a real one-second `ANS_WB` checkout with the
official `ansysli_util.exe`. The triggerless interactive launcher is also
protected by a named mutex, so simultaneous app/AI invocations reuse the same
Workbench instead of competing for port `51000`.

Windows automatic sign-in is configured separately with Microsoft's signed
Sysinternals Autologon utility; never pass its password through this
repository, SSH, shell history, or a chat. Parallels and the VM remain excluded
from macOS login items and Parallels host-start autostart.

The skill in [skills/ansys-mechanical](skills/ansys-mechanical/SKILL.md) applies
this sequence across projects. It is the single source of truth: the matching
entries under `~/.agents/skills`, `~/.codex/skills`, and `~/.claude/skills`
symlink to the repository source, so an edit here reaches Codex and Claude at
once.

## Adapting to another machine

Nothing below has to be set for the reference setup; every entry has a working
default. They exist so a different Mac, VM, Windows account, or Ansys release
does not require editing the scripts.

| Variable | Default | What it selects |
| --- | --- | --- |
| `ANSYS_MECHANICAL_SSH_HOST` | `ansys-mechanical-vm` | SSH host alias for the Windows VM |
| `ANSYS_PARALLELS_VM` | `Windows 11` | VM name passed to `prlctl` |
| `ANSYS_PARALLELS_VM_BUNDLE` | `/Volumes/WindowsVM/Windows 11.pvm` | `.pvm` opened to show the console |
| `ANSYS_VERSION` | `251` | Ansys release directory (`v251` = 2025 R1), used for both Windows executables |
| `ANSYS_MCP_PYTHON` | CPython 3.14 framework build | Interpreter the bootstrap builds `.venv` from |
| `ANSYS_MECHANICAL_GRPC_PORT` | `50056` | Local Mechanical gRPC port; standalone Windows Mechanical uses the same port |
| `ANSYS_WORKBENCH_GRPC_PORT` | `51000` | Workbench project-schematic gRPC port |
| `ANSYS_WINDOWS_TEMP` | auto-detected via `$env:TEMP` | Windows directory the bootstrap script is copied into |
| `ANSYS_LICENSE_PORT` | `1055` | FlexNet port probed for licensing readiness |
| `ANSYS_LICENSING_CLIENT_PORT` | `1084` | Local Ansys licensing web endpoint included in readiness |
| `ANSYS_LICENSING_STABILITY_SECONDS` | `20` | Continuous healthy window before the real `ANS_WB` checkout |
| `ANSYS_WORKBENCH_PROJECT_PATH` | — | `.wbpj` to open, if not passed as argument 1 |
| `ANSYS_WORKBENCH_SYSTEM_NAME` | auto when unique | Internal system name override, if not passed as argument 2 |
| `ANSYS_WORKBENCH_FORCE_RESTART` | `0` | `1` replaces a live Mechanical server, killing that session |

Timeouts, all in seconds: `ANSYS_MECHANICAL_SSH_WAIT_SECONDS` (180),
`ANSYS_MECHANICAL_START_WAIT_SECONDS` (180),
`ANSYS_MECHANICAL_TUNNEL_WAIT_SECONDS` (30),
`ANSYS_MECHANICAL_GRPC_WAIT_SECONDS` (120; Workbench-system gRPC readiness
after its TCP tunnel opens),
`ANSYS_WORKBENCH_START_WAIT_SECONDS` (180), and
`ANSYS_WORKBENCH_READY_WAIT_SECONDS` (300, the budget for the interactive
sign-in and the licensing daemons; deliberately separate so a slow cold boot
does not eat into the time allowed for Workbench itself).

Still machine-specific and **not** covered by any of these: the SSH key and
host alias, the MCP registration with your agent, and the Ansys installation
in the VM itself. The bootstrap script prints those as remaining manual steps.

## Persistence at a glance

- `.venv` is durable on disk until it is deleted, but it is not committed.
  Recreate it with `scripts/bootstrap-workstation`.
- The MCP remote-path patch lives in `.venv/.../site-packages` and does **not**
  survive a reinstall or upgrade of `ansys-mechanical-mcp`. Rerun
  `scripts/patch-mcp-remote-paths.py` after any such change.
- `skills/ansys-mechanical/SKILL.md.in` is the committed template; the bootstrap
  script generates `SKILL.md` next to it with this clone's absolute path
  substituted for `@REPO_DIR@`. The generated file is git-ignored, so edit the
  template. Skill entries under `~/.agents/skills`, `~/.codex/skills`, and
  `~/.claude/skills` are symlinked to their repository sources and repaired by
  the bootstrap script.
- The Codex MCP entry is durable in the user's Codex configuration until it is
  removed or changed.
- The dedicated SSH key and `ansys-mechanical-vm` host alias are durable in
  `~/.ssh`; their contents are never committed.
- Mechanical and the SSH tunnel remain runtime state. The explicit runtime
  starter recreates them only for a requested Mechanical workflow. The
  project-neutral readiness app can prepare visible blank Workbench and its
  tunnel on demand without starting Mechanical.
- `127.0.0.1:50056` on the Mac is the local entrance to the SSH tunnel. For a
  standalone session it forwards to the same Windows port; Workbench remaps
  its dynamic per-system port there.
- The official v0.2.0 server calls `Mechanical.exit()` during MCP shutdown when
  connected. Treat Codex/App restarts as capable of closing the connected
  Mechanical session; never leave unsaved work in that session.

The ChatGPT desktop app's SSH-host feature is separate: it runs remote Codex
project chats against the Windows filesystem and shell. It may use the same
OpenSSH host alias, but it is not the lifecycle owner of this Mechanical
tunnel. A remote Windows chat also uses Windows-side MCP configuration rather
than automatically inheriting this Mac-side server.

## Documentation map

- [Deployment architecture](docs/architecture.md)
- [Workbench-managed Mechanical access](docs/workbench-integration.md)
- [Documentation lookup against Ansys Help](docs/ansys-help-documentation-lookup.md)
- [Reusable Mac/Parallels setup template](docs/mac-parallels-mechanical-mcp-setup-template.md)
- [Official server inventory and boundaries](docs/official-pymechanical-mcp.md)
- [Live validation workflow](docs/live-validation-workflow.md)
- [Standalone Mechanical CAD-import compatibility runbook](docs/productive-test-runbook.md)
- [Proposed PyAnsys Geometry and Workbench-owned CAD workflow](docs/pyansys-geometry-workflow.md)
- [Repository roadmap](docs/roadmap.md)
- [Steady-state thermal application roadmap](docs/steady-state-thermal-workflow.md)
- [Reusable GitHub project workflow](docs/github-development-workflow.md)
- [Reusable CAE project operations skill](skills/cae-project-ops/SKILL.md)

## GitHub work tracking

Repository Markdown records the current validated setup. Proposed and active
work is tracked in GitHub rather than duplicated as a chat-only or local task
list:

- [Ansys Mechanical MCP Toolchain Project](https://github.com/users/hanneskoenig457/projects/4)
- [Official MCP capability audit](https://github.com/hanneskoenig457/ansys-mechanical-mcp/issues/23)
- [PyAnsys Geometry evaluation](https://github.com/hanneskoenig457/ansys-mechanical-mcp/issues/24)
- [Optional Workbench “Open for MCP” idea](https://github.com/hanneskoenig457/ansys-mechanical-mcp/issues/25)
- [Separate staged thermal workflow Project](https://github.com/users/hanneskoenig457/projects/3)

The first three Project items are deliberately different: a committed
capability audit, a bounded research decision, and an uncommitted idea. Their
status must not be inferred from their presence on the board.

## Operating boundary

Mechanical 2025 R1 without SP04 supports only insecure gRPC. In this setup,
plaintext gRPC is limited to loopback on both machines and the cross-machine
hop is an encrypted SSH tunnel. Do not expose port `50056` directly to the LAN,
use bridged networking for convenience, or treat `insecure` as acceptable for a
general remote deployment.

Start with read-only status and model inspection. Model changes, solve actions,
file writes, project closing, and disconnect operations require explicit scope
and awareness of their effects.

## Official sources

- [PyMechanical-MCP repository](https://github.com/ansys/pymechanical-mcp)
- [PyMechanical-MCP documentation](https://mechanical-mcp.docs.pyansys.com/)
- [PyMechanical documentation](https://mechanical.docs.pyansys.com/)
- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)

## License

The documentation and project material in this repository remain under the
repository [MIT license](LICENSE). The installed official PyMechanical-MCP
package is separate software distributed by Ansys under Apache-2.0.
