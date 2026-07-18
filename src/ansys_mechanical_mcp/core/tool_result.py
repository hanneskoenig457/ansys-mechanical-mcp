"""Shared result helpers for MCP tools."""

import json
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
        normalized = json.loads(json.dumps(asdict(self), allow_nan=False))
        if not isinstance(normalized, dict):  # pragma: no cover - dataclass root is a mapping.
            raise TypeError("Tool result must serialize to a JSON object.")
        return normalized
