"""Shared result helpers for MCP tools."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolResult:
    """JSON-compatible result payload for MCP tools."""

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary."""
        return asdict(self)

