# AGENTS.md

## Project role

Maintain a reproducible, safety-bounded workspace for the official Ansys
PyMechanical-MCP package, its Mac-to-Parallels connection, and engineering
workflows executed through it.

Do not build or reintroduce a competing `ansys-mechanical-mcp` Python package
unless the user explicitly opens a new, evidence-backed development project.
The former prototype is historical and recoverable from Git before commit
`26a270a`.

## Environment

- Host role: macOS MCP client and documentation/project workspace.
- Mechanical role: licensed Ansys Mechanical in a Parallels Windows VM.
- Python environment: repository-local `.venv`; never install globally.
- Pinned direct dependencies: `requirements-mac.txt`.
- Private machine details: `docs/private-mac-parallels-mechanical-mcp-setup.md`.
- Never commit `.venv`, credentials, private keys, CAD, Mechanical databases,
  result files, or confidential screenshots.

## Mechanical safety

- Use only official Ansys/PyMechanical/PyMechanical-MCP APIs and current
  official documentation for API-dependent behavior.
- Mechanical 2025 R1 without SP04 requires explicit `insecure` gRPC.
- Keep gRPC on `127.0.0.1` endpoints and carry the Mac-to-Windows hop through
  the SSH tunnel. Do not open the Mechanical port to the LAN.
- Prefer status, metadata, and other read-only checks first.
- Do not solve, save, clear, upload, open, close, disconnect, run arbitrary
  code, or mutate a model unless the user has placed that action in scope.
- The official v0.2.0 MCP cleanup calls `Mechanical.exit()` for a connected
  session. Warn before any action that can restart or stop the MCP process when
  Mechanical may contain unsaved work.
- Never invent solver results, model state, API support, or validation evidence.

## Documentation discipline

- Keep `README.md` as the current project entry point.
- Keep exact local installation and connection facts in the private setup
  guide; keep reusable architecture and workflow rules in tracked docs.
- Separate observed facts, assumptions, planned work, and validated outcomes.
- Record dates and exact package/Mechanical versions for live evidence.
- When behavior changes with package versions, verify the installed package and
  current official sources before editing instructions.

## GitHub project workflow

Use `docs/github-development-workflow.md` as the reusable operating model.
GitHub issues are durable work contracts; pull requests carry a reviewable
change; project statuses represent evidence gates rather than percentage done.

When a task names an issue:

1. read its body, dependencies, acceptance criteria, and latest handoff comments;
2. inspect Git status and preserve unrelated user changes;
3. implement only the issue scope on a dedicated branch;
4. verify the result proportionally to risk;
5. post concise evidence and the next action back to the issue;
6. repeat the copy-ready handoff in the final chat response.

Do not force-push handed-off commits or treat a merged PR as proof of licensed
Mechanical validation.

## File editing

Preserve user changes and avoid destructive Git operations. Local generated
state is disposable only when its exact purpose and replacement path are known.
Use the repository virtual environment for any Python command.
