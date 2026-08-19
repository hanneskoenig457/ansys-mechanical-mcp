# Workspace roadmap

## Completed: adopt the official server

- Retire the competing local MCP implementation from the active tree.
- Install official `ansys-mechanical-mcp==0.2.0` in the repository `.venv`.
- Connect it through Mac loopback and an SSH tunnel to Mechanical 2025 R1 in
  Parallels Windows.
- Register the official stdio server with Codex.
- Prove a live PyMechanical connection and successful Codex MCP loading.

## Completed: make setup reproducible and safe

- Keep exact Python/package/path facts in the private setup guide.
- Pin direct Mac dependencies.
- Keep public architecture and validation docs free of private credentials.
- Explicitly document the official v0.2.0 shutdown/`Mechanical.exit()` caveat.
- Use read-only first prompts and classify consequential tools.
- Make a clone self-sufficient: `scripts/bootstrap-workstation` rebuilds the
  environment, and `scripts/patch-mcp-remote-paths.py` turns the former
  site-packages hand-edit into a verified, idempotent step.
- Commit the agent skill and share it with Claude Code and Codex by symlink,
  so both agents follow one file.

## Completed: reach Workbench-managed projects

- Reach a Mechanical system inside a `.wbpj` without leaving Workbench, using
  PyWorkbench and `RunWB2.exe -I -E "StartServer(...)"`.
- Remap the per-system Mechanical port onto the existing `50053` endpoint so
  the MCP registration is unchanged.
- Carry every forward over one shared SSH ControlMaster connection.
- See [workbench-integration.md](workbench-integration.md) for the caveats
  found while validating it.

## Next: exercise official capabilities deliberately

1. Capture a structured status/model-info baseline from the official tools.
2. Inventory which v0.2.0 tools behave correctly with Mechanical 2025 R1 over
   the tunnel.
3. Record version-specific gaps as upstream issues or application-level
   workarounds; do not fork the server reflexively.
4. Establish safe local input/output roots for any file-transfer workflow.
5. Build one useful engineering workflow on top of the official server.

## Engineering application track

The selected learning project remains a staged steady-state thermal workflow.
Its goal is no longer to add MCP tools. It should use official tools plus
reviewed Mechanical scripts, with each engineering mutation and result checked
against a harmless model. See
[steady-state-thermal-workflow.md](steady-state-thermal-workflow.md).

## Reusable project-method track

Extract the GitHub issue/project/PR/handoff conventions into a reusable project
operating system. The tracked reference is
[github-development-workflow.md](github-development-workflow.md). A future
Codex skill can package that method after its desired global or project-local
installation location is chosen.

## Decision gate for custom development

Only open a new MCP-extension project if all of the following are true:

- a concrete user workflow is blocked;
- the behavior is reproduced against a pinned official release;
- configuration, prompt, or reviewed script cannot solve it safely;
- an upstream issue/feature request is insufficient or has an unsuitable
  timeline;
- the extension has a narrow contract and independent validation plan.

Until then, maintain integration and workflow assets, not a server fork.
