"""PyMechanical session management."""

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any, Literal

from ansys_mechanical_mcp.core.errors import AnsysMechanicalMcpError


MechanicalSessionMode = Literal["start", "connect"]
PyMechanicalFactory = Callable[..., Any]


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

        if self.mode == "connect" and self.version is not None:
            msg = (
                "Mechanical session version is a launch request and is only valid when mode "
                "is 'start'; inspect the connected product version instead."
            )
            raise MechanicalSessionError(msg)

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
    ) -> None:
        self.config = config or MechanicalSessionConfig()
        self._session = None
        self._launch_mechanical = launch_mechanical
        self._connect_to_mechanical = connect_to_mechanical
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

            if self.config.mode == "start":
                self._session = self._start()
            else:
                self._session = self._connect()

            if self._session is None:
                msg = "PyMechanical did not return a Mechanical session."
                raise MechanicalSessionError(msg)

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
        kwargs: dict[str, Any] = {
            "allow_input": False,
            "batch": self.config.effective_batch,
            "cleanup_on_exit": self.config.effective_cleanup_on_exit,
            "start_instance": True,
        }
        if self.config.version is not None:
            kwargs["version"] = self.config.version
        if self.config.port is not None:
            kwargs["port"] = self.config.port

        try:
            return launch_mechanical(**kwargs)
        except Exception as exc:
            msg = (
                "Failed to start Ansys Mechanical with PyMechanical "
                f"(version={self.config.version!r}, batch={self.config.effective_batch!r}, "
                f"host={self.config.host!r}, port={self.config.port!r}): {exc}"
            )
            raise MechanicalSessionStartError(msg) from exc

    def _connect(self):
        connect_to_mechanical = self._resolve_connect_to_mechanical()
        kwargs: dict[str, Any] = {
            "cleanup_on_exit": self.config.effective_cleanup_on_exit,
        }
        if self.config.host is not None:
            kwargs["ip"] = self.config.host
        if self.config.port is not None:
            kwargs["port"] = self.config.port

        try:
            return connect_to_mechanical(**kwargs)
        except Exception as exc:
            msg = (
                "Failed to connect to Ansys Mechanical with PyMechanical "
                f"(host={self.config.host!r}, port={self.config.port!r}): {exc}"
            )
            raise MechanicalSessionConnectError(msg) from exc

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
