"""PyMechanical session management placeholders."""

from dataclasses import dataclass


@dataclass(slots=True)
class MechanicalSessionConfig:
    """Configuration for a Mechanical session."""

    version: str | None = None
    batch: bool = True
    cleanup_on_exit: bool = True


class MechanicalSessionManager:
    """Manage a PyMechanical session.

    Implementation must be added only after the startup/connect behavior is verified
    against official PyMechanical documentation.
    """

    def __init__(self, config: MechanicalSessionConfig | None = None) -> None:
        self.config = config or MechanicalSessionConfig()
        self._session = None

    @property
    def session(self):
        """Return the underlying PyMechanical session, if available."""
        return self._session

