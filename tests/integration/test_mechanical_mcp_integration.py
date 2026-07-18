"""Opt-in read-only tests against a real licensed Mechanical installation."""

import os

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from ansys_mechanical_mcp.products.mechanical.session import MechanicalSessionConfig
from ansys_mechanical_mcp.server import create_mcp_server

RUN_INTEGRATION = os.getenv("ANSYS_MECHANICAL_MCP_RUN_INTEGRATION") == "1"
RUN_INTERACTIVE = os.getenv("ANSYS_MECHANICAL_MCP_RUN_SELECTION_INTEGRATION") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason="set ANSYS_MECHANICAL_MCP_RUN_INTEGRATION=1 for licensed integration tests",
)


def _session_config(*, interactive: bool = False) -> MechanicalSessionConfig:
    mode = os.getenv("ANSYS_MECHANICAL_MCP_MODE", "connect")
    port_text = os.getenv("ANSYS_MECHANICAL_MCP_PORT")
    return MechanicalSessionConfig(
        mode=mode,  # type: ignore[arg-type]
        host=os.getenv("ANSYS_MECHANICAL_MCP_HOST") if mode == "connect" else None,
        port=int(port_text) if port_text else None,
        version=os.getenv("ANSYS_MECHANICAL_MCP_VERSION") if mode == "start" else None,
        batch=False if interactive else None,
    )


@pytest.mark.anyio
async def test_real_read_only_model_inspection_mcp_roundtrip() -> None:
    server = create_mcp_server(session_config=_session_config())

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("inspect_mechanical_model", {})

    assert result.structuredContent["success"] is True, result.structuredContent
    assert isinstance(result.structuredContent["data"]["analyses"], list)


@pytest.mark.anyio
@pytest.mark.skipif(
    not RUN_INTERACTIVE,
    reason=("set ANSYS_MECHANICAL_MCP_RUN_SELECTION_INTEGRATION=1 after preparing a GUI session"),
)
async def test_real_read_only_current_selection_mcp_roundtrip() -> None:
    server = create_mcp_server(session_config=_session_config(interactive=True))

    async with create_connected_server_and_client_session(server) as client:
        inspection = await client.call_tool("inspect_mechanical_model", {})
        assert inspection.structuredContent["success"] is True, inspection.structuredContent

        result = await client.call_tool("capture_current_selection", {})

    assert result.structuredContent["success"] is True, result.structuredContent
    snapshot = result.structuredContent["data"]["snapshot"]
    assert snapshot["provenance"] == "mechanical_current_selection"
    assert snapshot["errors"] == []
