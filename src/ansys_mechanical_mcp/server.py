"""MCP server entrypoint."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from mcp.server.fastmcp import FastMCP

from ansys_mechanical_mcp.core.environment import check_environment

SERVER_NAME = "ansys-mechanical-mcp"


def create_mcp_server() -> FastMCP:
    """Create the MCP server and register the implemented v0.1 tools."""
    server = FastMCP(
        SERVER_NAME,
        instructions=(
            "Practical Ansys Mechanical/FEM automation tools. "
            "The v0.1 surface is intentionally narrow and does not simulate solver behavior."
        ),
    )

    @server.tool(
        name="check_environment",
        description=(
            "Return Python, package, executable, and Ansys environment diagnostics. "
            "This tool does not import PyMechanical, PyDPF, or require Ansys to be installed."
        ),
        structured_output=True,
    )
    def check_environment_tool() -> dict[str, Any]:
        """Return a JSON-compatible environment report."""
        return check_environment().to_dict()

    return server


def main(argv: Sequence[str] | None = None) -> None:
    """Run the MCP server.

    The full MCP server is intentionally not wired yet. The first implemented
    slice is an environment check that can run without an Ansys installation.
    """
    parser = argparse.ArgumentParser(prog="ansys-mechanical-mcp")
    parser.add_argument(
        "--check-environment",
        action="store_true",
        help="Print a JSON environment report and exit.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to use when running the server.",
    )
    args = parser.parse_args(argv)

    if args.check_environment:
        print(json.dumps(check_environment().to_dict(), indent=2, sort_keys=True))
        return

    create_mcp_server().run(transport=args.transport)


if __name__ == "__main__":
    main()
