"""PyMechanical session management."""

import platform
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any, Literal

from ansys_mechanical_mcp.core.errors import AnsysMechanicalMcpError
from ansys_mechanical_mcp.products.mechanical.transport import (
    MechanicalTransportMode,
    MechanicalTransportPreflight,
    discover_start_transport,
    is_loopback_host,
    is_wnua_loopback_host,
    platform_secure_transport,
    transport_security,
)


MechanicalSessionMode = Literal["start", "connect"]
PyMechanicalFactory = Callable[..., Any]
MechanicalTransportPreflightFactory = Callable[
    [str | None, int | None],
    MechanicalTransportPreflight,
]


class MechanicalSessionError(AnsysMechanicalMcpError):
    """Raised when a PyMechanical session cannot be started or connected."""


class MechanicalDependencyError(MechanicalSessionError):
    """Raised when the optional PyMechanical dependency is unavailable."""


class MechanicalSessionConfigurationError(MechanicalSessionError):
    """Raised when no explicit Mechanical start/connect mode was selected."""


class MechanicalSessionStartError(MechanicalSessionError):
    """Raised when a new Mechanical session cannot be started."""


class MechanicalSessionConnectError(MechanicalSessionError):
    """Raised when an existing Mechanical session cannot be reached."""


class MechanicalTransportConfigurationError(MechanicalSessionError):
    """Raised when a transport choice violates the connection safety policy."""


class MechanicalInsecureTransportOptInRequired(MechanicalTransportConfigurationError):
    """Raised when legacy local insecure transport requires an explicit choice."""


class MechanicalTransportPreflightError(MechanicalSessionError):
    """Raised when automatic transport selection lacks reliable local evidence."""


class MechanicalTransportCompatibilityError(MechanicalSessionError):
    """Raised when the selected executable/release cannot satisfy the start request."""


class MechanicalSessionCleanupError(MechanicalSessionError):
    """Raised when an owned Mechanical session cannot be closed cleanly."""


