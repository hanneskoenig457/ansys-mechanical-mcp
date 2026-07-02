import builtins

import pytest

from ansys_mechanical_mcp.core.errors import AnsysMechanicalMcpError
from ansys_mechanical_mcp.products.mechanical.session import (
    MechanicalSessionConfig,
    MechanicalSessionError,
    MechanicalSessionManager,
)


def test_start_or_connect_starts_mechanical_with_configured_arguments() -> None:
    calls = []
    session = object()

    def launch_mechanical(**kwargs):
        calls.append(kwargs)
        return session

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(
            mode="start",
            version="261",
            batch=False,
            cleanup_on_exit=False,
            port=10001,
        ),
        launch_mechanical=launch_mechanical,
    )

    result = manager.start_or_connect()

    assert result is session
    assert manager.session is session
    assert calls == [
        {
            "allow_input": False,
            "batch": False,
            "cleanup_on_exit": False,
            "start_instance": True,
            "version": "261",
            "port": 10001,
        }
    ]


def test_start_or_connect_connects_to_existing_mechanical_server() -> None:
    calls = []
    session = object()

    def connect_to_mechanical(**kwargs):
        calls.append(kwargs)
        return session

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(
            mode="connect",
            cleanup_on_exit=True,
            host="mechanical.example.test",
            port=10000,
        ),
        connect_to_mechanical=connect_to_mechanical,
    )

    result = manager.start_or_connect()

    assert result is session
    assert manager.session is session
    assert calls == [
        {
            "cleanup_on_exit": True,
            "ip": "mechanical.example.test",
            "port": 10000,
        }
    ]


def test_start_or_connect_returns_existing_session_without_launching_again() -> None:
    calls = []
    session = object()

    def launch_mechanical(**kwargs):
        calls.append(kwargs)
        return session

    manager = MechanicalSessionManager(launch_mechanical=launch_mechanical)

    assert manager.start_or_connect() is session
    assert manager.start_or_connect() is session
    assert len(calls) == 1


def test_invalid_mode_raises_project_error() -> None:
    with pytest.raises(MechanicalSessionError, match="mode"):
        MechanicalSessionConfig(mode="invalid")  # type: ignore[arg-type]


def test_invalid_port_raises_project_error() -> None:
    with pytest.raises(MechanicalSessionError, match="port"):
        MechanicalSessionConfig(port=0)


def test_start_mode_rejects_host() -> None:
    with pytest.raises(MechanicalSessionError, match="host"):
        MechanicalSessionConfig(mode="start", host="mechanical.example.test")


def test_cleanup_on_exit_defaults_to_true_when_starting() -> None:
    calls = []

    def launch_mechanical(**kwargs):
        calls.append(kwargs)
        return object()

    manager = MechanicalSessionManager(launch_mechanical=launch_mechanical)

    manager.start_or_connect()

    assert calls[0]["cleanup_on_exit"] is True


def test_cleanup_on_exit_defaults_to_false_when_connecting() -> None:
    calls = []

    def connect_to_mechanical(**kwargs):
        calls.append(kwargs)
        return object()

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect"),
        connect_to_mechanical=connect_to_mechanical,
    )

    manager.start_or_connect()

    assert calls[0]["cleanup_on_exit"] is False


def test_launch_failure_is_wrapped_in_project_error() -> None:
    def launch_mechanical(**_kwargs):
        raise RuntimeError("license unavailable")

    manager = MechanicalSessionManager(launch_mechanical=launch_mechanical)

    with pytest.raises(MechanicalSessionError, match="Failed to start.*license unavailable") as exc:
        manager.start_or_connect()

    assert isinstance(exc.value, AnsysMechanicalMcpError)
    assert isinstance(exc.value.__cause__, RuntimeError)


def test_connect_failure_is_wrapped_in_project_error() -> None:
    def connect_to_mechanical(**_kwargs):
        raise RuntimeError("connection refused")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect"),
        connect_to_mechanical=connect_to_mechanical,
    )

    with pytest.raises(MechanicalSessionError, match="Failed to connect.*connection refused") as exc:
        manager.start_or_connect()

    assert isinstance(exc.value, AnsysMechanicalMcpError)
    assert isinstance(exc.value.__cause__, RuntimeError)


def test_missing_pymechanical_is_reported_as_project_error(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ansys.mechanical.core":
            raise ImportError("blocked PyMechanical import")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    manager = MechanicalSessionManager()

    with pytest.raises(MechanicalSessionError, match="PyMechanical is not installed"):
        manager.start_or_connect()
