"""Read-only capture of Mechanical's current native selection."""

from __future__ import annotations

import json
import math
import textwrap
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from ansys_mechanical_mcp.core.selection import (
    SelectionContextObject,
    SelectionEntity,
    SelectionIssue,
    SelectionSnapshot,
)
from ansys_mechanical_mcp.core.tool_result import ToolResult
from ansys_mechanical_mcp.products.mechanical.tools import execute_mechanical_script

SELECTION_SCHEMA_VERSION = "1.0"
SELECTION_SOURCE = "ansys-mechanical"
SELECTION_PROVENANCE = "mechanical_current_selection"
MAX_SELECTION_ITEMS = 1000
_CAPTURE_FUNCTION_NAME = "__ansys_mechanical_mcp_capture_selection_v1"


_MECHANICAL_SELECTION_CAPTURE_BODY = r"""
# Read-only capture of the current graphics selection and active tree objects.
import json


_MAX_SELECTION_ITEMS = __ANSYS_MECHANICAL_MCP_MAX_SELECTION_ITEMS__
warnings = []


def _read_attr(obj, name):
    if obj is None:
        return False, None
    try:
        return True, getattr(obj, name)
    except Exception:
        return False, None


def _safe_text(value):
    if value is None:
        return None
    try:
        return str(value)
    except Exception:
        return None


def _safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _compact_type(value):
    text = _safe_text(value)
    if text is None:
        return ""
    return "".join(character for character in text.lower() if character.isalnum())


def _safe_sequence(value, code, field):
    if value is None:
        return [], 0

    total = None
    try:
        total = len(value)
    except Exception:
        count_available, count_value = _read_attr(value, "Count")
        total = _safe_int(count_value) if count_available else None

    items = []
    has_more = False
    try:
        for index, item in enumerate(value):
            if index >= _MAX_SELECTION_ITEMS:
                has_more = True
                break
            items.append(item)
    except Exception:
        warnings.append(
            {
                "code": code,
                "message": "Mechanical returned a non-iterable selection field.",
                "details": {"field": field, "value": _safe_text(value)},
            }
        )
        return [], total

    truncated = (total is not None and total > len(items)) or has_more
    if truncated:
        warnings.append(
            {
                "code": "SELECTION_FIELD_TRUNCATED",
                "message": "Mechanical selection data exceeded the bounded capture limit.",
                "details": {
                    "field": field,
                    "limit": _MAX_SELECTION_ITEMS,
                    "total": total,
                },
            }
        )
    if total is None and not truncated:
        total = len(items)
    return items, total


def _runtime_type(obj):
    available, get_type = _read_attr(obj, "GetType")
    if not available or not callable(get_type):
        return None
    try:
        dotnet_type = get_type()
    except Exception:
        return None
    available, name = _read_attr(dotnet_type, "Name")
    return _safe_text(name) if available else _safe_text(dotnet_type)


def _domain_type(obj):
    available, value = _read_attr(obj, "Type")
    return _safe_text(value) if available else None


def _object_id(obj):
    for field in ("ObjectId", "Id"):
        available, value = _read_attr(obj, field)
        if available:
            native_id = _safe_int(value)
            if native_id is not None:
                return native_id
    return None


selection_manager_available, selection_manager = _read_attr(ExtAPI, "SelectionManager")
if not selection_manager_available:
    raise RuntimeError("ExtAPI.SelectionManager is unavailable")

current_available, current = _read_attr(selection_manager, "CurrentSelection")
if not current_available:
    raise RuntimeError("ExtAPI.SelectionManager.CurrentSelection is unavailable")

selection_payload = {
    "present": current is not None,
    "selection_object_id": None,
    "native_selection_type": None,
    "name": None,
    "native_ids": [],
    "native_id_positions": [],
    "native_id_value_count": 0,
    "unparsed_ids": [],
    "rich_interface_available": False,
    "entities": [],
    "entity_value_count": 0,
    "element_face_indices": [],
    "element_face_index_positions": [],
    "element_face_index_value_count": 0,
    "unparsed_element_face_indices": [],
}

if current is not None:
    selection_id_available, selection_id = _read_attr(current, "Id")
    if selection_id_available:
        selection_payload["selection_object_id"] = _safe_int(selection_id)

    type_available, selection_type = _read_attr(current, "SelectionType")
    if type_available:
        selection_payload["native_selection_type"] = _safe_text(selection_type)

    name_available, selection_name = _read_attr(current, "Name")
    if name_available:
        selection_payload["name"] = _safe_text(selection_name)

    ids_available, ids_value = _read_attr(current, "Ids")
    if ids_available and ids_value is not None:
        raw_ids, raw_id_count = _safe_sequence(
            ids_value,
            "SELECTION_IDS_NOT_ITERABLE",
            "Ids",
        )
        selection_payload["native_id_value_count"] = raw_id_count
        for position, value in enumerate(raw_ids):
            native_id = _safe_int(value)
            if native_id is None:
                selection_payload["unparsed_ids"].append(_safe_text(value))
            else:
                selection_payload["native_ids"].append(native_id)
                selection_payload["native_id_positions"].append(position)
    elif ids_available:
        selection_payload["native_id_value_count"] = None
        warnings.append(
            {
                "code": "SELECTION_IDS_NULL",
                "message": "Mechanical returned null for the current selection Ids.",
                "details": {},
            }
        )
    else:
        selection_payload["native_id_value_count"] = None
        warnings.append(
            {
                "code": "SELECTION_IDS_UNAVAILABLE",
                "message": "The current ISelectionInfo does not expose readable Ids.",
                "details": {},
            }
        )

    entities_available, entities_value = _read_attr(current, "Entities")
    faces_available, face_indices_value = _read_attr(current, "ElementFaceIndices")
    selection_payload["rich_interface_available"] = entities_available or faces_available
    selection_kind = _compact_type(selection_payload["native_selection_type"])

    if (
        selection_kind.endswith("geometryentities")
        and entities_available
        and entities_value is not None
    ):
        raw_entities, _entity_count = _safe_sequence(
            entities_value,
            "SELECTION_ENTITIES_NOT_ITERABLE",
            "Entities",
        )
        selection_payload["entity_value_count"] = _entity_count
        for entity in raw_entities:
            selection_payload["entities"].append(
                {
                    "native_id": _object_id(entity),
                    "native_type": _runtime_type(entity),
                    "native_entity_type": _domain_type(entity),
                }
            )
    elif selection_kind.endswith("geometryentities") and entities_available:
        selection_payload["entity_value_count"] = None
        warnings.append(
            {
                "code": "SELECTION_ENTITIES_NULL",
                "message": "Mechanical returned null for geometry selection Entities.",
                "details": {},
            }
        )

    if (
        selection_kind.endswith("meshelementfaces")
        and faces_available
        and face_indices_value is not None
    ):
        raw_face_indices, raw_face_count = _safe_sequence(
            face_indices_value,
            "ELEMENT_FACE_INDICES_NOT_ITERABLE",
            "ElementFaceIndices",
        )
        selection_payload["element_face_index_value_count"] = raw_face_count
        for position, value in enumerate(raw_face_indices):
            face_index = _safe_int(value)
            if face_index is None:
                selection_payload["unparsed_element_face_indices"].append(_safe_text(value))
            else:
                selection_payload["element_face_indices"].append(face_index)
                selection_payload["element_face_index_positions"].append(position)
    elif selection_kind.endswith("meshelementfaces") and faces_available:
        selection_payload["element_face_index_value_count"] = None
        warnings.append(
            {
                "code": "ELEMENT_FACE_INDICES_NULL",
                "message": "Mechanical returned null for element-face indices.",
                "details": {},
            }
        )

data_model_available, data_model = _read_attr(ExtAPI, "DataModel")
project = None
model = None
tree = None
if data_model_available:
    project_available, project = _read_attr(data_model, "Project")
    if not project_available:
        project = None
    tree_available, tree = _read_attr(data_model, "Tree")
    if not tree_available:
        tree = None
else:
    warnings.append(
        {
            "code": "DATA_MODEL_UNAVAILABLE",
            "message": "Mechanical ExtAPI.DataModel is unavailable.",
            "details": {},
        }
    )
if project is not None:
    model_available, model = _read_attr(project, "Model")
    if not model_available:
        model = None

active_tree_objects = []
if tree is not None:
    active_available, active_value = _read_attr(tree, "ActiveObjects")
    if active_available:
        raw_active_objects, _active_object_count = _safe_sequence(
            active_value,
            "ACTIVE_TREE_OBJECTS_NOT_ITERABLE",
            "Tree.ActiveObjects",
        )
        for active_object in raw_active_objects:
            name_available, name = _read_attr(active_object, "Name")
            category_available, category = _read_attr(
                active_object,
                "DataModelObjectCategory",
            )
            active_tree_objects.append(
                {
                    "native_id": _object_id(active_object),
                    "name": _safe_text(name) if name_available else None,
                    "native_type": _runtime_type(active_object),
                    "category": _safe_text(category) if category_available else None,
                }
            )
    else:
        warnings.append(
            {
                "code": "ACTIVE_TREE_OBJECTS_UNAVAILABLE",
                "message": "Mechanical Tree.ActiveObjects is unavailable.",
                "details": {},
            }
        )
elif data_model_available:
    warnings.append(
        {
            "code": "ACTIVE_TREE_UNAVAILABLE",
            "message": "Mechanical DataModel.Tree is unavailable.",
            "details": {},
        }
    )

product_version_available, product_version = _read_attr(project, "ProductVersion")
project_name_available, project_name = _read_attr(project, "Name")
model_name_available, model_name = _read_attr(model, "Name")

payload = {
    "selection": selection_payload,
    "active_tree_objects": active_tree_objects,
    "model_context": {
        "product_version": (
            _safe_text(product_version) if product_version_available else None
        ),
        "project_name": _safe_text(project_name) if project_name_available else None,
        "model_name": _safe_text(model_name) if model_name_available else None,
        "document_id": None,
        "model_id": None,
        "geometry_revision": None,
        "mesh_revision": None,
    },
    "warnings": warnings,
}

""".strip()

