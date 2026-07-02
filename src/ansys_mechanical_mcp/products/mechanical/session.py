"""PyMechanical session management."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from ansys_mechanical_mcp.core.errors import AnsysMechanicalMcpError


MechanicalSessionMode = Literal["start", "connect"]
PyMechanicalFactory = Callable[..., Any]


class MechanicalSessionError(AnsysMechanicalMcpError):
    """Raised when a PyMechanical session cannot be started or connected."""


@dataclass(slots=True)
class MechanicalSessionConfig:
    """Configuration for a Mechanical session."""

    mode: MechanicalSessionMode = "start"
    version: str | None = None
    batch: bool = True
    cleanup_on_exit: bool | None = None
    host: str | None = None
    port: int | None = None

    def __post_init__(self) -> None:
        """Validate user-facing session configuration."""
        if self.mode not in ("start", "connect"):
            msg = "Mechanical session mode must be either 'start' or 'connect'."
            raise MechanicalSessionError(msg)

        if self.port is not None and not 1 <= self.port <= 65535:
            msg = "Mechanical session port must be between 1 and 65535."
            raise MechanicalSessionError(msg)

        if self.mode == "start" and self.host is not None:
            msg = "Mechanical session host is only valid when mode is 'connect'."
            raise MechanicalSessionError(msg)

    @property
    def effective_cleanup_on_exit(self) -> bool:
        """Return the cleanup behavior for the configured session mode."""
        if self.cleanup_on_exit is not None:
            return self.cleanup_on_exit
        return self.mode == "start"


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

    @property
    def session(self):
        """Return the underlying PyMechanical session, if available."""
        return self._session

    def start_or_connect(self):
        """Start or connect to Mechanical and return the PyMechanical session."""
        if self._session is not None:
            return self._session

        if self.config.mode == "start":
            self._session = self._start()
        else:
            self._session = self._connect()

        return self._session

    def _start(self):
        launch_mechanical = self._resolve_launch_mechanical()
        kwargs: dict[str, Any] = {
            "allow_input": False,
            "batch": self.config.batch,
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
                f"(version={self.config.version!r}, batch={self.config.batch!r}, "
                f"host={self.config.host!r}, port={self.config.port!r}): {exc}"
            )
            raise MechanicalSessionError(msg) from exc

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
            raise MechanicalSessionError(msg) from exc

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
            raise MechanicalSessionError(msg) from exc

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
            raise MechanicalSessionError(msg) from exc

        self._connect_to_mechanical = connect_to_mechanical
        return connect_to_mechanical
