# Deployment architecture

## Decision

Use the official Ansys PyMechanical-MCP server as the Mechanical integration
layer. This repository supplies deployment, safety, validation, and
application-level workflow material around it; it does not implement another
MCP server.

## Runtime topology

```text
Natural-language request
        |
        v
Codex / ChatGPT Desktop on macOS
        |
        | starts immediately; no VM side effects
        v
official ansys-mechanical-mcp in <repository>/.venv
        |
        | PyMechanical: try 127.0.0.1:50056
        v
global skill runs explicit runtime starter only if unavailable
        |
        | starts/verifies VM, Windows task, and SSH tunnel
        v
Mac SSH tunnel entrance at 127.0.0.1:50056
        |
        | encrypted SSH through Parallels Shared Network
        v
Windows 127.0.0.1:50056 (standalone only; Workbench system ports are dynamic)
        |
        v
Ansys Mechanical 2025 R1 gRPC service
```

The MCP protocol and Mechanical gRPC are separate transports. Codex launches a
small side-effect-free script that immediately replaces itself with the
official MCP server. When a real Mechanical request cannot connect to the Mac
loopback endpoint, the global skill runs the separate runtime starter. That
starter prepares the VM, Windows task, and tunnel but does not start or stop
the MCP process. The MCP then connects through PyMechanical to the loopback
port, which SSH forwards into Windows.

## Responsibility boundaries

| Concern | Authority |
| --- | --- |
| MCP tools and lifecycle | Official `ansys-mechanical-mcp` package |
| Mechanical connection and scripting | Official PyMechanical package |
| Model state, solve, results, and entity identity | Running Mechanical instance |
| Cross-machine confidentiality | SSH tunnel plus VM/firewall containment |
| Runtime bootstrap | Explicit repository starter plus triggerless interactive Windows launcher tasks |
| Cross-project operating order | Global personal `ansys-mechanical` skill |
| Codex server registration | User-level Codex configuration |
| Setup, validation, prompts, and project method | This repository |
| Secrets and private machine values | Local ignored files and OS credential stores |

## State and persistence

```text
Repository files       durable, version controlled
Private setup guide    durable, local, ignored by Git
.venv                  durable, local, reproducible, ignored by Git
Codex MCP entry        durable user configuration
SSH alias/key          durable user configuration, outside Git
Windows launcher tasks durable, triggerless, updated by runtime starters
Mechanical process     runtime only
SSH tunnel process     runtime only, recreated by explicit starter
MCP stdio process      runtime only, owned by Codex
```

The same local address does not imply the same computer. `127.0.0.1` on macOS
is the SSH tunnel entrance; `127.0.0.1` in the forwarding destination is
Windows loopback.

## Security boundary

Mechanical 2025 R1 without SP04 cannot use the newer secure gRPC modes. This
deployment accepts explicit `insecure` gRPC only because:

1. the Mac endpoint is bound to `127.0.0.1`;
2. the forwarding destination is Windows `127.0.0.1`;
3. the cross-machine hop is encrypted by SSH;
4. Parallels remains in Shared Network mode;
5. no Windows firewall opening is created for the Mechanical port.

This is a private development topology, not a general remote-service design.

Visible GUI automation remains bounded by Windows session isolation. Runtime
starters invoke triggerless interactive launcher tasks only after an
interactive console logon exists; no Ansys task runs merely because Windows
logged on. Automatic Windows sign-in is a separate, explicit decision and does
not change the SSH or gRPC containment described above.

## Lifecycle caveat

PyMechanical-MCP 0.2.0 connects with `cleanup_on_exit=False`, but its MCP
product cleanup subsequently calls `Mechanical.exit()` when a connection is
present. Therefore stopping or restarting Codex's MCP process can close the
Mechanical application. The operator must save or discard work deliberately
before restarting the full stack.

## Extension rule

Add repository content only when it supports one of these roles:

- reproducible installation or diagnostics;
- safety-bounded Mechanical operation;
- reusable prompts/scripts for an engineering workflow;
- validation evidence and regression procedures;
- project-management templates or AI operating instructions.

Do not recreate tools already supplied by the official package merely to keep
the old source layout alive. If an official tool has a concrete gap, first
document the missing behavior and reproduce it against the installed version;
then decide whether the right result is an upstream issue, an application-level
script, or a separate extension project.
