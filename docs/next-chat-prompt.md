# Prompt For The Next Development Chat

Use this as the first message in a new coding chat.

```text
Please read AGENTS.md, README.md, docs/architecture.md, docs/roadmap.md, and docs/api-research.md first.

We are building ansys-mechanical-mcp: an MCP server for practical Ansys Mechanical/FEM automation using PyMechanical and PyDPF.

Do not implement a broad universal Ansys server.
Do not create fake solver responses.
Do not add large unimplemented tool lists.
Use a local `.venv` in the repository for Python commands and dependency installation. Do not install packages globally.

First task:
Review the current skeleton and propose the smallest concrete v0.1 implementation plan.

The v0.1 prototype should only aim to:
- check the local environment
- start or connect to Mechanical
- execute a controlled Mechanical script
- inspect the current model/analyses at a basic level
- solve an existing Static Structural analysis
- extract a basic result summary with PyDPF

Before writing API-dependent code, verify the relevant official documentation:
- PyMechanical
- Mechanical Scripting API
- PyDPF
- ansys-common-mcp

After the plan, implement only the first small slice that can be tested without an Ansys installation.
```
