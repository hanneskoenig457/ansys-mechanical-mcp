import builtins
import json
import threading
import time

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

import ansys_mechanical_mcp.server as server_module
from ansys_mechanical_mcp.products.mechanical.session import (
    MechanicalSessionConfig,
    MechanicalSessionManager,
)
from ansys_mechanical_mcp.server import create_mcp_server


class FakeMechanicalSession:
    def __init__(self, result: str) -> None:
        self.result = result
        self.script_calls = []
        self.script_thread_ids = []
        self.exit_calls = []
        self.exit_thread_ids = []

    def run_python_script(self, script, **kwargs):
        self.script_calls.append((script, kwargs))
        self.script_thread_ids.append(threading.get_ident())
        return self.result

    def exit(self, *, force: bool) -> None:
        self.exit_calls.append({"force": force})
        self.exit_thread_ids.append(threading.get_ident())


@pytest.mark.anyio
async def test_server_registers_implemented_tools() -> None:
    server = create_mcp_server()

    tools = await server.list_tools()

    assert [tool.name for tool in tools] == [
        "check_environment",
        "inspect_mechanical_model",
        "capture_current_selection",
    ]
    assert all(tool.outputSchema is not None for tool in tools)


def test_server_rejects_unvalidated_http_transport_entrypoints() -> None:
    server = create_mcp_server()

    with pytest.raises(ValueError, match="only the stdio transport"):
        server.run(transport="streamable-http")
    with pytest.raises(RuntimeError, match="only the stdio transport"):
        server.streamable_http_app()


def test_cli_keeps_mechanical_unconfigured_without_explicit_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeServer:
        def run(self, *, transport: str) -> None:
            captured["transport"] = transport

    def fake_create_mcp_server(*, session_config):
        captured["config"] = session_config
        return FakeServer()

    monkeypatch.setattr(server_module, "create_mcp_server", fake_create_mcp_server)

    server_module.main([])

    assert captured["transport"] == "stdio"
    assert captured["config"].mode is None
    assert captured["config"].effective_cleanup_on_exit is False


def test_cli_started_ui_cleanup_requires_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeServer:
        def run(self, *, transport: str) -> None:
            captured["transport"] = transport

    def fake_create_mcp_server(*, session_config):
        captured["config"] = session_config
        return FakeServer()

    monkeypatch.setattr(server_module, "create_mcp_server", fake_create_mcp_server)

    server_module.main(["--mechanical-mode", "start", "--mechanical-ui"])

    assert captured["config"].interactive is True
    assert captured["config"].effective_cleanup_on_exit is False


@pytest.mark.anyio
async def test_check_environment_tool_returns_structured_payload_without_lifespan() -> None:
    server = create_mcp_server()

    _content, structured = await server.call_tool("check_environment", {})

    assert structured["success"] is True
    assert structured["data"]["ready"]["mcp_server"] is True
    assert "packages" in structured["data"]


@pytest.mark.anyio
async def test_mechanical_tool_requires_explicit_start_or_connect_mode() -> None:
    server = create_mcp_server()

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("inspect_mechanical_model", {})

    assert result.isError is True
    assert result.structuredContent["error"] == "MECHANICAL_SESSION_CONFIGURATION_REQUIRED"
    assert result.structuredContent["data"]["operation"] == "configure"


@pytest.mark.anyio
async def test_selection_tool_requires_explicit_start_or_connect_mode() -> None:
    server = create_mcp_server()

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("capture_current_selection", {})

    assert result.isError is True
    assert result.structuredContent["error"] == "MECHANICAL_SESSION_CONFIGURATION_REQUIRED"


@pytest.mark.anyio
async def test_inspection_mcp_roundtrip_reuses_session_and_cleans_up_once() -> None:
    session = FakeMechanicalSession('{"product_version":"2026 R1","analyses":[]}')
    launch_calls = []

    def launch_mechanical(**kwargs):
        launch_calls.append(kwargs)
        return session

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=launch_mechanical,
    )
    server = create_mcp_server(session_manager=manager)
    event_loop_thread_id = threading.get_ident()

    async with create_connected_server_and_client_session(
        server,
        raise_exceptions=True,
    ) as client:
        first = await client.call_tool("inspect_mechanical_model", {})
        second = await client.call_tool("inspect_mechanical_model", {})

        assert first.isError is False
        assert first.structuredContent["success"] is True
        assert first.structuredContent["data"] == {
            "product_version": "2026 R1",
            "analyses": [],
        }
        assert second.structuredContent == first.structuredContent
        assert len(launch_calls) == 1
        assert len(session.script_calls) == 2
        assert all(thread_id != event_loop_thread_id for thread_id in session.script_thread_ids)
        assert session.exit_calls == []

    assert session.exit_calls == [{"force": True}]
    assert session.exit_thread_ids[0] != event_loop_thread_id


