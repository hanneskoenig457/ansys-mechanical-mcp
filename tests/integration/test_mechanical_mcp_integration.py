"""Opt-in read-only tests against a real licensed Mechanical installation."""

import os
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from ansys_mechanical_mcp.products.mechanical.session import MechanicalSessionConfig
from ansys_mechanical_mcp.server import create_mcp_server
from ansys_mechanical_mcp.workflows.cad_import import CadImportConfig

RUN_INTEGRATION = os.getenv("ANSYS_MECHANICAL_MCP_RUN_INTEGRATION") == "1"
RUN_INTERACTIVE = os.getenv("ANSYS_MECHANICAL_MCP_RUN_SELECTION_INTEGRATION") == "1"
RUN_CAD_IMPORT = os.getenv("ANSYS_MECHANICAL_MCP_RUN_CAD_IMPORT_INTEGRATION") == "1"

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
        transport_mode=os.getenv("ANSYS_MECHANICAL_MCP_TRANSPORT", "auto"),  # type: ignore[arg-type]
        certs_dir=os.getenv("ANSYS_MECHANICAL_MCP_CERTS_DIR"),
        allow_insecure_remote=(
            os.getenv("ANSYS_MECHANICAL_MCP_ALLOW_INSECURE_REMOTE") == "1"
        ),
        exec_file=os.getenv("ANSYS_MECHANICAL_MCP_EXEC_FILE") if mode == "start" else None,
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


@pytest.mark.anyio
@pytest.mark.skipif(
    not RUN_CAD_IMPORT,
    reason=(
        "set ANSYS_MECHANICAL_MCP_RUN_CAD_IMPORT_INTEGRATION=1 only after preparing "
        "a harmless STEP input, unused output, and new/proven-empty local project"
    ),
)
async def test_real_confirmed_cad_import_mcp_roundtrip() -> None:
    input_root_text = os.getenv("ANSYS_MECHANICAL_MCP_CAD_INPUT_ROOT")
    output_root_text = os.getenv("ANSYS_MECHANICAL_MCP_CAD_OUTPUT_ROOT")
    input_relative = os.getenv("ANSYS_MECHANICAL_MCP_CAD_INPUT")
    output_relative = os.getenv("ANSYS_MECHANICAL_MCP_CAD_OUTPUT")
    assert input_root_text
    assert output_root_text
    assert input_relative
    assert output_relative

    server = create_mcp_server(
        session_config=_session_config(),
        cad_import_config=CadImportConfig(
            input_root=Path(input_root_text),
            output_root=Path(output_root_text),
        ),
    )

    async with create_connected_server_and_client_session(server) as client:
        intake = await client.call_tool(
            "intake_local_cad",
            {"input_path": input_relative},
        )
        assert intake.structuredContent["success"] is True, intake.structuredContent

        preview = await client.call_tool(
            "preview_geometry_import",
            {
                "input_path": input_relative,
                "output_project": output_relative,
            },
        )
        assert preview.structuredContent["success"] is True, preview.structuredContent
        assert preview.structuredContent["data"]["state"]["is_empty"] is True

        plan_id = preview.structuredContent["data"]["plan"]["plan_id"]
        applied = await client.call_tool("apply_geometry_import", {"plan_id": plan_id})
        assert applied.structuredContent["success"] is True, applied.structuredContent
        assert applied.structuredContent["data"]["attempt_count"] == 1
        assert applied.structuredContent["data"]["retry_allowed"] is False

        inspection = await client.call_tool("inspect_imported_geometry", {})
        assert inspection.structuredContent["success"] is True, inspection.structuredContent
        assert inspection.structuredContent["data"]["state"]["body_count"] >= 1
