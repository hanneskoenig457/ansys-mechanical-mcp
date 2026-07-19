"""MCP server entrypoint."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Annotated, Any, Literal

import anyio
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import CallToolResult, TextContent

from ansys_mechanical_mcp.core.environment import check_environment
from ansys_mechanical_mcp.core.tool_result import ToolResult
from ansys_mechanical_mcp.products.mechanical.context import (
    MechanicalApplicationContext,
    create_mechanical_lifespan,
)
from ansys_mechanical_mcp.products.mechanical.session import (
    MechanicalSessionConfig,
    MechanicalSessionError,
    MechanicalSessionManager,
)

SERVER_NAME = "ansys-mechanical-mcp"


class MechanicalMCPServer(FastMCP[MechanicalApplicationContext]):
    """FastMCP server with the validated single-lifespan transport boundary."""

    _TRANSPORT_ERROR = (
        "This Mechanical session lifecycle currently supports only the stdio transport."
    )

    def run(
        self,
        transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
        mount_path: str | None = None,
    ) -> None:
        """Run only over stdio until HTTP has a process-wide lifecycle."""
        if transport != "stdio":
            raise ValueError(self._TRANSPORT_ERROR)
        super().run(transport=transport, mount_path=mount_path)

    async def run_sse_async(self, mount_path: str | None = None) -> None:
        """Reject SSE because MCP v1 scopes its lifespan per connection."""
        raise RuntimeError(self._TRANSPORT_ERROR)

    async def run_streamable_http_async(self) -> None:
        """Reject Streamable HTTP because MCP v1 lacks the required scope."""
        raise RuntimeError(self._TRANSPORT_ERROR)

    def sse_app(self, mount_path: str | None = None) -> Any:
        """Reject mounting the unsupported SSE application directly."""
        raise RuntimeError(self._TRANSPORT_ERROR)

    def streamable_http_app(self) -> Any:
        """Reject mounting the unsupported Streamable HTTP application directly."""
        raise RuntimeError(self._TRANSPORT_ERROR)


def create_mcp_server(
    *,
    session_config: MechanicalSessionConfig | None = None,
    session_manager: MechanicalSessionManager | None = None,
) -> MechanicalMCPServer:
    """Create the MCP server and register the implemented v0.1 tools."""
    if session_config is not None and session_manager is not None:
        msg = "Provide either 'session_config' or 'session_manager', not both."
        raise ValueError(msg)

    manager = session_manager or MechanicalSessionManager(session_config)
    server = MechanicalMCPServer(
        SERVER_NAME,
        instructions=(
            "Practical Ansys Mechanical/FEM automation tools. "
            "The v0.1 surface is intentionally narrow and does not simulate solver behavior."
        ),
        lifespan=create_mechanical_lifespan(manager),
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

    @server.tool(
        name="inspect_mechanical_model",
        description=(
            "Return read-only Mechanical product and analysis metadata through the persistent "
            "server session. This may start or connect using the configured session mode."
        ),
        structured_output=True,
    )
    async def inspect_mechanical_model_tool(
        ctx: Context[ServerSession, MechanicalApplicationContext],
    ) -> Annotated[CallToolResult, dict[str, Any]]:
        """Inspect the model through the lifespan-owned Mechanical context."""
        app_context = ctx.request_context.lifespan_context
        result = await anyio.to_thread.run_sync(app_context.inspect_model)
        return _mcp_tool_result(result)

    @server.tool(
        name="capture_current_selection",
        description=(
            "Capture the current read-only graphics selection and active tree context from the "
            "same explicitly interactive Mechanical session. Never launches a new session."
        ),
        structured_output=True,
    )
    async def capture_current_selection_tool(
        ctx: Context[ServerSession, MechanicalApplicationContext],
    ) -> Annotated[CallToolResult, dict[str, Any]]:
        """Capture Mechanical's current native selection without model mutation."""
        app_context = ctx.request_context.lifespan_context
        result = await anyio.to_thread.run_sync(app_context.capture_selection)
        return _mcp_tool_result(result)

    return server


