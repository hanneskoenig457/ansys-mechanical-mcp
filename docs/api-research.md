# API Research

Track official sources and verified API decisions here.

## Primary Sources

- PyAnsys documentation: https://docs.pyansys.com/
- PyMechanical documentation: https://mechanical.docs.pyansys.com/
- Mechanical Scripting API documentation: https://scripting.mechanical.docs.pyansys.com/
- PyDPF documentation: https://dpf.docs.pyansys.com/
- Ansys Common MCP: https://github.com/ansys/pyansys-common-mcp

## Questions To Resolve

- How should the server start Mechanical for the supported Ansys versions?
- Can the server attach to an already running Mechanical session?
- What is the most stable way to execute Mechanical scripts from PyMechanical?
- What structured model inspection data is available directly through PyMechanical?
- Which result files should PyDPF consume for the v0.1 Static Structural workflow?
- How should integration tests detect and skip when Ansys is not installed?

## Decisions

- PyMechanical launch/connect: use `ansys.mechanical.core.launch_mechanical()`
  to launch and `ansys.mechanical.core.Mechanical(...)` or
  `connect_to_mechanical(...)` to connect to an existing Mechanical server.
  Source: https://mechanical.docs.pyansys.com/version/stable/getting_started/running_mechanical.html
- PyMechanical script execution: use `Mechanical.run_python_script(...)` or
  `Mechanical.run_python_script_from_file(...)`; the API returns the string value
  of the last executed statement where possible.
  Source: https://mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/core/mechanical/Mechanical.html
- Mechanical model inspection: use the Mechanical scripting `DataModel` object,
  including `AnalysisList`, `AnalysisNames`, and object lookup methods.
  Source: https://scripting.mechanical.docs.pyansys.com/version/api/ansys/mechanical/stubs/v241/Ansys/ACT/Interfaces/Mechanical/IMechanicalDataModel.html
- Mechanical solve: use the Mechanical scripting `Analysis.Solve(wait: bool)`
  method on a real analysis object.
  Source: https://scripting.mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/stubs/v241/Ansys/ACT/Automation/Mechanical/Analysis.html
- PyDPF result summary: create `ansys.dpf.core.Model(...)` from a result file and
  use `model.metadata.result_info`, `model.metadata.meshed_region`, available
  results, and time/frequency support for v0.1 summaries.
  Source: https://dpf.docs.pyansys.com/version/stable/user_guide/model.html
- PyAnsys Common MCP: if adopted for the server layer, follow its pattern of a
  product-specific context plus a server derived from `PyAnsysBaseMCP`.
  Source: https://common-mcp.docs.pyansys.com/version/stable/getting_started/index.html
- MCP server layer for the first slice: use the official Python MCP SDK
  `FastMCP` server directly for the single `check_environment` tool. Keep
  `ansys-common-mcp` optional until the project needs a persistent product
  context for real Mechanical sessions.
  Source: https://modelcontextprotocol.github.io/python-sdk/server/

## First Implementation Slice

The first slice is an environment check. It deliberately avoids importing
PyMechanical, PyDPF, or Ansys Common MCP so that the tests stay independent from
licensed Ansys products and optional dependencies.
