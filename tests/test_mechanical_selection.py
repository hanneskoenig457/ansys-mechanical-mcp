import json
from datetime import datetime, timezone

import pytest

from ansys_mechanical_mcp.products.mechanical.selection import (
    MECHANICAL_SELECTION_CAPTURE_SCRIPT,
    capture_current_selection,
)


class FakeMechanicalSession:
    def __init__(self, result: object, *, fail: bool = False) -> None:
        self.result = result
        self.fail = fail
        self.calls = []

    def run_python_script(self, script, **kwargs):
        self.calls.append((script, kwargs))
        if self.fail:
            raise RuntimeError("selection transport failed")
        return self.result


def _payload(*, selection=None, active_tree_objects=None, warnings=None) -> str:
    selection_payload = {
        "present": True,
        "native_selection_type": "GeometryEntities",
        "name": None,
        "native_ids": [42],
        "unparsed_ids": [],
        "rich_interface_available": True,
        "entities": [{"native_id": 42, "native_type": "GeoFace"}],
        "element_face_indices": [],
        "unparsed_element_face_indices": [],
    }
    if selection is not None:
        selection_payload.update(selection)
    return json.dumps(
        {
            "selection": selection_payload,
            "active_tree_objects": active_tree_objects or [],
            "model_context": {
                "product_version": "2026 R1",
                "project_name": "Project",
                "model_name": "Model",
                "document_id": None,
                "model_id": None,
                "geometry_revision": None,
                "mesh_revision": None,
            },
            "warnings": warnings or [],
        }
    )


def _clock() -> datetime:
    return datetime(2026, 7, 17, 12, 30, tzinfo=timezone.utc)


def test_capture_empty_selection_returns_truthful_snapshot() -> None:
    raw = _payload(
        selection={
            "present": False,
            "native_selection_type": None,
            "native_ids": [],
            "rich_interface_available": False,
            "entities": [],
        }
    )

    result = capture_current_selection(
        FakeMechanicalSession(raw),
        session_context={"mode": "connect", "interactive": True},
        clock=_clock,
    )

    snapshot = result.data["snapshot"]
    assert result.success is True
    assert snapshot["captured_at"] == "2026-07-17T12:30:00Z"
    assert snapshot["is_empty"] is True
    assert snapshot["count"] == 0
    assert snapshot["native_ids"] == []
    assert snapshot["entities"] == []
    assert snapshot["summary"] == "No entities are selected in Mechanical."
    assert not any(
        warning["code"] == "RICH_SELECTION_INTERFACE_UNAVAILABLE"
        for warning in snapshot["warnings"]
    )


def test_capture_single_geometry_selection_normalizes_face_and_context() -> None:
    raw = _payload(
        active_tree_objects=[
            {
                "native_id": 17,
                "name": "Static Structural",
                "native_type": "Analysis",
                "category": "Analysis",
            }
        ]
    )
    session = FakeMechanicalSession(raw)

    result = capture_current_selection(
        session,
        session_context={"mode": "connect", "interactive": True},
        clock=_clock,
    )

    snapshot = result.data["snapshot"]
    assert result.success is True
    assert snapshot["schema_version"] == "1.0"
    assert snapshot["source"] == "ansys-mechanical"
    assert snapshot["provenance"] == "mechanical_current_selection"
    assert snapshot["capture_status"] == "captured"
    assert snapshot["is_complete"] is True
    assert snapshot["native_selection_type"] == "GeometryEntities"
    assert snapshot["entity_type"] == "face"
    assert snapshot["count"] == 1
    assert snapshot["entities"] == [
        {
            "native_id": 42,
            "entity_type": "face",
            "native_type": "GeoFace",
            "native_entity_type": None,
            "element_face_index": None,
        }
    ]
    assert snapshot["active_tree_objects"][0]["name"] == "Static Structural"
    assert snapshot["model_context"]["geometry_revision"] is None
    assert "geometry_revision" in snapshot["model_context"]["unavailable_fields"]
    assert snapshot["summary"] == "Mechanical selection contains 1 face."
    assert "ExtAPI.SelectionManager" in session.calls[0][0]
    assert "CurrentSelection" in session.calls[0][0]
    assert "ActiveObjects" in session.calls[0][0]
    assert session.calls[0][0] == MECHANICAL_SELECTION_CAPTURE_SCRIPT