_RENDERED_SELECTION_CAPTURE_BODY = _MECHANICAL_SELECTION_CAPTURE_BODY.replace(
    "__ANSYS_MECHANICAL_MCP_MAX_SELECTION_ITEMS__",
    str(MAX_SELECTION_ITEMS),
)

MECHANICAL_SELECTION_CAPTURE_SCRIPT = (
    f"def {_CAPTURE_FUNCTION_NAME}():\n"
    "    def _capture():\n"
    f"{textwrap.indent(_RENDERED_SELECTION_CAPTURE_BODY, '        ')}\n"
    "        return json.dumps(payload)\n"
    "    try:\n"
    "        return _capture()\n"
    "    finally:\n"
    "        try:\n"
    f"            del globals()['{_CAPTURE_FUNCTION_NAME}']\n"
    "        except Exception:\n"
    "            pass\n"
    f"{_CAPTURE_FUNCTION_NAME}()"
)


def capture_current_selection(
    session: Any,
    *,
    session_context: dict[str, Any] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ToolResult:
    """Capture and normalize Mechanical's current graphics selection."""
    captured_at = _captured_at(clock)
    context = _validated_json_mapping(session_context or {})
    execution = execute_mechanical_script(
        session,
        script=MECHANICAL_SELECTION_CAPTURE_SCRIPT,
    )
    if not execution.success:
        return selection_error_result(
            error="MECHANICAL_SELECTION_EXECUTION_FAILED",
            message="Mechanical selection capture failed during script execution.",
            session_context=context,
            captured_at=captured_at,
            details={"execution_error": execution.error, "execution_message": execution.message},
        )

    raw_result = execution.data.get("result")
    if not isinstance(raw_result, str) or not raw_result.strip():
        return selection_error_result(
            error="MECHANICAL_SELECTION_PARSE_FAILED",
            message="Mechanical selection capture did not return JSON text.",
            session_context=context,
            captured_at=captured_at,
            details={"raw_result": _json_diagnostic(raw_result)},
        )

    try:
        payload = json.loads(raw_result)
        snapshot = _normalize_selection_payload(
            payload,
            session_context=context,
            captured_at=captured_at,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return selection_error_result(
            error="MECHANICAL_SELECTION_PARSE_FAILED",
            message=f"Mechanical selection capture returned invalid JSON: {exc}",
            session_context=context,
            captured_at=captured_at,
            details={"raw_result": raw_result},
        )

    return ToolResult(
        success=True,
        message="Mechanical current selection captured successfully.",
        data={"snapshot": snapshot.to_dict()},
    )


def selection_error_result(
    *,
    error: str,
    message: str,
    session_context: dict[str, Any] | None = None,
    captured_at: str | None = None,
    details: dict[str, Any] | None = None,
) -> ToolResult:
    """Return a structured failed selection snapshot for pre-capture errors."""
    context = _validated_json_mapping(session_context or {})
    issue = SelectionIssue(
        code=error,
        message=message,
        details=_validated_json_mapping(details or {}),
    )
    snapshot = SelectionSnapshot(
        schema_version=SELECTION_SCHEMA_VERSION,
        source=SELECTION_SOURCE,
        provenance=f"{SELECTION_PROVENANCE}_attempt",
        capture_status="failed",
        is_complete=False,
        captured_at=captured_at or _captured_at(None),
        session_context=context,
        model_context=_empty_model_context(),
        native_selection_type=None,
        entity_type=None,
        is_empty=None,
        count=None,
        entities=[],
        native_ids=[],
        active_tree_objects=[],
        summary="Mechanical selection capture failed.",
        errors=[issue],
    )
    return ToolResult(
        success=False,
        message=message,
        data={"snapshot": snapshot.to_dict()},
        error=error,
    )


def _normalize_selection_payload(
    payload: Any,
    *,
    session_context: dict[str, Any],
    captured_at: str,
) -> SelectionSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("selection payload must be a JSON object")

    selection = payload.get("selection")
    if not isinstance(selection, dict):
        raise ValueError("'selection' must be a JSON object")

    present = selection.get("present")
    if not isinstance(present, bool):
        raise ValueError("'selection.present' must be a boolean")

    native_selection_type = _nullable_text(
        selection.get("native_selection_type"),
        "selection.native_selection_type",
    )
    native_ids = _integer_list(selection.get("native_ids"), "selection.native_ids")
    unparsed_ids = _text_list(selection.get("unparsed_ids", []), "selection.unparsed_ids")
    native_id_positions = _positions(
        selection.get("native_id_positions"),
        len(native_ids),
        "selection.native_id_positions",
    )
    native_id_value_count = _value_count(
        selection,
        "native_id_value_count",
        minimum=len(native_ids) + len(unparsed_ids),
    )
    _validate_position_bounds(
        native_id_positions,
        native_id_value_count,
        "selection.native_id_positions",
    )
    raw_entity_records = _entity_records(selection.get("entities"))
    entity_value_count = _value_count(
        selection,
        "entity_value_count",
        minimum=len(raw_entity_records),
    )
    face_indices = _integer_list(
        selection.get("element_face_indices"),
        "selection.element_face_indices",
    )
    unparsed_face_indices = _text_list(
        selection.get("unparsed_element_face_indices", []),
        "selection.unparsed_element_face_indices",
    )
    face_index_positions = _positions(
        selection.get("element_face_index_positions"),
        len(face_indices),
        "selection.element_face_index_positions",
    )
    face_index_value_count = _value_count(
        selection,
        "element_face_index_value_count",
        minimum=len(face_indices) + len(unparsed_face_indices),
    )
    _validate_position_bounds(
        face_index_positions,
        face_index_value_count,
        "selection.element_face_index_positions",
    )
    rich_interface = selection.get("rich_interface_available")
    if not isinstance(rich_interface, bool):
        raise ValueError("'selection.rich_interface_available' must be a boolean")

    warnings = _issues(payload.get("warnings", []), "warnings")
    normalized_selection_type = _normalize_selection_type(native_selection_type)

    missing_rich_entity_ids = sum(record["native_id"] is None for record in raw_entity_records)
    if normalized_selection_type == "geometry" and missing_rich_entity_ids:
        warnings.append(
            SelectionIssue(
                code="SELECTION_ENTITY_IDS_UNAVAILABLE",
                message="Some richer geometry entity records do not expose a native ID.",
                details={"missing_id_count": missing_rich_entity_ids},
            )
        )

    if present and not rich_interface:
        warnings.append(
            SelectionIssue(
                code="RICH_SELECTION_INTERFACE_UNAVAILABLE",
                message=(
                    "The current selection exposes only the general ISelectionInfo surface; "
                    "Mechanical-specific entity details are unavailable."
                ),
            )
        )

    if present and native_selection_type is None:
        warnings.append(
            SelectionIssue(
                code="SELECTION_TYPE_UNAVAILABLE",
                message="Mechanical did not provide a readable native selection type.",
            )
        )
    elif normalized_selection_type is None and native_selection_type is not None:
        warnings.append(
            SelectionIssue(
                code="UNKNOWN_SELECTION_TYPE",
                message="The native Mechanical selection type is not normalized by this schema.",
                details={"native_selection_type": native_selection_type},
            )
        )

    if not native_ids and normalized_selection_type == "geometry":
        recovered_ids = [
            record["native_id"] for record in raw_entity_records if record["native_id"] is not None
        ]
        if recovered_ids:
            native_ids = recovered_ids
            native_id_positions = list(range(len(native_ids)))
            warnings.append(
                SelectionIssue(
                    code="SELECTION_IDS_RECOVERED_FROM_ENTITIES",
                    message="Native IDs were recovered from rich geometry entity records.",
                )
            )

    entities = _selection_entities(
        native_ids,
        raw_entity_records,
        normalized_selection_type,
        face_indices,
        native_id_positions,
        face_index_positions,
        native_id_value_count,
        face_index_value_count,
        warnings,
    )
    count = native_id_value_count
    relevant_entity_count = entity_value_count if normalized_selection_type == "geometry" else 0
    if count is None and relevant_entity_count not in (None, 0):
        count = entity_value_count
    if count is not None:
        count = max(count, relevant_entity_count or 0, len(native_ids), len(entities))
    elif native_ids or entities:
        count = None
    is_empty = None if count is None else count == 0
    entity_type = _aggregate_entity_type(normalized_selection_type, entities, count)
    if normalized_selection_type == "geometry" and count not in (None, 0) and entity_type is None:
        warnings.append(
            SelectionIssue(
                code="GEOMETRY_ENTITY_TYPES_INCOMPLETE",
                message=(
                    "Mechanical did not provide a normalized geometry type for every selected "
                    "entity; no aggregate geometry type was claimed."
                ),
                details={"selected_count": count, "detailed_entity_count": len(entities)},
            )
        )

    if native_ids:
        warnings.append(
            SelectionIssue(
                code="NATIVE_IDS_ARE_REVISION_SCOPED",
                message=(
                    "Native IDs are valid only for this Mechanical model and revision and "
                    "must be resolved again before any later mutation."
                ),
            )
        )

    model_context = _model_context(payload.get("model_context"))
    if model_context["unavailable_fields"]:
        warnings.append(
            SelectionIssue(
                code="MODEL_REVISION_CONTEXT_INCOMPLETE",
                message=(
                    "Mechanical did not expose stable document/model/revision identifiers "
                    "through the validated capture path."
                ),
                details={"unavailable_fields": model_context["unavailable_fields"]},
            )
        )

    active_tree_objects = _active_tree_objects(payload.get("active_tree_objects"))
    if unparsed_ids:
        warnings.append(
            SelectionIssue(
                code="SELECTION_IDS_PARTIALLY_UNREADABLE",
                message="Mechanical returned selection IDs that could not be converted to integers.",
                details={"values": unparsed_ids},
            )
        )
    if unparsed_face_indices:
        warnings.append(
            SelectionIssue(
                code="ELEMENT_FACE_INDICES_PARTIALLY_UNREADABLE",
                message=(
                    "Mechanical returned element-face indices that could not be converted "
                    "to integers."
                ),
                details={"values": unparsed_face_indices},
            )
        )
    incomplete_coverage: dict[str, dict[str, int]] = {}
    if native_id_value_count is not None and native_id_value_count > len(native_ids) + len(
        unparsed_ids
    ):
        incomplete_coverage["Ids"] = {
            "source_count": native_id_value_count,
            "returned_count": len(native_ids) + len(unparsed_ids),
        }
    if (
        normalized_selection_type == "geometry"
        and entity_value_count is not None
        and entity_value_count > len(raw_entity_records)
    ):
        incomplete_coverage["Entities"] = {
            "source_count": entity_value_count,
            "returned_count": len(raw_entity_records),
        }
    if (
        normalized_selection_type == "element_face"
        and face_index_value_count is not None
        and face_index_value_count > len(face_indices) + len(unparsed_face_indices)
    ):
        incomplete_coverage["ElementFaceIndices"] = {
            "source_count": face_index_value_count,
            "returned_count": len(face_indices) + len(unparsed_face_indices),
        }
    if incomplete_coverage:
        warnings.append(
            SelectionIssue(
                code="CAPTURE_ARRAY_COVERAGE_INCOMPLETE",
                message="The returned native arrays do not cover their reported source counts.",
                details={"fields": incomplete_coverage},
            )
        )
    incomplete_codes = {
        "ACTIVE_TREE_OBJECTS_NOT_ITERABLE",
        "ACTIVE_TREE_OBJECTS_UNAVAILABLE",
        "ACTIVE_TREE_UNAVAILABLE",
        "CAPTURE_ARRAY_COVERAGE_INCOMPLETE",
        "DATA_MODEL_UNAVAILABLE",
        "ELEMENT_FACE_INDICES_NOT_ITERABLE",
        "ELEMENT_FACE_INDICES_NULL",
        "ELEMENT_FACE_INDICES_PARTIALLY_UNREADABLE",
        "ELEMENT_FACE_MAPPING_INCOMPLETE",
        "ELEMENT_FACE_MAPPING_PARTIAL",
        "GEOMETRY_ENTITY_TYPES_INCOMPLETE",
        "SELECTION_ENTITIES_NOT_ITERABLE",
        "SELECTION_ENTITIES_NULL",
        "SELECTION_ENTITY_IDS_UNAVAILABLE",
        "SELECTION_ENTITY_DETAILS_UNMATCHED",
        "SELECTION_FIELD_TRUNCATED",
        "SELECTION_IDS_NOT_ITERABLE",
        "SELECTION_IDS_NULL",
        "SELECTION_IDS_PARTIALLY_UNREADABLE",
        "SELECTION_IDS_RECOVERED_FROM_ENTITIES",
        "SELECTION_IDS_UNAVAILABLE",
        "SELECTION_TYPE_UNAVAILABLE",
        "UNKNOWN_SELECTION_TYPE",
    }
    is_complete = native_id_value_count is not None and not any(
        warning.code in incomplete_codes for warning in warnings
    )
    capture_status = "captured" if is_complete else "partial"
    raw_fields = {
        "selection_object_id": _nullable_integer(
            selection.get("selection_object_id"),
            "selection.selection_object_id",
        ),
        "selection_name": _nullable_text(selection.get("name"), "selection.name"),
        "rich_interface_available": rich_interface,
        "capture_limit": MAX_SELECTION_ITEMS,
        "native_id_positions": native_id_positions,
        "native_id_value_count": native_id_value_count,
        "entity_value_count": entity_value_count,
        "element_face_indices": face_indices,
        "element_face_index_positions": face_index_positions,
        "element_face_index_value_count": face_index_value_count,
        "unparsed_ids": unparsed_ids,
        "unparsed_element_face_indices": unparsed_face_indices,
    }

    snapshot = SelectionSnapshot(
        schema_version=SELECTION_SCHEMA_VERSION,
        source=SELECTION_SOURCE,
        provenance=SELECTION_PROVENANCE,
        capture_status=capture_status,
        is_complete=is_complete,
        captured_at=captured_at,
        session_context=session_context,
        model_context=model_context,
        native_selection_type=native_selection_type,
        entity_type=entity_type,
        is_empty=is_empty,
        count=count,
        entities=entities,
        native_ids=native_ids,
        active_tree_objects=active_tree_objects,
        summary=_summary(is_empty, count, entity_type, native_selection_type),
        raw_fields=raw_fields,
        warnings=warnings,
        errors=[],
    )
    snapshot.to_dict()
    return snapshot


def _selection_entities(
    native_ids: list[int],
    records: list[dict[str, Any]],
    normalized_selection_type: str | None,
    face_indices: list[int],
    native_id_positions: list[int],
    face_index_positions: list[int],
    native_id_value_count: int | None,
    face_index_value_count: int | None,
    warnings: list[SelectionIssue],
) -> list[SelectionEntity]:
    face_by_position = dict(zip(face_index_positions, face_indices, strict=True))
    face_mapping_allowed = (
        normalized_selection_type == "element_face"
        and native_id_value_count is not None
        and native_id_value_count == face_index_value_count
    )
    if normalized_selection_type == "element_face":
        if not face_mapping_allowed:
            warnings.append(
                SelectionIssue(
                    code="ELEMENT_FACE_MAPPING_INCOMPLETE",
                    message=(
                        "Mechanical element IDs and element-face indices do not have a verified "
                        "equal source length; no positional face mapping was applied."
                    ),
                    details={
                        "id_value_count": native_id_value_count,
                        "face_index_value_count": face_index_value_count,
                    },
                )
            )
        else:
            missing_positions = [
                position for position in native_id_positions if position not in face_by_position
            ]
            if missing_positions:
                warnings.append(
                    SelectionIssue(
                        code="ELEMENT_FACE_MAPPING_PARTIAL",
                        message=(
                            "Some element-face pairs contain an unreadable face index; only "
                            "positionally verified pairs were retained."
                        ),
                        details={"unmapped_id_positions": missing_positions},
                    )
                )

    records_by_id: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        native_id = record["native_id"]
        if native_id is not None:
            records_by_id.setdefault(native_id, []).append(record)

    entities: list[SelectionEntity] = []
    for index, native_id in enumerate(native_ids):
        source_position = native_id_positions[index]
        matches = records_by_id.get(native_id, [])
        record = matches.pop(0) if matches else None
        native_type = record["native_type"] if record is not None else None
        native_entity_type = record["native_entity_type"] if record is not None else None
        entity_type = _normalize_geometry_entity_type(native_entity_type)
        if entity_type is None:
            entity_type = _normalize_geometry_entity_type(native_type)
        if normalized_selection_type in {"node", "element", "element_face"}:
            entity_type = normalized_selection_type

        face_index = None
        if face_mapping_allowed:
            face_index = face_by_position.get(source_position)

        entities.append(
            SelectionEntity(
                native_id=native_id,
                entity_type=entity_type,
                native_type=native_type,
                native_entity_type=native_entity_type,
                element_face_index=face_index,
            )
        )

    if not native_ids:
        for record in records:
            native_type = record["native_type"]
            native_entity_type = record["native_entity_type"]
            entity_type = _normalize_geometry_entity_type(native_entity_type)
            if entity_type is None:
                entity_type = _normalize_geometry_entity_type(native_type)
            entities.append(
                SelectionEntity(
                    native_id=record["native_id"],
                    entity_type=entity_type,
                    native_type=native_type,
                    native_entity_type=native_entity_type,
                )
            )

    unmatched_records = sum(len(matches) for matches in records_by_id.values())
    if native_ids and unmatched_records:
        warnings.append(
            SelectionIssue(
                code="SELECTION_ENTITY_DETAILS_UNMATCHED",
                message="Some rich entity records could not be matched to selection IDs.",
                details={"unmatched_count": unmatched_records},
            )
        )

    return entities


def _aggregate_entity_type(
    normalized_selection_type: str | None,
    entities: list[SelectionEntity],
    count: int | None,
) -> str | None:
    if normalized_selection_type in {"node", "element", "element_face"}:
        return normalized_selection_type
    if normalized_selection_type != "geometry":
        return None

    if (
        count is None
        or len(entities) != count
        or any(entity.entity_type is None for entity in entities)
    ):
        return None

    types = {entity.entity_type for entity in entities if entity.entity_type is not None}
    if len(types) == 1:
        return next(iter(types))
    if len(types) > 1:
        return "mixed_geometry"
    return None


def _normalize_selection_type(value: str | None) -> str | None:
    compact = _compact_type(value)
    for suffix, normalized in (
        ("geometryentities", "geometry"),
        ("meshnodes", "node"),
        ("meshelements", "element"),
        ("meshelementfaces", "element_face"),
    ):
        if compact.endswith(suffix):
            return normalized
    return None


def _normalize_geometry_entity_type(value: str | None) -> str | None:
    compact = _compact_type(value)
    for suffix, normalized in (
        ("geoface", "face"),
        ("face", "face"),
        ("geoedge", "edge"),
        ("edge", "edge"),
        ("geovertex", "vertex"),
        ("vertex", "vertex"),
        ("geobody", "body"),
        ("body", "body"),
    ):
        if compact.endswith(suffix):
            return normalized
    return None


def _compact_type(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(character for character in value.lower() if character.isalnum())


def _entity_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("'selection.entities' must be a list")
    records = []
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise ValueError(f"'selection.entities[{index}]' must be a JSON object")
        native_id = record.get("native_id")
        if native_id is not None and (
            isinstance(native_id, bool) or not isinstance(native_id, int)
        ):
            raise ValueError(f"'selection.entities[{index}].native_id' must be an integer or null")
        records.append(
            {
                "native_id": native_id,
                "native_type": _nullable_text(
                    record.get("native_type"),
                    f"selection.entities[{index}].native_type",
                ),
                "native_entity_type": _nullable_text(
                    record.get("native_entity_type"),
                    f"selection.entities[{index}].native_entity_type",
                ),
            }
        )
    return records


def _active_tree_objects(value: Any) -> list[SelectionContextObject]:
    if not isinstance(value, list):
        raise ValueError("'active_tree_objects' must be a list")
    objects = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise ValueError(f"'active_tree_objects[{index}]' must be a JSON object")
        native_id = entry.get("native_id")
        if native_id is not None and (
            isinstance(native_id, bool) or not isinstance(native_id, int)
        ):
            raise ValueError(f"'active_tree_objects[{index}].native_id' must be an integer or null")
        objects.append(
            SelectionContextObject(
                native_id=native_id,
                name=_nullable_text(entry.get("name"), f"active_tree_objects[{index}].name"),
                native_type=_nullable_text(
                    entry.get("native_type"),
                    f"active_tree_objects[{index}].native_type",
                ),
                category=_nullable_text(
                    entry.get("category"),
                    f"active_tree_objects[{index}].category",
                ),
            )
        )
    return objects


def _model_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("'model_context' must be a JSON object")
    fields = (
        "product_version",
        "project_name",
        "model_name",
        "document_id",
        "model_id",
        "geometry_revision",
        "mesh_revision",
    )
    context = {
        field: _nullable_text(value.get(field), f"model_context.{field}") for field in fields
    }
    context["unavailable_fields"] = [field for field in fields if context[field] is None]
    return context


def _empty_model_context() -> dict[str, Any]:
    fields = [
        "product_version",
        "project_name",
        "model_name",
        "document_id",
        "model_id",
        "geometry_revision",
        "mesh_revision",
    ]
    return {**dict.fromkeys(fields), "unavailable_fields": fields}


def _issues(value: Any, field: str) -> list[SelectionIssue]:
    if not isinstance(value, list):
        raise ValueError(f"'{field}' must be a list")
    issues = []
    for index, issue in enumerate(value):
        if not isinstance(issue, dict):
            raise ValueError(f"'{field}[{index}]' must be a JSON object")
        code = issue.get("code")
        message = issue.get("message")
        details = issue.get("details", {})
        if not isinstance(code, str) or not isinstance(message, str):
            raise ValueError(f"'{field}[{index}]' must contain string code and message")
        if not isinstance(details, dict):
            raise ValueError(f"'{field}[{index}].details' must be a JSON object")
        issues.append(
            SelectionIssue(
                code=code,
                message=message,
                details=_validated_json_mapping(details),
            )
        )
    return issues


def _integer_list(value: Any, field: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"'{field}' must be a list")
    integers = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(f"'{field}[{index}]' must be an integer")
        integers.append(item)
    return integers


def _positions(value: Any, expected_length: int, field: str) -> list[int]:
    if value is None:
        return list(range(expected_length))
    positions = _integer_list(value, field)
    if len(positions) != expected_length:
        raise ValueError(f"'{field}' must have one entry per parsed value")
    if any(position < 0 for position in positions):
        raise ValueError(f"'{field}' entries must be non-negative")
    if len(set(positions)) != len(positions):
        raise ValueError(f"'{field}' entries must be unique")
    return positions


def _value_count(
    mapping: dict[str, Any],
    field: str,
    *,
    minimum: int,
) -> int | None:
    if field not in mapping:
        return minimum
    value = mapping.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"'selection.{field}' must be null or an integer >= {minimum}")
    return value


def _validate_position_bounds(
    positions: list[int],
    value_count: int | None,
    field: str,
) -> None:
    if value_count is not None and any(position >= value_count for position in positions):
        raise ValueError(f"'{field}' contains a position outside the source sequence")


def _text_list(value: Any, field: str) -> list[str | None]:
    if not isinstance(value, list):
        raise ValueError(f"'{field}' must be a list")
    return [_nullable_text(item, f"{field}[{index}]") for index, item in enumerate(value)]


def _nullable_text(value: Any, field: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"'{field}' must be a string or null")


def _nullable_integer(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"'{field}' must be an integer or null")
    return value


def _summary(
    is_empty: bool | None,
    count: int | None,
    entity_type: str | None,
    native_selection_type: str | None,
) -> str:
    if is_empty is None or count is None:
        return "Mechanical selection entity count is unknown."
    if is_empty:
        return "No entities are selected in Mechanical."
    if entity_type is not None:
        labels = {
            "face": ("face", "faces"),
            "edge": ("edge", "edges"),
            "vertex": ("vertex", "vertices"),
            "body": ("body", "bodies"),
            "node": ("node", "nodes"),
            "element": ("element", "elements"),
            "element_face": ("element face", "element faces"),
            "mixed_geometry": ("mixed geometry entity", "mixed geometry entities"),
        }
        singular, plural = labels.get(
            entity_type,
            (entity_type.replace("_", " "), f"{entity_type.replace('_', ' ')}s"),
        )
        return f"Mechanical selection contains {count} {singular if count == 1 else plural}."
    if native_selection_type is not None:
        return (
            f"Mechanical selection contains {count} entities "
            f"(native type: {native_selection_type})."
        )
    return f"Mechanical selection contains {count} entities of unknown type."


def _captured_at(clock: Callable[[], datetime] | None) -> str:
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validated_json_mapping(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("JSON mapping must be a dictionary")
    normalized = json.loads(json.dumps(value, allow_nan=False))
    if not isinstance(normalized, dict):  # pragma: no cover - mapping input stays a mapping.
        raise TypeError("JSON mapping must serialize to an object")
    return normalized


def _json_diagnostic(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return {"python_type": "float", "text": str(value)}
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    try:
        text = str(value)
    except Exception:
        text = None
    return {"python_type": type(value).__name__, "text": text}
