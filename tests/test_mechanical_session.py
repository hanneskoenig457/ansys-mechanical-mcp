import builtins

import pytest

from ansys_mechanical_mcp.core.errors import AnsysMechanicalMcpError
from ansys_mechanical_mcp.products.mechanical.session import (
    MechanicalSessionConfig,
    MechanicalSessionCleanupError,
    MechanicalSessionError,
    MechanicalSessionManager,
)


class FakeClosableSession:
    def __init__(self, *, fail: bool = False) -> None:
        self.exit_calls = []
        self.fail = fail

    def exit(self, *, force: bool) -> None:
        self.exit_calls.append({"force": force})
        if self.fail:
            raise RuntimeError("shutdown transport failed")


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

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=launch_mechanical,
    )

    assert manager.start_or_connect() is session
    assert manager.start_or_connect() is session
    assert len(calls) == 1


def test_invalid_mode_raises_project_error() -> None:
    with pytest.raises(MechanicalSessionError, match="mode"):
        MechanicalSessionConfig(mode="invalid")  # type: ignore[arg-type]


def test_invalid_port_raises_project_error() -> None:
    with pytest.raises(MechanicalSessionError, match="port"):
        MechanicalSessionConfig(port=0)


def test_invalid_batch_mode_raises_project_error() -> None:
    with pytest.raises(MechanicalSessionError, match="batch"):
        MechanicalSessionConfig(batch="false")  # type: ignore[arg-type]


def test_invalid_cleanup_mode_raises_project_error() -> None:
    with pytest.raises(MechanicalSessionError, match="cleanup_on_exit"):
        MechanicalSessionConfig(cleanup_on_exit="true")  # type: ignore[arg-type]


def test_start_mode_rejects_host() -> None:
    with pytest.raises(MechanicalSessionError, match="host"):
        MechanicalSessionConfig(mode="start", host="mechanical.example.test")


def test_connect_mode_rejects_unused_launch_version() -> None:
    with pytest.raises(MechanicalSessionError, match="launch request"):
        MechanicalSessionConfig(mode="connect", version="261")


def test_cleanup_on_exit_defaults_to_true_when_starting() -> None:
    calls = []

    def launch_mechanical(**kwargs):
        calls.append(kwargs)
        return object()

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=launch_mechanical,
    )

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


def test_cleanup_on_exit_defaults_to_false_for_started_ui_session() -> None:
    config = MechanicalSessionConfig(mode="start", batch=False)

    assert config.owns_session is True
    assert config.interactive is True
    assert config.effective_cleanup_on_exit is False


def test_connect_mode_keeps_interactivity_unknown_until_explicitly_declared() -> None:
    config = MechanicalSessionConfig(mode="connect")

    assert config.effective_batch is None
    assert config.interactive is None

    interactive_config = MechanicalSessionConfig(mode="connect", batch=False)

    assert interactive_config.interactive is True


def test_unconfigured_manager_refuses_to_choose_start_or_connect() -> None:
    manager = MechanicalSessionManager()

    with pytest.raises(MechanicalSessionError, match="not configured"):
        manager.start_or_connect()

    assert manager.config.to_dict()["configured"] is False


def test_session_configuration_is_immutable_after_creation() -> None:
    config = MechanicalSessionConfig(mode="connect")

    with pytest.raises(AttributeError):
        config.cleanup_on_exit = True  # type: ignore[misc]


def test_close_exits_server_started_session_once() -> None:
    session = FakeClosableSession()
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=lambda **_kwargs: session,
    )
    manager.start_or_connect()

    manager.close()
    manager.close()

    assert manager.closed is True
    assert manager.session is None
    assert session.exit_calls == [{"force": True}]


def test_close_leaves_connected_user_session_running_by_default() -> None:
    session = FakeClosableSession()
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect"),
        connect_to_mechanical=lambda **_kwargs: session,
    )
    manager.start_or_connect()

    manager.close()
    manager.close()

    assert manager.closed is True
    assert session.exit_calls == []


def test_close_leaves_started_ui_session_running_without_explicit_force_cleanup() -> None:
    session = FakeClosableSession()
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", batch=False),
        launch_mechanical=lambda **_kwargs: session,
    )
    manager.start_or_connect()

    manager.close()

    assert manager.closed is True
    assert session.exit_calls == []


def test_close_honors_explicit_cleanup_for_connected_session() -> None:
    session = FakeClosableSession()
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", cleanup_on_exit=True),
        connect_to_mechanical=lambda **_kwargs: session,
    )
    manager.start_or_connect()

    manager.close()

    assert session.exit_calls == [{"force": True}]


def test_close_failure_retains_session_and_allows_cleanup_retry() -> None:
    session = FakeClosableSession(fail=True)
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=lambda **_kwargs: session,
    )
    manager.start_or_connect()

    with pytest.raises(MechanicalSessionCleanupError, match="shutdown transport failed"):
        manager.close()

    assert manager.closed is False
    assert manager.session is session
    session.fail = False
    manager.close()
    manager.close()

    assert manager.closed is True
    assert manager.session is None
    assert session.exit_calls == [{"force": True}, {"force": True}]


def test_start_or_connect_rejects_reuse_after_close() -> None:
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=lambda **_kwargs: FakeClosableSession(),
    )
    manager.close()

    with pytest.raises(MechanicalSessionError, match="already closed"):
        manager.start_or_connect()


def test_launch_failure_is_wrapped_in_project_error() -> None:
    def launch_mechanical(**_kwargs):
        raise RuntimeError("license unavailable")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=launch_mechanical,
    )

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

    with pytest.raises(
        MechanicalSessionError, match="Failed to connect.*connection refused"
    ) as exc:
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
    manager = MechanicalSessionManager(MechanicalSessionConfig(mode="start"))

    with pytest.raises(MechanicalSessionError, match="PyMechanical is not installed"):
        manager.start_or_connect()