def test_capture_multiple_geometry_selection_preserves_each_native_id() -> None:
    raw = _payload(
        selection={
            "native_ids": [10, 11],
            "entities": [
                {"native_id": 10, "native_type": "IGeoFace"},
                {"native_id": 11, "native_type": "IGeoFace"},
            ],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert snapshot["count"] == 2
    assert snapshot["entity_type"] == "face"
    assert [entry["native_id"] for entry in snapshot["entities"]] == [10, 11]
    assert snapshot["summary"] == "Mechanical selection contains 2 faces."


def test_general_selection_info_returns_partial_geometry_snapshot_with_warning() -> None:
    raw = _payload(
        selection={
            "native_ids": [10, 11],
            "rich_interface_available": False,
            "entities": [],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert result.success is True
    assert snapshot["entity_type"] is None
    assert snapshot["native_ids"] == [10, 11]
    assert [entry["entity_type"] for entry in snapshot["entities"]] == [None, None]
    assert "RICH_SELECTION_INTERFACE_UNAVAILABLE" in {
        warning["code"] for warning in snapshot["warnings"]
    }


def test_unknown_selection_type_is_preserved_with_warning() -> None:
    raw = _payload(
        selection={
            "native_selection_type": "FutureSelectionMode",
            "rich_interface_available": False,
            "entities": [],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert result.success is True
    assert snapshot["native_selection_type"] == "FutureSelectionMode"
    assert snapshot["entity_type"] is None
    assert "UNKNOWN_SELECTION_TYPE" in {warning["code"] for warning in snapshot["warnings"]}
    assert "FutureSelectionMode" in snapshot["summary"]


@pytest.mark.parametrize(
    ("native_selection_type", "expected_entity_type"),
    [("MeshNodes", "node"), ("MeshElements", "element")],
)
def test_mesh_id_selection_uses_documented_selection_type_semantics(
    native_selection_type: str,
    expected_entity_type: str,
) -> None:
    raw = _payload(
        selection={
            "native_selection_type": native_selection_type,
            "native_ids": [100, 101],
            "rich_interface_available": False,
            "entities": [],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert snapshot["entity_type"] == expected_entity_type
    assert [entry["entity_type"] for entry in snapshot["entities"]] == [
        expected_entity_type,
        expected_entity_type,
    ]


def test_element_face_selection_preserves_documented_positional_pairs() -> None:
    raw = _payload(
        selection={
            "native_selection_type": "MeshElementFaces",
            "native_ids": [100, 101],
            "entities": [],
            "element_face_indices": [2, 4],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert snapshot["entity_type"] == "element_face"
    assert snapshot["entities"] == [
        {
            "native_id": 100,
            "entity_type": "element_face",
            "native_type": None,
            "native_entity_type": None,
            "element_face_index": 2,
        },
        {
            "native_id": 101,
            "entity_type": "element_face",
            "native_type": None,
            "native_entity_type": None,
            "element_face_index": 4,
        },
    ]


def test_mismatched_element_face_arrays_remain_unpaired_and_warn() -> None:
    raw = _payload(
        selection={
            "native_selection_type": "MeshElementFaces",
            "native_ids": [100, 101],
            "entities": [],
            "element_face_indices": [2],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert [entry["element_face_index"] for entry in snapshot["entities"]] == [None, None]
    assert "ELEMENT_FACE_MAPPING_INCOMPLETE" in {
        warning["code"] for warning in snapshot["warnings"]
    }
    assert snapshot["raw_fields"]["element_face_indices"] == [2]


def test_element_face_mapping_preserves_original_positions_after_parse_failures() -> None:
    raw = _payload(
        selection={
            "native_selection_type": "MeshElementFaces",
            "native_ids": [101],
            "native_id_positions": [1],
            "native_id_value_count": 2,
            "unparsed_ids": ["bad-id"],
            "entities": [],
            "element_face_indices": [2],
            "element_face_index_positions": [0],
            "element_face_index_value_count": 2,
            "unparsed_element_face_indices": ["bad-face"],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert snapshot["entities"][0]["native_id"] == 101
    assert snapshot["entities"][0]["element_face_index"] is None
    assert "ELEMENT_FACE_MAPPING_PARTIAL" in {warning["code"] for warning in snapshot["warnings"]}
    assert snapshot["capture_status"] == "partial"
    assert snapshot["is_complete"] is False


def test_unreadable_native_ids_do_not_claim_an_empty_selection() -> None:
    raw = _payload(
        selection={
            "native_ids": [],
            "native_id_positions": [],
            "native_id_value_count": 1,
            "unparsed_ids": ["bad-id"],
            "rich_interface_available": False,
            "entities": [],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert snapshot["count"] == 1
    assert snapshot["is_empty"] is False
    assert "SELECTION_IDS_PARTIALLY_UNREADABLE" in {
        warning["code"] for warning in snapshot["warnings"]
    }


def test_capture_wraps_mechanical_transport_failure() -> None:
    result = capture_current_selection(
        FakeMechanicalSession(_payload(), fail=True),
        session_context={"mode": "connect"},
        clock=_clock,
    )

    snapshot = result.data["snapshot"]
    assert result.success is False
    assert result.error == "MECHANICAL_SELECTION_EXECUTION_FAILED"
    assert snapshot["capture_status"] == "failed"
    assert snapshot["is_complete"] is False
    assert snapshot["provenance"] == "mechanical_current_selection_attempt"
    assert snapshot["is_empty"] is None
    assert snapshot["count"] is None
    assert snapshot["errors"][0]["code"] == "MECHANICAL_SELECTION_EXECUTION_FAILED"
    assert "selection transport failed" in snapshot["errors"][0]["details"]["execution_message"]


def test_capture_wraps_invalid_json_payload() -> None:
    result = capture_current_selection(FakeMechanicalSession("not json"), clock=_clock)

    assert result.success is False
    assert result.error == "MECHANICAL_SELECTION_PARSE_FAILED"
    assert result.data["snapshot"]["errors"][0]["details"]["raw_result"] == "not json"


def test_capture_keeps_non_json_proxy_response_json_compatible() -> None:
    class NativeProxy:
        def __str__(self) -> str:
            return "selection-proxy"

    result = capture_current_selection(FakeMechanicalSession(NativeProxy()), clock=_clock)

    assert result.success is False
    details = result.data["snapshot"]["errors"][0]["details"]
    assert details["raw_result"] == {
        "python_type": "NativeProxy",
        "text": "selection-proxy",
    }
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_capture_keeps_nonfinite_response_json_compatible(value: float) -> None:
    result = capture_current_selection(FakeMechanicalSession(value), clock=_clock)

    assert result.success is False
    details = result.data["snapshot"]["errors"][0]["details"]
    assert details["raw_result"]["python_type"] == "float"
    assert json.loads(json.dumps(result.to_dict(), allow_nan=False)) == result.to_dict()


def test_snapshot_normalizes_tuple_values_and_non_string_mapping_keys() -> None:
    result = capture_current_selection(
        FakeMechanicalSession(_payload()),
        session_context={"tuple": (1, 2), 7: "native-key"},  # type: ignore[dict-item]
        clock=_clock,
    )

    context = result.data["snapshot"]["session_context"]
    assert context == {"tuple": [1, 2], "7": "native-key"}


def test_mechanical_script_warns_when_tree_capability_is_unavailable() -> None:
    class SelectionManager:
        CurrentSelection = None

    class DataModel:
        pass

    class ExtApi:
        pass

    ext_api = ExtApi()
    ext_api.SelectionManager = SelectionManager()
    ext_api.DataModel = DataModel()
    script_body, capture_call = MECHANICAL_SELECTION_CAPTURE_SCRIPT.rsplit("\n", 1)
    namespace = {"ExtAPI": ext_api}
    exec(f"{script_body}\n__test_capture_result = {capture_call}", namespace)

    payload = json.loads(namespace["__test_capture_result"])
    warning_codes = {warning["code"] for warning in payload["warnings"]}
    assert "ACTIVE_TREE_UNAVAILABLE" in warning_codes
    assert "_read_attr" not in namespace
    assert not any(name.startswith("__ansys_mechanical_mcp_capture") for name in namespace)


def test_mechanical_script_bounds_large_native_selection_before_serialization() -> None:
    class CurrentSelection:
        SelectionType = "MeshNodes"
        Name = None
        Ids = list(range(1005))

    class SelectionManager:
        pass

    class ExtApi:
        pass

    ext_api = ExtApi()
    selection_manager = SelectionManager()
    selection_manager.CurrentSelection = CurrentSelection()
    ext_api.SelectionManager = selection_manager
    script_body, capture_call = MECHANICAL_SELECTION_CAPTURE_SCRIPT.rsplit("\n", 1)
    namespace = {"ExtAPI": ext_api}
    exec(f"{script_body}\n__test_capture_result = {capture_call}", namespace)

    payload = json.loads(namespace["__test_capture_result"])
    assert payload["selection"]["native_id_value_count"] == 1005
    assert len(payload["selection"]["native_ids"]) == 1000
    assert "SELECTION_FIELD_TRUNCATED" in {warning["code"] for warning in payload["warnings"]}

    result = capture_current_selection(
        FakeMechanicalSession(namespace["__test_capture_result"]),
        clock=_clock,
    )
    snapshot = result.data["snapshot"]
    assert snapshot["count"] == 1005
    assert len(snapshot["native_ids"]) == 1000
    assert snapshot["capture_status"] == "partial"
    assert snapshot["is_complete"] is False


def test_countless_iterable_at_exact_limit_is_not_marked_truncated() -> None:
    class ExactLimitIds:
        def __iter__(self):
            return iter(range(1000))

    class CurrentSelection:
        SelectionType = "MeshNodes"
        Name = None
        Ids = ExactLimitIds()

    class SelectionManager:
        pass

    class ExtApi:
        pass

    selection_manager = SelectionManager()
    selection_manager.CurrentSelection = CurrentSelection()
    ext_api = ExtApi()
    ext_api.SelectionManager = selection_manager
    script_body, capture_call = MECHANICAL_SELECTION_CAPTURE_SCRIPT.rsplit("\n", 1)
    namespace = {"ExtAPI": ext_api}
    exec(f"{script_body}\n__test_capture_result = {capture_call}", namespace)

    payload = json.loads(namespace["__test_capture_result"])
    assert payload["selection"]["native_id_value_count"] == 1000
    assert "SELECTION_FIELD_TRUNCATED" not in {warning["code"] for warning in payload["warnings"]}


def test_capture_function_removes_global_binding_after_script_failure() -> None:
    class ExtApi:
        pass

    script_body, capture_call = MECHANICAL_SELECTION_CAPTURE_SCRIPT.rsplit("\n", 1)
    namespace = {"ExtAPI": ExtApi()}

    with pytest.raises(RuntimeError, match="SelectionManager"):
        exec(f"{script_body}\n__test_capture_result = {capture_call}", namespace)

    assert not any(name.startswith("__ansys_mechanical_mcp_capture") for name in namespace)


def test_active_tree_native_type_uses_runtime_type_not_domain_type_property() -> None:
    class SelectionManager:
        CurrentSelection = None

    class RuntimeType:
        Name = "Sizing"

    class ActiveObject:
        ObjectId = 5
        Name = "Local Sizing"
        Type = "MisleadingSizingSetting"
        DataModelObjectCategory = "MeshControl"

        def GetType(self):
            return RuntimeType()

    class Tree:
        pass

    class DataModel:
        pass

    class ExtApi:
        pass

    ext_api = ExtApi()
    ext_api.SelectionManager = SelectionManager()
    data_model = DataModel()
    tree = Tree()
    tree.ActiveObjects = [ActiveObject()]
    data_model.Tree = tree
    ext_api.DataModel = data_model
    script_body, capture_call = MECHANICAL_SELECTION_CAPTURE_SCRIPT.rsplit("\n", 1)
    namespace = {"ExtAPI": ext_api}
    exec(f"{script_body}\n__test_capture_result = {capture_call}", namespace)

    payload = json.loads(namespace["__test_capture_result"])
    assert payload["active_tree_objects"][0]["native_type"] == "Sizing"


def test_null_ids_are_unknown_instead_of_empty() -> None:
    class CurrentSelection:
        SelectionType = "GeometryEntities"
        Name = None
        Ids = None

    class SelectionManager:
        pass

    class ExtApi:
        pass

    selection_manager = SelectionManager()
    selection_manager.CurrentSelection = CurrentSelection()
    ext_api = ExtApi()
    ext_api.SelectionManager = selection_manager
    script_body, capture_call = MECHANICAL_SELECTION_CAPTURE_SCRIPT.rsplit("\n", 1)
    namespace = {"ExtAPI": ext_api}
    exec(f"{script_body}\n__test_capture_result = {capture_call}", namespace)

    result = capture_current_selection(
        FakeMechanicalSession(namespace["__test_capture_result"]),
        clock=_clock,
    )
    snapshot = result.data["snapshot"]
    assert snapshot["count"] is None
    assert snapshot["is_empty"] is None
    assert snapshot["capture_status"] == "partial"
    assert "SELECTION_IDS_NULL" in {warning["code"] for warning in snapshot["warnings"]}


def test_irrelevant_null_rich_fields_do_not_make_node_selection_partial() -> None:
    class CurrentSelection:
        SelectionType = "MeshNodes"
        Name = None
        Ids = [10, 11]
        Entities = None
        ElementFaceIndices = None

    class SelectionManager:
        pass

    class Tree:
        ActiveObjects = []

    class DataModel:
        pass

    class ExtApi:
        pass

    selection_manager = SelectionManager()
    selection_manager.CurrentSelection = CurrentSelection()
    data_model = DataModel()
    data_model.Tree = Tree()
    ext_api = ExtApi()
    ext_api.SelectionManager = selection_manager
    ext_api.DataModel = data_model
    script_body, capture_call = MECHANICAL_SELECTION_CAPTURE_SCRIPT.rsplit("\n", 1)
    namespace = {"ExtAPI": ext_api}
    exec(f"{script_body}\n__test_capture_result = {capture_call}", namespace)

    result = capture_current_selection(
        FakeMechanicalSession(namespace["__test_capture_result"]),
        clock=_clock,
    )
    snapshot = result.data["snapshot"]
    assert snapshot["entity_type"] == "node"
    assert snapshot["capture_status"] == "captured"
    assert snapshot["is_complete"] is True


def test_geometry_aggregate_type_requires_details_for_every_selected_entity() -> None:
    raw = _payload(
        selection={
            "native_ids": [10, 11],
            "entities": [{"native_id": 10, "native_type": "GeoFace"}],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    snapshot = result.data["snapshot"]
    assert snapshot["count"] == 2
    assert snapshot["entity_type"] is None
    assert snapshot["capture_status"] == "partial"
    assert "GEOMETRY_ENTITY_TYPES_INCOMPLETE" in {
        warning["code"] for warning in snapshot["warnings"]
    }


@pytest.mark.parametrize(
    ("native_types", "expected_summary"),
    [
        (["GeoBody", "GeoBody"], "Mechanical selection contains 2 bodies."),
        (["GeoVertex", "GeoVertex"], "Mechanical selection contains 2 vertices."),
        (
            ["GeoFace", "GeoEdge"],
            "Mechanical selection contains 2 mixed geometry entities.",
        ),
    ],
)
def test_geometry_summary_uses_correct_plural_forms(
    native_types: list[str],
    expected_summary: str,
) -> None:
    native_ids = list(range(1, len(native_types) + 1))
    raw = _payload(
        selection={
            "native_ids": native_ids,
            "entities": [
                {"native_id": native_id, "native_type": native_type}
                for native_id, native_type in zip(native_ids, native_types, strict=True)
            ],
        }
    )

    result = capture_current_selection(FakeMechanicalSession(raw), clock=_clock)

    assert result.data["snapshot"]["summary"] == expected_summary


def test_successful_snapshot_is_strictly_json_compatible() -> None:
    result = capture_current_selection(FakeMechanicalSession(_payload()), clock=_clock)

    assert json.loads(json.dumps(result.to_dict(), allow_nan=False)) == result.to_dict()