@pytest.mark.anyio
async def test_concurrent_mechanical_calls_are_serialized_on_the_shared_session() -> None:
    class TrackingSession(FakeMechanicalSession):
        def __init__(self) -> None:
            super().__init__('{"product_version":"2026 R1","analyses":[]}')
            self.active_calls = 0
            self.max_active_calls = 0
            self.state_lock = threading.Lock()

        def run_python_script(self, script, **kwargs):
            with self.state_lock:
                self.active_calls += 1
                self.max_active_calls = max(self.max_active_calls, self.active_calls)
            try:
                time.sleep(0.03)
                return super().run_python_script(script, **kwargs)
            finally:
                with self.state_lock:
                    self.active_calls -= 1

    session = TrackingSession()
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=lambda **_kwargs: session,
    )
    server = create_mcp_server(session_manager=manager)
    results = []

    async with create_connected_server_and_client_session(server) as client:

        async def inspect() -> None:
            results.append(await client.call_tool("inspect_mechanical_model", {}))

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(inspect)
            task_group.start_soon(inspect)

    assert len(results) == 2
    assert all(result.isError is False for result in results)
    assert session.max_active_calls == 1


@pytest.mark.anyio
async def test_inspection_returns_structured_start_error() -> None:
    def launch_mechanical(**_kwargs):
        raise RuntimeError("license unavailable")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=launch_mechanical,
    )
    server = create_mcp_server(session_manager=manager)

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("inspect_mechanical_model", {})

    structured = result.structuredContent
    assert result.isError is True
    assert structured["success"] is False
    assert structured["error"] == "MECHANICAL_SESSION_START_FAILED"
    assert structured["data"]["operation"] == "start"
    assert "license unavailable" in structured["message"]


@pytest.mark.anyio
async def test_inspection_returns_structured_missing_dependency_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ansys.mechanical.core":
            raise ImportError("blocked PyMechanical import")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    server = create_mcp_server(session_config=MechanicalSessionConfig(mode="start"))

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("inspect_mechanical_model", {})

    assert result.isError is True
    assert result.structuredContent["success"] is False
    assert result.structuredContent["error"] == "MECHANICAL_DEPENDENCY_MISSING"


@pytest.mark.anyio
async def test_inspection_mcp_error_payload_remains_json_compatible() -> None:
    class NativeProxy:
        def __str__(self) -> str:
            return "native-proxy"

    session = FakeMechanicalSession(NativeProxy())  # type: ignore[arg-type]
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=lambda **_kwargs: session,
    )
    server = create_mcp_server(session_manager=manager)

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("inspect_mechanical_model", {})

    structured = result.structuredContent
    assert result.isError is True
    assert structured["success"] is False
    assert structured["data"]["raw_result"] == {
        "python_type": "NativeProxy",
        "text": "native-proxy",
    }
    assert json.loads(json.dumps(structured)) == structured


@pytest.mark.anyio
async def test_selection_mcp_roundtrip_connects_to_declared_gui_session() -> None:
    selection_payload = json.dumps(
        {
            "selection": {
                "present": True,
                "native_selection_type": "GeometryEntities",
                "name": None,
                "native_ids": [42],
                "unparsed_ids": [],
                "rich_interface_available": True,
                "entities": [{"native_id": 42, "native_type": "GeoFace"}],
                "element_face_indices": [],
                "unparsed_element_face_indices": [],
            },
            "active_tree_objects": [],
            "model_context": {
                "product_version": "2026 R1",
                "project_name": None,
                "model_name": None,
                "document_id": None,
                "model_id": None,
                "geometry_revision": None,
                "mesh_revision": None,
            },
            "warnings": [],
        }
    )
    session = FakeMechanicalSession(selection_payload)
    connect_calls = []

    def connect_to_mechanical(**kwargs):
        connect_calls.append(kwargs)
        return session

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", batch=False, port=10000),
        connect_to_mechanical=connect_to_mechanical,
    )
    server = create_mcp_server(session_manager=manager)

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("capture_current_selection", {})

    structured = result.structuredContent
    assert result.isError is False
    assert structured["success"] is True
    assert structured["data"]["snapshot"]["entity_type"] == "face"
    assert connect_calls == [{"cleanup_on_exit": False, "port": 10000}]
    assert session.exit_calls == []


