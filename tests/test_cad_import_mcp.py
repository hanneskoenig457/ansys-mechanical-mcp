import hashlib
import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from ansys_mechanical_mcp.products.mechanical.session import (
    MechanicalSessionConfig,
    MechanicalSessionManager,
)
from ansys_mechanical_mcp.server import create_mcp_server
from ansys_mechanical_mcp.workflows.cad_import import CadImportConfig


def _state(*, imported: bool = False) -> dict:
    return {
        "inspection_status": "complete",
        "product_version": "2025 R1",
        "project_file_name": "ring.mechdb" if imported else None,
        "project_file_identity": "saved-id" if imported else None,
        "unit_system": "StandardNMM",
        "analysis_count": 0,
        "geometry_import_count": 1 if imported else 0,
        "body_count": 1 if imported else 0,
        "bodies": (
            [{"object_id": 9, "name": "Ring", "type": "Solid", "material": None}]
            if imported
            else []
        ),
        "is_empty": not imported,
        "errors": [],
    }


class FakeMechanicalSession:
    def __init__(self, *, input_path: Path, output_path: Path) -> None:
        self.input_path = input_path
        self.output_path = output_path
        self.imported = False
        self.apply_calls = 0

    def run_python_script(self, script: str, **_kwargs) -> str:
        if "__ansys_mechanical_mcp_inspect_geometry_import" in script:
            return json.dumps({"state": _state(imported=self.imported)})
        if "__ansys_mechanical_mcp_apply_geometry_import" in script:
            self.apply_calls += 1
            self.output_path.write_bytes(b"fake-mechdb")
            self.imported = True
            return json.dumps(
                {
                    "state": _state(imported=True),
                    "import": {
                        "object_id": 12,
                        "format": "Automatic",
                        "source_sha256": hashlib.sha256(self.input_path.read_bytes()).hexdigest(),
                        "output_created": True,
                        "overwrite": False,
                    },
                }
            )
        raise AssertionError("unexpected script")


@pytest.mark.anyio
async def test_stage_one_cad_import_in_process_mcp_roundtrip(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    input_root.mkdir()
    output_root.mkdir()
    input_path = input_root / "ring.step"
    output_path = output_root / "ring.mechdb"
    input_path.write_bytes(b"ring")
    session = FakeMechanicalSession(input_path=input_path, output_path=output_path)
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", host="127.0.0.1"),
        connect_to_mechanical=lambda **_kwargs: session,
        system_name="Windows",
    )
    server = create_mcp_server(
        session_manager=manager,
        cad_import_config=CadImportConfig(
            input_root=input_root,
            output_root=output_root,
        ),
    )

    async with create_connected_server_and_client_session(server) as client:
        intake = await client.call_tool("intake_local_cad", {"input_path": "ring.step"})
        preview = await client.call_tool(
            "preview_geometry_import",
            {"input_path": "ring.step", "output_project": "ring.mechdb"},
        )
        plan_id = preview.structuredContent["data"]["plan"]["plan_id"]
        apply = await client.call_tool("apply_geometry_import", {"plan_id": plan_id})
        repeat = await client.call_tool("apply_geometry_import", {"plan_id": plan_id})
        inspection = await client.call_tool("inspect_imported_geometry", {})

    assert intake.isError is False
    assert preview.isError is False
    assert apply.isError is False
    assert apply.structuredContent["data"]["state"]["body_count"] == 1
    assert apply.structuredContent["data"]["attempt_count"] == 1
    assert repeat.isError is True
    assert repeat.structuredContent["error"] == "CAD_IMPORT_PLAN_ALREADY_USED"
    assert inspection.structuredContent["data"]["state"]["body_count"] == 1
    assert session.apply_calls == 1
    for result in (intake, preview, apply, repeat, inspection):
        assert json.loads(json.dumps(result.structuredContent, allow_nan=False)) == (
            result.structuredContent
        )
        assert str(input_root) not in json.dumps(result.structuredContent)


@pytest.mark.anyio
async def test_cad_intake_reports_missing_root_configuration() -> None:
    server = create_mcp_server()

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("intake_local_cad", {"input_path": "ring.step"})

    assert result.isError is True
    assert result.structuredContent["error"] == "CAD_IMPORT_ROOTS_CONFIGURATION_REQUIRED"


@pytest.mark.anyio
async def test_cad_import_rejects_non_local_mechanical_connect(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    input_root.mkdir()
    output_root.mkdir()
    (input_root / "ring.step").write_bytes(b"ring")
    connect_calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(
            mode="connect",
            host="mechanical.example.test",
            transport_mode="insecure",
            allow_insecure_remote=True,
        ),
        connect_to_mechanical=lambda **kwargs: connect_calls.append(kwargs) or object(),
        system_name="Windows",
    )
    server = create_mcp_server(
        session_manager=manager,
        cad_import_config=CadImportConfig(input_root=input_root, output_root=output_root),
    )

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "preview_geometry_import",
            {"input_path": "ring.step", "output_project": "ring.mechdb"},
        )

    assert result.isError is True
    assert result.structuredContent["error"] == "CAD_IMPORT_LOCAL_SESSION_REQUIRED"
    assert connect_calls == []
