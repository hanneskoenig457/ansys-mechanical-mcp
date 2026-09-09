#!/usr/bin/env python3
"""Verify the initial MCP tool list exposed by the local launch wrapper.

The check starts an isolated stdio server without ``--connect-on-startup`` and
therefore never launches or connects to Mechanical.  It protects the Codex
integration requirement that Mechanical scripting and solve tools are visible
at the initial MCP handshake.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {
    "check_mechanical_status",
    "check_mechanical_installed",
    "launch_mechanical",
    "connect_to_mechanical",
    "disconnect_from_mechanical",
    "list_mechanical_instances",
    "list_files",
    "upload_file",
    "download_file",
    "clear_mechanical",
    "save_project",
    "open_project",
    "run_python_script",
    "solve_analysis",
    "get_model_info",
    "export_results",
    "screenshot",
    "create_custom_plot",
    "get_mechanical_logs",
    "run_python_code",
    "get_guidelines_for",
}


async def list_initial_tools(wrapper: Path) -> set[str]:
    """Return tools reported in the wrapper's first MCP handshake."""
    with tempfile.TemporaryDirectory(prefix="ansys-mcp-tool-surface-") as config_dir:
        environment = dict(os.environ, MPLCONFIGDIR=config_dir)
        parameters = StdioServerParameters(
            command=str(wrapper),
            args=["--ip", "127.0.0.1", "--port", "9", "--transport-mode", "insecure"],
            cwd=str(wrapper.parent.parent),
            env=environment,
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()
    return {tool.name for tool in response.tools}


def main() -> int:
    repository = Path(__file__).resolve().parent.parent
    wrapper = repository / "scripts" / "start-ansys-mechanical-mcp"
    actual_tools = asyncio.run(list_initial_tools(wrapper))
    missing = sorted(EXPECTED_TOOLS - actual_tools)
    unexpected = sorted(actual_tools - EXPECTED_TOOLS)
    print(
        json.dumps(
            {
                "expected_count": len(EXPECTED_TOOLS),
                "actual_count": len(actual_tools),
                "missing": missing,
                "unexpected": unexpected,
            },
            indent=2,
        )
    )
    return 1 if missing or unexpected else 0


if __name__ == "__main__":
    raise SystemExit(main())