@pytest.mark.anyio
async def test_inspection_and_selection_share_one_started_gui_session() -> None:
    selection_payload = json.dumps(
        {
            "selection": {
                "present": False,
                "native_selection_type": None,
                "name": None,
                "native_ids": [],
                "unparsed_ids": [],
                "rich_interface_available": False,
                "entities": [],
                "element_face_indices": [],
                "unparsed_element_face_indices": [],
            },
            "active_tree_objects": [],
            "model_context": {
                "product_version": "2026 R1",
                "project_name": None,
                "model_name": None,
                "document_id": None,
                "model_id": None,
                "geometry_revision": None,
                "mesh_revision": None,
            },
            "warnings": [],
        }
    )

    class RoutingMechanicalSession(FakeMechanicalSession):
        def run_python_script(self, script, **kwargs):
            self.script_calls.append((script, kwargs))
            if "CurrentSelection" in script:
                return selection_payload
            return '{"product_version":"2026 R1","analyses":[]}'

    session = RoutingMechanicalSession("")
    launch_calls = []

    def launch_mechanical(**kwargs):
        launch_calls.append(kwargs)
        return session

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", batch=False, cleanup_on_exit=True),
        launch_mechanical=launch_mechanical,
    )
    server = create_mcp_server(session_manager=manager)

    async with create_connected_server_and_client_session(server) as client:
        inspection = await client.call_tool("inspect_mechanical_model", {})
        selection = await client.call_tool("capture_current_selection", {})

        assert inspection.structuredContent["success"] is True
        assert selection.structuredContent["success"] is True
        assert selection.structuredContent["data"]["snapshot"]["is_empty"] is True
        assert len(launch_calls) == 1
        assert len(session.script_calls) == 2

    assert session.exit_calls == [{"force": True}]


@pytest.mark.anyio
async def test_selection_refuses_headless_session_without_connecting() -> None:
    calls = []

    def connect_to_mechanical(**kwargs):
        calls.append(kwargs)
        return FakeMechanicalSession("{}")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", batch=True),
        connect_to_mechanical=connect_to_mechanical,
    )
    server = create_mcp_server(session_manager=manager)

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("capture_current_selection", {})

    structured = result.structuredContent
    assert result.isError is True
    assert structured["success"] is False
    assert structured["error"] == "MECHANICAL_SELECTION_INTERACTIVE_SESSION_REQUIRED"
    assert structured["data"]["snapshot"]["errors"][0]["code"] == structured["error"]
    assert calls == []


@pytest.mark.anyio
async def test_selection_returns_structured_connection_error() -> None:
    def connect_to_mechanical(**_kwargs):
        raise RuntimeError("connection refused")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", batch=False),
        connect_to_mechanical=connect_to_mechanical,
    )
    server = create_mcp_server(session_manager=manager)

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("capture_current_selection", {})

    structured = result.structuredContent
    assert result.isError is True
    assert structured["success"] is False
    assert structured["error"] == "MECHANICAL_SESSION_CONNECT_FAILED"
    assert "connection refused" in structured["message"]


@pytest.mark.anyio
async def test_selection_does_not_implicitly_start_new_gui_session() -> None:
    calls = []

    def launch_mechanical(**kwargs):
        calls.append(kwargs)
        return FakeMechanicalSession("{}")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", batch=False),
        launch_mechanical=launch_mechanical,
    )
    server = create_mcp_server(session_manager=manager)

    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("capture_current_selection", {})

    structured = result.structuredContent
    assert result.isError is True
    assert structured["success"] is False
    assert structured["error"] == "MECHANICAL_SELECTION_SESSION_NOT_READY"
    assert calls == []
