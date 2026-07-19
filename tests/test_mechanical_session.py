import builtins
import json

import pytest

import ansys_mechanical_mcp.products.mechanical.session as session_module
from ansys_mechanical_mcp.core.errors import AnsysMechanicalMcpError
from ansys_mechanical_mcp.products.mechanical.session import (
    MechanicalInsecureTransportOptInRequired,
    MechanicalSessionConfig,
    MechanicalSessionCleanupError,
    MechanicalSessionError,
    MechanicalSessionManager,
    MechanicalTransportCompatibilityError,
    MechanicalTransportPreflightError,
)
from ansys_mechanical_mcp.products.mechanical.transport import MechanicalTransportPreflight


@pytest.fixture(autouse=True)
def deterministic_fake_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep legacy session tests independent from PyMechanical and the host OS."""
    monkeypatch.setattr(session_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        session_module,
        "discover_start_transport",
        lambda _exec_file, _requested_revision, *, system_name: MechanicalTransportPreflight(
            status="supported",
            exact_executable_validated=True,
            detected_revision=261,
            secure_transport_supported=True,
            source="unit_test",
        ),
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
            "host": "127.0.0.1",
            "start_instance": True,
            "transport_mode": "wnua",
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
            "transport_mode": "mtls",
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


@pytest.mark.parametrize("version", ["foo", "25.1", "", "2610", "²51"])
def test_start_mode_requires_three_digit_revision(version: str) -> None:
    with pytest.raises(MechanicalSessionError, match="three-digit|must not be empty"):
        MechanicalSessionConfig(mode="start", version=version)


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


def test_explicit_insecure_transport_starts_confirmed_legacy_service_pack_once() -> None:
    calls = []
    session = object()
    preflight = MechanicalTransportPreflight(
        status="unsupported",
        executable_path=r"C:\Program Files\ANSYS Inc\v251\aisol\bin\winx64\AnsysWBU.exe",
        exact_executable_validated=True,
        detected_revision=251,
        secure_transport_supported=False,
        required_secure_service_pack="SP04",
        source="unit_test",
    )

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(
            mode="start",
            version="251",
            port=10000,
            transport_mode="insecure",
        ),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or session,
        transport_preflight=lambda _exec_file, _requested_revision: preflight,
        system_name="Windows",
    )

    assert manager.start_or_connect() is session
    assert manager.start_or_connect() is session

    assert len(calls) == 1
    assert calls[0]["port"] == 10000
    assert calls[0]["transport_mode"] == "insecure"
    assert calls[0]["exec_file"] == preflight.executable_path
    context = manager.session_context
    assert context["transport"]["effective_mode"] == "insecure"
    assert context["transport"]["selected_mode"] == "insecure"
    assert context["transport"]["automatic_insecure_selection"] is False
    assert context["transport"]["connection_scope"] == (
        "local_start_legacy_listener_unverified"
    )
    assert context["transport"]["listener_binding"] == "unverified_legacy_default"
    assert context["transport"]["listener_binding_verified"] is False
    assert context["transport"]["selected_host_is_binding_proof"] is False
    assert {warning["code"] for warning in context["transport"]["warnings"]} == {
        "MECHANICAL_TRANSPORT_INSECURE",
        "MECHANICAL_LEGACY_LISTENER_BINDING_UNVERIFIED",
    }
    binding_warning = next(
        warning
        for warning in context["transport"]["warnings"]
        if warning["code"] == "MECHANICAL_LEGACY_LISTENER_BINDING_UNVERIFIED"
    )
    assert "0.0.0.0 or ::" in binding_warning["message"]
    assert "do not prove the listener binding" in binding_warning["message"]
    assert binding_warning["details"]["possible_listener_addresses"] == ["0.0.0.0", "::"]
    assert binding_warning["details"]["listener_binding_verified"] is False
    assert context["transport"]["fallback_attempted"] is False
    assert context["establishment"] == {
        "status": "established",
        "attempt_count": 1,
        "start_retry_blocked": False,
    }
    assert json.loads(json.dumps(context, allow_nan=False)) == context


def test_auto_legacy_transport_requires_explicit_opt_in_without_launch() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", version="251", port=10000),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        transport_preflight=lambda _exec_file, _requested_revision: (
            MechanicalTransportPreflight(
                status="unsupported",
                detected_revision=251,
                secure_transport_supported=False,
                required_secure_service_pack="SP04",
                source="unit_test",
            )
        ),
        system_name="Windows",
    )

    for _ in range(2):
        with pytest.raises(MechanicalInsecureTransportOptInRequired, match="explicit"):
            manager.start_or_connect()

    assert calls == []
    context = manager.session_context
    assert context["transport"]["selected_mode"] is None
    assert context["transport"]["effective_mode"] is None
    assert context["establishment"] == {
        "status": "failed",
        "attempt_count": 0,
        "start_retry_blocked": True,
    }


def test_auto_transport_keeps_secure_mode_for_compatible_installation() -> None:
    calls = []
    preflight = MechanicalTransportPreflight(
        status="supported",
        executable_path=r"C:\Program Files\ANSYS Inc\v261\aisol\bin\winx64\AnsysWBU.exe",
        exact_executable_validated=True,
        detected_revision=261,
        secure_transport_supported=True,
        source="unit_test",
    )
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        transport_preflight=lambda _exec_file, _requested_revision: preflight,
        system_name="Windows",
    )

    manager.start_or_connect()

    assert calls[0]["transport_mode"] == "wnua"
    assert manager.session_context["transport"]["secure"] is True


def test_linux_mtls_start_uses_certificate_compatible_localhost() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        transport_preflight=lambda _exec_file, _requested_revision: MechanicalTransportPreflight(
            status="supported",
            exact_executable_validated=True,
            detected_revision=261,
            secure_transport_supported=True,
            source="unit_test",
        ),
        system_name="Linux",
    )

    manager.start_or_connect()

    assert calls[0]["transport_mode"] == "mtls"
    assert calls[0]["host"] == "localhost"


def test_auto_transport_unknown_preflight_does_not_launch_or_downgrade() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        transport_preflight=lambda _exec_file, _requested_revision: MechanicalTransportPreflight(
            status="unknown",
            exact_executable_validated=True,
            message="builddate.txt missing",
            source="unit_test",
        ),
        system_name="Windows",
    )

    with pytest.raises(MechanicalTransportPreflightError, match="No insecure downgrade"):
        manager.start_or_connect()
    with pytest.raises(MechanicalTransportPreflightError):
        manager.start_or_connect()

    assert calls == []
    assert manager.session_context["establishment"] == {
        "status": "failed",
        "attempt_count": 0,
        "start_retry_blocked": True,
    }


def test_incompatible_preflight_is_latched_without_launch() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", transport_mode="insecure"),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        transport_preflight=lambda _exec_file, _requested_revision: (
            MechanicalTransportPreflight(
                status="incompatible",
                detected_revision=231,
                source="unit_test",
                message="PyMechanical requires revision 242 or later.",
            )
        ),
        system_name="Windows",
    )

    for _ in range(2):
        with pytest.raises(MechanicalTransportCompatibilityError, match="242 or later"):
            manager.start_or_connect()

    assert calls == []
    assert manager.session_context["establishment"]["start_retry_blocked"] is True


def test_explicit_secure_transport_rejects_confirmed_incompatible_release() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", transport_mode="wnua"),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        transport_preflight=lambda _exec_file, _requested_revision: MechanicalTransportPreflight(
            status="unsupported",
            detected_revision=251,
            secure_transport_supported=False,
            required_secure_service_pack="SP04",
            source="unit_test",
        ),
        system_name="Windows",
    )

    with pytest.raises(MechanicalTransportCompatibilityError, match="SP04"):
        manager.start_or_connect()

    assert calls == []


def test_start_failure_is_latched_and_never_launches_a_second_process() -> None:
    calls = []

    def launch_mechanical(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("license unavailable")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=launch_mechanical,
    )

    with pytest.raises(MechanicalSessionError, match="license unavailable"):
        manager.start_or_connect()
    with pytest.raises(MechanicalSessionError, match="license unavailable"):
        manager.start_or_connect()

    assert len(calls) == 1
    assert manager.session_context["establishment"]["start_retry_blocked"] is True


def test_connect_failure_can_retry_without_starting_a_process() -> None:
    calls = []

    def connect_to_mechanical(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("connection refused")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", host="127.0.0.1"),
        connect_to_mechanical=connect_to_mechanical,
        system_name="Windows",
    )

    for _ in range(2):
        with pytest.raises(MechanicalSessionError, match="connection refused"):
            manager.start_or_connect()

    assert len(calls) == 2
    assert manager.session_context["establishment"]["start_retry_blocked"] is False
    assert manager.session_context["establishment"]["status"] == "failed"
    assert manager.session_context["transport"]["retry_performed"] is True


def test_remote_auto_connect_uses_mtls_without_insecure_fallback() -> None:
    calls = []
    session = object()
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(
            mode="connect",
            host="mechanical.example.test",
            certs_dir="C:/certs",
        ),
        connect_to_mechanical=lambda **kwargs: calls.append(kwargs) or session,
        system_name="Windows",
    )

    assert manager.start_or_connect() is session

    assert calls == [
        {
            "cleanup_on_exit": False,
            "transport_mode": "mtls",
            "ip": "mechanical.example.test",
            "certs_dir": "C:/certs",
        }
    ]
    context = manager.session_context
    assert context["transport"]["connection_scope"] == "remote_connect"
    assert context["transport"]["listener_binding"] == "not_applicable_connect"
    assert context["transport"]["fallback_attempted"] is False


def test_explicit_insecure_unknown_preflight_uses_neutral_binding_diagnostic() -> None:
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", transport_mode="insecure"),
        launch_mechanical=lambda **_kwargs: object(),
        transport_preflight=lambda _exec_file, _requested_revision: (
            MechanicalTransportPreflight(
                status="unknown",
                executable_path=r"C:\Ansys\v251\AnsysWBU.exe",
                exact_executable_validated=True,
                detected_revision=251,
                source="unit_test",
                message="build metadata has no explicit SP marker",
            )
        ),
        system_name="Windows",
    )

    manager.start_or_connect()

    transport = manager.session_context["transport"]
    assert transport["connection_scope"] == "local_start_listener_binding_support_unknown"
    assert transport["listener_binding"] == "support_unknown"
    assert transport["listener_binding_verified"] is False
    assert transport["selected_host"] == "127.0.0.1"
    assert transport["effective_host"] == "127.0.0.1"
    assert transport["selected_host_is_binding_proof"] is False
    assert {warning["code"] for warning in transport["warnings"]} == {
        "MECHANICAL_TRANSPORT_INSECURE",
        "MECHANICAL_LISTENER_BINDING_SUPPORT_UNKNOWN",
    }
    warning = next(
        warning
        for warning in transport["warnings"]
        if warning["code"] == "MECHANICAL_LISTENER_BINDING_SUPPORT_UNKNOWN"
    )
    assert "0.0.0.0 or ::" in warning["message"]
    assert "other network interfaces" in warning["message"]
    assert "unencrypted and unauthenticated" in warning["message"]
    assert "selected_host and effective_host" in warning["message"]
    assert "do not prove the listener binding" in warning["message"]
    assert "After every start" in warning["message"]
    assert "trusted or isolated" in warning["message"]
    assert warning["details"]["required_action"] == (
        "verify_listener_address_and_owning_process_after_every_start"
    )
    assert json.loads(json.dumps(transport, allow_nan=False)) == transport


def test_explicit_transport_cannot_fall_through_to_implicit_pypim_launch() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", transport_mode="insecure"),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        transport_preflight=lambda _exec_file, _requested_revision: (
            MechanicalTransportPreflight(
                status="unknown",
                source="unit_test",
                message="no local executable",
            )
        ),
        system_name="Windows",
    )

    with pytest.raises(MechanicalTransportPreflightError, match="PyPIM"):
        manager.start_or_connect()

    assert calls == []


def test_explicit_transport_cannot_bypass_unknown_executable_revision() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", transport_mode="insecure"),
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        transport_preflight=lambda _exec_file, _requested_revision: (
            MechanicalTransportPreflight(
                status="unknown",
                executable_path=r"C:\Ansys\unknown\AnsysWBU.exe",
                exact_executable_validated=True,
                detected_revision=None,
                source="unit_test",
                message="revision detection failed",
            )
        ),
        system_name="Windows",
    )

    with pytest.raises(MechanicalTransportPreflightError, match="detected revision"):
        manager.start_or_connect()

    assert calls == []


def test_remote_insecure_connect_requires_explicit_acknowledgement() -> None:
    with pytest.raises(MechanicalSessionError, match="explicit acknowledgement"):
        MechanicalSessionConfig(
            mode="connect",
            host="mechanical.example.test",
            transport_mode="insecure",
        )

    config = MechanicalSessionConfig(
        mode="connect",
        host="mechanical.example.test",
        transport_mode="insecure",
        allow_insecure_remote=True,
    )

    assert config.to_dict()["transport"]["allow_insecure_remote"] is True

    calls = []
    manager = MechanicalSessionManager(
        config,
        connect_to_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        system_name="Windows",
    )
    manager.start_or_connect()

    assert calls[0]["transport_mode"] == "insecure"
    transport = manager.session_context["transport"]
    assert transport["secure"] is False
    assert transport["warnings"][0]["code"] == "MECHANICAL_TRANSPORT_INSECURE"


@pytest.mark.parametrize("host", ["mechanical.example.test", "::1", "127.5.6.7"])
def test_unsupported_wnua_endpoint_is_rejected_before_connection(host: str) -> None:
    with pytest.raises(MechanicalSessionError, match="localhost.*127.0.0.1"):
        MechanicalSessionConfig(
            mode="connect",
            host=host,
            transport_mode="wnua",
        )


def test_windows_auto_connect_rejects_loopback_spelling_unsupported_by_wnua() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", host="::1"),
        connect_to_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        system_name="Windows",
    )

    with pytest.raises(MechanicalSessionError, match="Automatic WNUA"):
        manager.start_or_connect()

    assert calls == []


@pytest.mark.parametrize("mode", ["start", "connect"])
def test_wnua_is_rejected_on_linux_before_factory_call(mode: str) -> None:
    calls = []
    config = MechanicalSessionConfig(mode=mode, transport_mode="wnua")  # type: ignore[arg-type]
    manager = MechanicalSessionManager(
        config,
        launch_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        connect_to_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        system_name="Linux",
    )

    with pytest.raises(MechanicalSessionError, match="Windows only"):
        manager.start_or_connect()

    assert calls == []


def test_wnua_connect_canonicalizes_accepted_localhost_spelling() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", host=" LOCALHOST ", transport_mode="wnua"),
        connect_to_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        system_name="Windows",
    )

    manager.start_or_connect()

    assert calls[0]["ip"] == "127.0.0.1"


def test_connect_without_host_pins_loopback_instead_of_using_environment_default() -> None:
    calls = []
    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="connect", transport_mode="insecure"),
        connect_to_mechanical=lambda **kwargs: calls.append(kwargs) or object(),
        system_name="Windows",
    )

    manager.start_or_connect()

    assert calls[0]["ip"] == "127.0.0.1"
    assert manager.session_context["transport"]["effective_host"] == "127.0.0.1"


def test_similar_start_error_is_not_misclassified_as_transport_compatibility() -> None:
    calls = []

    def launch_mechanical(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("secure transport certificate unavailable due to license setup")

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start"),
        launch_mechanical=launch_mechanical,
    )

    with pytest.raises(MechanicalSessionError, match="Failed to start") as exc:
        manager.start_or_connect()

    assert not isinstance(exc.value, MechanicalTransportCompatibilityError)
    assert len(calls) == 1


def test_exact_pymechanical_preprocess_error_is_classified_without_retry() -> None:
    calls = []

    def launch_mechanical(**kwargs):
        calls.append(kwargs)
        raise RuntimeError(
            "Mechanical version 251 does not support secure transport modes. "
            "Update to Service Pack SP04 or later for secure gRPC support."
        )

    manager = MechanicalSessionManager(
        MechanicalSessionConfig(mode="start", transport_mode="wnua"),
        launch_mechanical=launch_mechanical,
        transport_preflight=lambda _exec_file, _requested_revision: MechanicalTransportPreflight(
            status="unknown",
            exact_executable_validated=True,
            detected_revision=251,
            source="unit_test",
        ),
        system_name="Windows",
    )

    with pytest.raises(MechanicalTransportCompatibilityError, match="SP04"):
        manager.start_or_connect()
    with pytest.raises(MechanicalTransportCompatibilityError):
        manager.start_or_connect()

    assert len(calls) == 1
