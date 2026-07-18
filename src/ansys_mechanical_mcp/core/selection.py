"""Small product-neutral contracts for read-only native selection capture."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SelectionIssue:
    """Structured warning or error attached to a selection snapshot."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SelectionEntity:
    """One native entity reference observed in the source product."""

    native_id: int | None
    entity_type: str | None = None
    native_type: str | None = None
    native_entity_type: str | None = None
    element_face_index: int | None = None


@dataclass(slots=True)
class SelectionContextObject:
    """A separately observed active object in the source product's tree."""

    native_id: int | None
    name: str | None = None
    native_type: str | None = None
    category: str | None = None


@dataclass(slots=True)
class SelectionSnapshot:
    """Revision-scoped, JSON-compatible facts about one native selection."""

    schema_version: str
    source: str
    provenance: str
    capture_status: str
    is_complete: bool
    captured_at: str
    session_context: dict[str, Any]
    model_context: dict[str, Any]
    native_selection_type: str | None
    entity_type: str | None
    is_empty: bool | None
    count: int | None
    entities: list[SelectionEntity]
    native_ids: list[int]
    active_tree_objects: list[SelectionContextObject]
    summary: str
    raw_fields: dict[str, Any] = field(default_factory=dict)
    warnings: list[SelectionIssue] = field(default_factory=list)
    errors: list[SelectionIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return and validate the snapshot as strict JSON-compatible data."""
        payload = asdict(self)
        normalized = json.loads(json.dumps(payload, allow_nan=False))
        if not isinstance(normalized, dict):  # pragma: no cover - dataclass root is a mapping.
            raise TypeError("Selection snapshot must serialize to a JSON object.")
        return normalized
