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
| Mechanical target seen by the Mac | `127.0.0.1:50053` |
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
(see below), and symlinks the skill into `~/.claude/skills` and
`~/.codex/skills`. It then prints the two steps it cannot do for you: the SSH
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
  "$PWD/scripts/start-ansys-mechanical-mcp" \
  --ip 127.0.0.1 \
  --port 50053 \
  --transport-mode insecure
```

Confirm the stored registration with:

```bash
codex mcp get ansys-mechanical
```

For an actual Mechanical task, first try the MCP connection. If the runtime is
not reachable, start the runtime that matches the target and then call
`connect_to_mechanical`:

| Target | Runtime starter |
| --- | --- |
| Standalone `.mechdb` | `scripts/ensure-ansys-mechanical-runtime` |
| Workbench `.wbpj` system | `scripts/ensure-ansys-workbench-mechanical-runtime '<wbpj>' '<system>'` |

Both serve the same MCP endpoint `127.0.0.1:50053`, so the MCP registration
never changes. See
[Workbench-managed Mechanical access](docs/workbench-integration.md) for the
second one.

The skill in [skills/ansys-mechanical](skills/ansys-mechanical/SKILL.md) applies
this sequence across projects. It is the single source of truth: both
`~/.claude/skills/ansys-mechanical/SKILL.md` and
`~/.codex/skills/ansys-mechanical/SKILL.md` are symlinks to that file, so an
edit here reaches every agent at once.

## Persistence at a glance

- `.venv` is durable on disk until it is deleted, but it is not committed.
  Recreate it with `scripts/bootstrap-workstation`.
- The MCP remote-path patch lives in `.venv/.../site-packages` and does **not**
  survive a reinstall or upgrade of `ansys-mechanical-mcp`. Rerun
  `scripts/patch-mcp-remote-paths.py` after any such change.
- The skill is committed here; the agent copies under `~/.claude/skills` and
  `~/.codex/skills` are symlinks recreated by the bootstrap script.
- The Codex MCP entry is durable in the user's Codex configuration until it is
  removed or changed.
- The dedicated SSH key and `ansys-mechanical-vm` host alias are durable in
  `~/.ssh`; their contents are never committed.
- Mechanical and the SSH tunnel remain runtime state. The explicit runtime
  starter recreates them only for a requested Mechanical workflow.
- `127.0.0.1:50053` on the Mac is the local entrance to the SSH tunnel. The
  tunnel forwards it to `127.0.0.1:50053` inside Windows.
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
- [Reusable Mac/Parallels setup template](docs/mac-parallels-mechanical-mcp-setup-template.md)
- [Official server inventory and boundaries](docs/official-pymechanical-mcp.md)
- [Live validation workflow](docs/live-validation-workflow.md)
- [Productive cold-start and NX-import test runbook](docs/productive-test-runbook.md)
- [Repository roadmap](docs/roadmap.md)
- [Steady-state thermal application roadmap](docs/steady-state-thermal-workflow.md)
- [Reusable GitHub project workflow](docs/github-development-workflow.md)

## Operating boundary

Mechanical 2025 R1 without SP04 supports only insecure gRPC. In this setup,
plaintext gRPC is limited to loopback on both machines and the cross-machine
hop is an encrypted SSH tunnel. Do not expose port `50053` directly to the LAN,
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