def _mcp_tool_result(result: ToolResult) -> CallToolResult:
    """Preserve one structured payload while setting MCP error semantics."""
    payload = result.to_dict()
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, indent=2, allow_nan=False))],
        structuredContent=payload,
        isError=not result.success,
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Run the MCP server.

    Mechanical state is scoped to the FastMCP lifespan. The current stable MCP
    SDK v1 gives the required single lifespan for the local stdio transport.
    """
    parser = argparse.ArgumentParser(prog="ansys-mechanical-mcp")
    parser.add_argument(
        "--check-environment",
        action="store_true",
        help="Print a JSON environment report and exit.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio",),
        default="stdio",
        help="MCP transport. The persistent Mechanical lifecycle currently supports stdio.",
    )
    parser.add_argument(
        "--mechanical-mode",
        choices=("start", "connect"),
        default=None,
        help=(
            "Explicitly start a new Mechanical process or connect to an existing gRPC server. "
            "Mechanical tools return a configuration error when this option is omitted."
        ),
    )
    parser.add_argument(
        "--mechanical-host",
        help="Host name or IP for --mechanical-mode=connect.",
    )
    parser.add_argument(
        "--mechanical-port",
        type=int,
        help="Mechanical gRPC port.",
    )
    parser.add_argument(
        "--mechanical-version",
        help="Requested launch version for --mechanical-mode=start, for example 261.",
    )
    parser.add_argument(
        "--mechanical-exec-file",
        help=(
            "Exact local Mechanical executable for --mechanical-mode=start. When omitted, "
            "PyMechanical path discovery selects the local executable used by transport preflight."
        ),
    )
    parser.add_argument(
        "--mechanical-transport-mode",
        choices=("auto", "wnua", "mtls", "insecure"),
        default="auto",
        help=(
            "Mechanical gRPC transport. 'auto' preflights a local start, keeps secure transport "
            "when supported, requires explicit 'insecure' for legacy service packs, and never "
            "downgrades a connect operation."
        ),
    )
    parser.add_argument(
        "--mechanical-certs-dir",
        help="Certificate directory for Mechanical mTLS transport.",
    )
    parser.add_argument(
        "--mechanical-allow-insecure-remote",
        action="store_true",
        help=(
            "Explicitly acknowledge unencrypted, unauthenticated transport to a non-loopback "
            "Mechanical host. Valid only with --mechanical-transport-mode=insecure."
        ),
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--mechanical-batch",
        dest="mechanical_batch",
        action="store_true",
        help="Use or declare a headless Mechanical session.",
    )
    mode_group.add_argument(
        "--mechanical-ui",
        dest="mechanical_batch",
        action="store_false",
        help="Start with a GUI, or explicitly declare that a connected server has a GUI.",
    )
    parser.set_defaults(mechanical_batch=None)
    parser.add_argument(
        "--mechanical-cleanup-on-exit",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Force-exit Mechanical during server shutdown. Defaults to true only for a "
            "started headless session; started UI and connected sessions default to false."
        ),
    )
    args = parser.parse_args(argv)

    if args.check_environment:
        print(json.dumps(check_environment().to_dict(), indent=2, sort_keys=True))
        return

    try:
        session_config = MechanicalSessionConfig(
            mode=args.mechanical_mode,
            version=args.mechanical_version,
            batch=args.mechanical_batch,
            cleanup_on_exit=args.mechanical_cleanup_on_exit,
            host=args.mechanical_host,
            port=args.mechanical_port,
            transport_mode=args.mechanical_transport_mode,
            certs_dir=args.mechanical_certs_dir,
            allow_insecure_remote=args.mechanical_allow_insecure_remote,
            exec_file=args.mechanical_exec_file,
        )
    except MechanicalSessionError as exc:
        parser.error(str(exc))

    create_mcp_server(session_config=session_config).run(transport=args.transport)


if __name__ == "__main__":
    main()