@dataclass(slots=True, frozen=True)
class MechanicalSessionConfig:
    """Configuration for a Mechanical session."""

    mode: MechanicalSessionMode | None = None
    version: str | None = None
    batch: bool | None = None
    cleanup_on_exit: bool | None = None
    host: str | None = None
    port: int | None = None
    transport_mode: MechanicalTransportMode = "auto"
    certs_dir: str | None = None
    allow_insecure_remote: bool = False
    exec_file: str | None = None

    def __post_init__(self) -> None:
        """Validate user-facing session configuration."""
        if self.mode not in (None, "start", "connect"):
            msg = "Mechanical session mode must be null, 'start', or 'connect'."
            raise MechanicalSessionError(msg)

        if self.batch is not None and not isinstance(self.batch, bool):
            msg = "Mechanical session batch mode must be a boolean or null."
            raise MechanicalSessionError(msg)

        if self.cleanup_on_exit is not None and not isinstance(self.cleanup_on_exit, bool):
            msg = "Mechanical cleanup_on_exit must be a boolean or null."
            raise MechanicalSessionError(msg)

        if self.transport_mode not in ("auto", "insecure", "mtls", "wnua"):
            msg = "Mechanical transport mode must be 'auto', 'insecure', 'mtls', or 'wnua'."
            raise MechanicalSessionError(msg)

        if not isinstance(self.allow_insecure_remote, bool):
            msg = "Mechanical allow_insecure_remote must be a boolean."
            raise MechanicalSessionError(msg)

        if self.port is not None and (
            isinstance(self.port, bool)
            or not isinstance(self.port, int)
            or not 1 <= self.port <= 65535
        ):
            msg = "Mechanical session port must be between 1 and 65535."
            raise MechanicalSessionError(msg)

        if self.mode != "connect" and self.host is not None:
            msg = "Mechanical session host is only valid when mode is 'connect'."
            raise MechanicalSessionError(msg)

        if self.host is not None and (not isinstance(self.host, str) or not self.host.strip()):
            msg = "Mechanical session host must not be empty."
            raise MechanicalSessionError(msg)

        if self.version is not None and (
            not isinstance(self.version, str) or not self.version.strip()
        ):
            msg = "Mechanical session version must not be empty."
            raise MechanicalSessionError(msg)

        if self.version is not None:
            revision = self.version.strip()
            if len(revision) != 3 or any(character not in "0123456789" for character in revision):
                msg = (
                    "Mechanical session version must be a three-digit ASCII revision, "
                    "for example '251'."
                )
                raise MechanicalSessionError(msg)
            object.__setattr__(self, "version", revision)

        if self.certs_dir is not None and (
            not isinstance(self.certs_dir, str) or not self.certs_dir.strip()
        ):
            msg = "Mechanical certificate directory must not be empty."
            raise MechanicalSessionError(msg)

        if self.exec_file is not None and (
            not isinstance(self.exec_file, str) or not self.exec_file.strip()
        ):
            msg = "Mechanical executable path must not be empty."
            raise MechanicalSessionError(msg)

        if self.mode == "connect" and self.version is not None:
            msg = (
                "Mechanical session version is a launch request and is only valid when mode "
                "is 'start'; inspect the connected product version instead."
            )
            raise MechanicalSessionError(msg)

        if self.mode != "start" and self.exec_file is not None:
            msg = "Mechanical executable path is only valid when mode is 'start'."
            raise MechanicalSessionError(msg)

        if self.transport_mode not in ("auto", "mtls") and self.certs_dir is not None:
            msg = "Mechanical certificate directory is only valid for 'auto' or 'mtls' transport."
            raise MechanicalTransportConfigurationError(msg)

        remote_connect = self.mode == "connect" and not is_loopback_host(self.host)
        if (
            self.mode == "connect"
            and self.transport_mode == "wnua"
            and not is_wnua_loopback_host(self.host)
        ):
            msg = (
                "WNUA connections require the exact PyMechanical-supported endpoint "
                "'localhost' or '127.0.0.1'."
            )
            raise MechanicalTransportConfigurationError(msg)

        if remote_connect and self.transport_mode == "insecure" and not self.allow_insecure_remote:
            msg = (
                "Insecure remote Mechanical connections require explicit acknowledgement with "
                "allow_insecure_remote=True."
            )
            raise MechanicalTransportConfigurationError(msg)

        if self.allow_insecure_remote and not (
            remote_connect and self.transport_mode == "insecure"
        ):
            msg = (
                "allow_insecure_remote is only valid for an explicitly insecure, non-loopback "
                "Mechanical connection."
            )
            raise MechanicalTransportConfigurationError(msg)

    @property
    def effective_cleanup_on_exit(self) -> bool:
        """Return the cleanup behavior for the configured session mode."""
        if self.cleanup_on_exit is not None:
            return self.cleanup_on_exit
        # A manager-owned headless process is safe to close automatically.
        # Interactive UI sessions may contain unsaved user edits, so force-close
        # must be an explicit operator decision.
        return self.mode == "start" and self.effective_batch is True

    @property
    def effective_batch(self) -> bool | None:
        """Return the effective batch setting.

        Starting defaults to PyMechanical's documented batch mode. For a
        connected instance, ``None`` deliberately means that GUI capability is
        unknown until the operator declares it explicitly.
        """
        if self.batch is not None:
            return self.batch
        if self.mode == "start":
            return True
        return None

    @property
    def interactive(self) -> bool | None:
        """Return whether the configured session is suitable for GUI selection."""
        effective_batch = self.effective_batch
        if effective_batch is None:
            return None
        return not effective_batch

    @property
    def owns_session(self) -> bool:
        """Return whether the manager starts, and therefore owns, the session."""
        return self.mode == "start"

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible session configuration and ownership metadata."""
        return {
            "configured": self.mode is not None,
            "mode": self.mode,
            "host": self.host,
            "port": self.port,
            "requested_version": self.version,
            "batch": self.effective_batch,
            "interactive": self.interactive,
            "cleanup_on_exit": self.effective_cleanup_on_exit,
            "owns_session": self.owns_session,
            "requested_executable": self.exec_file,
            "transport": {
                "policy": self.transport_mode,
                "requested_mode": (
                    None if self.transport_mode == "auto" else self.transport_mode
                ),
                "certs_dir": self.certs_dir,
                "allow_insecure_remote": self.allow_insecure_remote,
            },
        }


class MechanicalSessionManager:
    """Manage a PyMechanical session.

    PyMechanical is imported lazily so unit tests and environment checks do not
    require an Ansys installation. Tests can inject fake callables for the launch
    and connect operations.
    """

    def __init__(
        self,
        config: MechanicalSessionConfig | None = None,
        *,
        launch_mechanical: PyMechanicalFactory | None = None,
        connect_to_mechanical: PyMechanicalFactory | None = None,
        transport_preflight: MechanicalTransportPreflightFactory | None = None,
        system_name: str | None = None,
    ) -> None:
        self.config = config or MechanicalSessionConfig()
        self._session = None
        self._launch_mechanical = launch_mechanical
        self._connect_to_mechanical = connect_to_mechanical
        self._transport_preflight_factory = transport_preflight
        self._system_name = system_name or platform.system()
        self._transport_preflight: MechanicalTransportPreflight | None = None
        self._selected_transport: str | None = None
        self._effective_transport: str | None = None
        self._transport_selection_reason: str | None = None
        self._connection_scope = self._configured_connection_scope()
        self._selected_host: str | None = None
        self._effective_host: str | None = None
        self._establishment_attempts = 0
        self._establishment_failed = False
        self._start_error: MechanicalSessionError | None = None
        self._closed = False
        self._lock = RLock()

    @property
    def session(self):
        """Return the underlying PyMechanical session, if available."""
        return self._session

    @property
    def closed(self) -> bool:
        """Return whether the manager has completed its cleanup path."""
        return self._closed

    @property
    def session_context(self) -> dict[str, Any]:
        """Return configured and runtime session facts as a JSON-compatible mapping."""
        context = self.config.to_dict()
        transport = context["transport"]
        selected_secure, selected_security = transport_security(self._selected_transport)
        secure, security = transport_security(self._effective_transport)
        warnings = []
        if self._selected_transport == "insecure":
            warnings.append(
                {
                    "code": "MECHANICAL_TRANSPORT_INSECURE",
                    "message": (
                        "The selected Mechanical gRPC transport is unencrypted and "
                        "unauthenticated."
                    ),
                }
            )
        binding_preflight_status = (
            self._transport_preflight.status
            if self._transport_preflight is not None
            else None
        )
        binding_unverified = (
            self.config.mode == "start"
            and self._selected_transport == "insecure"
            and binding_preflight_status in ("unsupported", "unknown")
        )
        if binding_unverified:
            confirmed_legacy = binding_preflight_status == "unsupported"
            warnings.append(
                {
                    "code": (
                        "MECHANICAL_LEGACY_LISTENER_BINDING_UNVERIFIED"
                        if confirmed_legacy
                        else "MECHANICAL_LISTENER_BINDING_SUPPORT_UNKNOWN"
                    ),
                    "message": (
                        "This confirmed legacy service pack does not support the host-binding "
                        "argument. Verify the actual insecure listener with an operating-system "
                        "query."
                        if confirmed_legacy
                        else (
                            "Host-binding support could not be determined for this Mechanical "
                            "executable. Verify the actual insecure listener with an "
                            "operating-system query."
                        )
                    ),
                }
            )
        transport.update(
            {
                "selected_mode": self._selected_transport,
                "effective_mode": self._effective_transport,
                "selected_secure": selected_secure,
                "selected_security": selected_security,
                "secure": secure,
                "security": security,
                "connection_scope": self._connection_scope,
                "selected_host": self._selected_host,
                "effective_host": self._effective_host,
                "listener_binding": (
                    "not_applicable_connect"
                    if self.config.mode == "connect"
                    else "unverified_legacy_default"
                    if binding_preflight_status == "unsupported" and binding_unverified
                    else "support_unknown"
                    if binding_preflight_status == "unknown" and binding_unverified
                    else "requested_loopback"
                    if self._selected_host is not None and is_loopback_host(self._selected_host)
                    else "remote"
                    if self._selected_host is not None
                    else "not_selected"
                ),
                "selection_reason": self._transport_selection_reason,
                "automatic": self.config.transport_mode == "auto",
                "automatic_insecure_selection": (
                    self.config.transport_mode == "auto"
                    and self._selected_transport == "insecure"
                ),
                "fallback_attempted": False,
                "retry_performed": self._establishment_attempts > 1,
                "preflight": (
                    self._transport_preflight.to_dict()
                    if self._transport_preflight is not None
                    else MechanicalTransportPreflight(status="not_run").to_dict()
                ),
                "warnings": warnings,
            }
        )
        context["establishment"] = {
            "status": (
                "established"
                if self._session is not None
                else "failed"
                if self._establishment_failed
                else "not_started"
            ),
            "attempt_count": self._establishment_attempts,
            "start_retry_blocked": self._start_error is not None,
        }
        return context

    def start_or_connect(self):
        """Start or connect to Mechanical and return the PyMechanical session."""
        with self._lock:
            if self._closed:
                msg = "Mechanical session manager is already closed."
                raise MechanicalSessionError(msg)

            if self.config.mode is None:
                msg = (
                    "Mechanical session mode is not configured. Explicitly choose "
                    "'start' or 'connect' before using a Mechanical tool."
                )
                raise MechanicalSessionConfigurationError(msg)

            if self._session is not None:
                return self._session

            if self.config.mode == "start" and self._start_error is not None:
                raise self._start_error

            try:
                if self.config.mode == "start":
                    self._session = self._start()
                else:
                    self._session = self._connect()
                if self._session is None:
                    msg = "PyMechanical did not return a Mechanical session."
                    raise MechanicalSessionError(msg)
            except MechanicalSessionError as exc:
                self._establishment_failed = True
                if self.config.mode == "start":
                    # A failure after PyMechanical creates a process can leave it
                    # running. Immutable configuration plus a sticky error prevents
                    # a second inspection from silently starting another process.
                    self._start_error = exc
                raise

            self._establishment_failed = False
            return self._session

    def close(self) -> None:
        """Close an eligible Mechanical session exactly once.

        A server-started headless session is closed by default. A started UI or
        connected session is left running by default and is only force-closed
        when the operator explicitly sets ``cleanup_on_exit=True``.
        """
        with self._lock:
            if self._closed:
                return

            session = self._session
            if session is None or not self.config.effective_cleanup_on_exit:
                self._session = None
                self._closed = True
                return

            exit_mechanical = getattr(session, "exit", None)
            if not callable(exit_mechanical):
                msg = "Mechanical session must provide a callable 'exit' method for cleanup."
                raise MechanicalSessionCleanupError(msg)

            try:
                exit_mechanical(force=True)
            except Exception as exc:
                msg = f"Failed to close Ansys Mechanical cleanly: {exc}"
                raise MechanicalSessionCleanupError(msg) from exc

            self._session = None
            self._closed = True

    def _start(self):
        launch_mechanical = self._resolve_launch_mechanical()
        effective_transport, exec_file = self._select_start_transport()
        start_host = "localhost" if effective_transport == "mtls" else "127.0.0.1"
        self._selected_host = start_host
        kwargs: dict[str, Any] = {
            "allow_input": False,
            "batch": self.config.effective_batch,
            "cleanup_on_exit": self.config.effective_cleanup_on_exit,
            "host": start_host,
            "start_instance": True,
            "transport_mode": effective_transport,
        }
        if self.config.version is not None:
            kwargs["version"] = self.config.version
        if self.config.port is not None:
            kwargs["port"] = self.config.port
        if exec_file is not None:
            kwargs["exec_file"] = exec_file
        if effective_transport == "mtls" and self.config.certs_dir is not None:
            kwargs["certs_dir"] = self.config.certs_dir

        self._establishment_attempts += 1
        try:
            session = launch_mechanical(**kwargs)
        except Exception as exc:
            if _is_secure_transport_compatibility_error(exc):
                msg = (
                    "The selected secure Mechanical transport is incompatible with the "
                    f"installed release or service pack: {exc}"
                )
                raise MechanicalTransportCompatibilityError(msg) from exc
            msg = (
                "Failed to start Ansys Mechanical with PyMechanical "
                f"(version={self.config.version!r}, batch={self.config.effective_batch!r}, "
                f"host={start_host!r}, port={self.config.port!r}, "
                f"transport={effective_transport!r}): {exc}"
            )
            raise MechanicalSessionStartError(msg) from exc
        if session is not None:
            self._effective_transport = effective_transport
            self._effective_host = start_host
        return session

    def _connect(self):
        connect_to_mechanical = self._resolve_connect_to_mechanical()
        effective_transport = self._select_connect_transport()
        connect_host = (
            "127.0.0.1"
            if effective_transport == "wnua"
            else self.config.host
            or ("localhost" if effective_transport == "mtls" else "127.0.0.1")
        )
        self._selected_host = connect_host
        kwargs: dict[str, Any] = {
            "cleanup_on_exit": self.config.effective_cleanup_on_exit,
            "ip": connect_host,
            "transport_mode": effective_transport,
        }
        if self.config.port is not None:
            kwargs["port"] = self.config.port
        if effective_transport == "mtls" and self.config.certs_dir is not None:
            kwargs["certs_dir"] = self.config.certs_dir

        self._establishment_attempts += 1
        try:
            session = connect_to_mechanical(**kwargs)
        except Exception as exc:
            msg = (
                "Failed to connect to Ansys Mechanical with PyMechanical "
                f"(host={connect_host!r}, port={self.config.port!r}, "
                f"transport={effective_transport!r}): {exc}"
            )
            raise MechanicalSessionConnectError(msg) from exc
        if session is not None:
            self._effective_transport = effective_transport
            self._effective_host = connect_host
        return session

    def _select_start_transport(self) -> tuple[str, str | None]:
        if (
            self.config.transport_mode == "wnua"
            and self._system_name.strip().lower() != "windows"
        ):
            msg = "WNUA Mechanical transport is available on Windows only."
            raise MechanicalTransportConfigurationError(msg)

        if self._transport_preflight_factory is None:
            preflight = discover_start_transport(
                self.config.exec_file,
                int(self.config.version) if self.config.version is not None else None,
                system_name=self._system_name,
            )
        else:
            preflight = self._transport_preflight_factory(
                self.config.exec_file,
                int(self.config.version) if self.config.version is not None else None,
            )
        self._transport_preflight = preflight

        requested = self.config.transport_mode
        if preflight.status == "incompatible":
            msg = f"{preflight.message} No Mechanical process was started."
            raise MechanicalTransportCompatibilityError(msg)

        if requested == "auto":
            if preflight.status == "unsupported":
                self._connection_scope = "local_start_legacy_listener_unverified"
                self._transport_selection_reason = (
                    "local_legacy_insecure_requires_explicit_opt_in"
                )
                msg = (
                    "The selected local Mechanical release requires insecure gRPC, but its "
                    "legacy listener binding cannot be verified before launch. Auto mode did "
                    "not start a process. If this local risk is acceptable, persist the "
                    "explicit transport choice 'insecure' and verify the listener binding "
                    "with an operating-system query after the one launch attempt."
                )
                raise MechanicalInsecureTransportOptInRequired(msg)
            elif preflight.status == "supported":
                try:
                    effective = platform_secure_transport(self._system_name)
                except ValueError as exc:
                    raise MechanicalTransportConfigurationError(str(exc)) from exc
                reason = "local_secure_transport_supported"
            else:
                msg = (
                    "Automatic Mechanical transport selection requires a resolved executable, "
                    "revision, and service-pack compatibility result. No insecure downgrade or "
                    f"start was attempted. Preflight: {preflight.message}"
                )
                raise MechanicalTransportPreflightError(msg)
        else:
            effective = requested
            reason = "explicit_transport"
            if effective in ("mtls", "wnua") and preflight.status == "unsupported":
                requirement = preflight.required_secure_service_pack or "a newer release"
                msg = (
                    f"Mechanical revision {preflight.detected_revision} does not support "
                    f"transport {effective!r}; secure transport requires {requirement}. "
                    "No Mechanical process was started."
                )
                raise MechanicalTransportCompatibilityError(msg)

        if (
            not preflight.exact_executable_validated
            or preflight.detected_revision is None
        ):
            msg = (
                "Starting a local Mechanical process requires a validated exact executable "
                "path and detected revision. PyPIM or implicit remote launch is outside this "
                f"session mode. No process was started. Preflight: {preflight.message}"
            )
            raise MechanicalTransportPreflightError(msg)

        self._selected_transport = effective
        self._transport_selection_reason = reason
        self._connection_scope = (
            "local_start_legacy_listener_unverified"
            if preflight.status == "unsupported" and effective == "insecure"
            else "local_start_listener_binding_support_unknown"
            if preflight.status == "unknown" and effective == "insecure"
            else "local_start_loopback"
        )
        return effective, preflight.executable_path or self.config.exec_file

    def _select_connect_transport(self) -> str:
        if (
            self.config.transport_mode == "wnua"
            and self._system_name.strip().lower() != "windows"
        ):
            msg = "WNUA Mechanical transport is available on Windows only."
            raise MechanicalTransportConfigurationError(msg)

        loopback = is_loopback_host(self.config.host)
        if self.config.transport_mode == "auto":
            if loopback:
                try:
                    effective = platform_secure_transport(self._system_name)
                except ValueError as exc:
                    raise MechanicalTransportConfigurationError(str(exc)) from exc
                if effective == "wnua" and not is_wnua_loopback_host(self.config.host):
                    msg = (
                        "Automatic WNUA connections require the exact PyMechanical-supported "
                        "endpoint 'localhost' or '127.0.0.1'."
                    )
                    raise MechanicalTransportConfigurationError(msg)
                reason = "loopback_secure_platform_default"
            else:
                effective = "mtls"
                reason = "remote_secure_default"
        else:
            effective = self.config.transport_mode
            reason = "explicit_transport"

        self._selected_transport = effective
        self._transport_selection_reason = reason
        self._transport_preflight = MechanicalTransportPreflight(
            status="not_run",
            source="connect_requires_matching_server_transport",
            message=(
                "A connect operation cannot determine the server transport before connecting; "
                "no automatic secure-to-insecure downgrade is performed."
            ),
        )
        return effective

    def _configured_connection_scope(self) -> str | None:
        if self.config.mode == "start":
            return "local_start_pending_transport_preflight"
        if self.config.mode == "connect":
            return "loopback_connect" if is_loopback_host(self.config.host) else "remote_connect"
        return None

    def _resolve_launch_mechanical(self) -> PyMechanicalFactory:
        if self._launch_mechanical is not None:
            return self._launch_mechanical

        try:
            from ansys.mechanical.core import launch_mechanical
        except ImportError as exc:
            msg = (
                "PyMechanical is not installed. Install ansys-mechanical-core "
                "or the project's 'ansys' extra to start Ansys Mechanical."
            )
            raise MechanicalDependencyError(msg) from exc

        self._launch_mechanical = launch_mechanical
        return launch_mechanical

    def _resolve_connect_to_mechanical(self) -> PyMechanicalFactory:
        if self._connect_to_mechanical is not None:
            return self._connect_to_mechanical

        try:
            from ansys.mechanical.core import connect_to_mechanical
        except ImportError as exc:
            msg = (
                "PyMechanical is not installed. Install ansys-mechanical-core "
                "or the project's 'ansys' extra to connect to Ansys Mechanical."
            )
            raise MechanicalDependencyError(msg) from exc

        self._connect_to_mechanical = connect_to_mechanical
        return connect_to_mechanical


def _is_secure_transport_compatibility_error(error: Exception) -> bool:
    """Match only PyMechanical's documented pre-process compatibility failure."""
    message = str(error)
    return (
        message.startswith("Mechanical version ")
        and "does not support secure transport modes." in message
        and "secure gRPC support" in message
    )
