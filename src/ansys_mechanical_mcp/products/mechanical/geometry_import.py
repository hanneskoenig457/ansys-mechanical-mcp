"""Controlled Mechanical geometry import and native readback."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from ansys_mechanical_mcp.core.tool_result import ToolResult
from ansys_mechanical_mcp.products.mechanical.tools import execute_mechanical_script

_INSPECT_FUNCTION_NAME = "__ansys_mechanical_mcp_inspect_geometry_import_v1"
_APPLY_FUNCTION_NAME = "__ansys_mechanical_mcp_apply_geometry_import_v1"

_STATE_HELPERS = r"""
def _safe_attr(obj, name):
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


def _safe_path_metadata(value):
    text = _safe_text(value)
    if not text:
        return None, None
    try:
        normalized = os.path.normcase(os.path.abspath(text))
        identity = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return os.path.basename(text), identity
    except Exception:
        return None, None


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _items(value):
    if value is None:
        return []
    try:
        return list(value)
    except Exception:
        return None


def _body_metadata(body):
    object_id = None
    for field in ("ObjectId", "Id"):
        available, value = _safe_attr(body, field)
        if available:
            object_id = _safe_int(value)
            if object_id is not None:
                break
    _, name = _safe_attr(body, "Name")
    _, body_type = _safe_attr(body, "BodyType")
    _, material = _safe_attr(body, "Material")
    return {
        "object_id": object_id,
        "name": _safe_text(name),
        "type": _safe_text(body_type),
        "material": _safe_text(material),
    }


def _capture_state():
    errors = []
    data_model_available, data_model = _safe_attr(ExtAPI, "DataModel")
    project_available, project = _safe_attr(data_model, "Project")
    model_available, model = _safe_attr(project, "Model")
    if not data_model_available:
        errors.append("ExtAPI.DataModel unavailable")
    if not project_available:
        errors.append("ExtAPI.DataModel.Project unavailable")
    if not model_available:
        errors.append("Project.Model unavailable")

    _, product_version = _safe_attr(project, "ProductVersion")
    _, project_file = _safe_attr(project, "FilePath")
    project_file_name, project_file_identity = _safe_path_metadata(project_file)
    _, unit_system = _safe_attr(project, "UnitSystem")

    analyses_available, analyses_value = _safe_attr(model, "Analyses")
    analyses = _items(analyses_value) if analyses_available else None
    if analyses is None:
        errors.append("Model.Analyses is unavailable or non-iterable")

    import_group_available, import_group = _safe_attr(model, "GeometryImportGroup")
    imports_available, imports_value = _safe_attr(import_group, "Children")
    imports = _items(imports_value) if imports_available else None
    if not import_group_available or imports is None:
        errors.append("Model.GeometryImportGroup.Children is unavailable or non-iterable")

    geo_data_available, geo_data = _safe_attr(data_model, "GeoData")
    assemblies_available, assemblies_value = _safe_attr(geo_data, "Assemblies")
    assemblies = _items(assemblies_value) if assemblies_available else None
    bodies = []
    if not geo_data_available or assemblies is None:
        errors.append("ExtAPI.DataModel.GeoData.Assemblies is unavailable or non-iterable")
    else:
        for assembly in assemblies:
            parts_available, parts_value = _safe_attr(assembly, "Parts")
            parts = _items(parts_value) if parts_available else None
            if parts is None:
                errors.append("A geometry assembly has no iterable Parts collection")
                continue
            for part in parts:
                part_bodies_available, part_bodies_value = _safe_attr(part, "Bodies")
                part_bodies = _items(part_bodies_value) if part_bodies_available else None
                if part_bodies is None:
                    errors.append("A geometry part has no iterable Bodies collection")
                    continue
                bodies.extend(_body_metadata(body) for body in part_bodies)

    analysis_count = len(analyses) if analyses is not None else None
    geometry_import_count = len(imports) if imports is not None else None
    body_count = len(bodies) if assemblies is not None else None
    complete = not errors
    return {
        "inspection_status": "complete" if complete else "partial",
        "product_version": _safe_text(product_version),
        "project_file_name": project_file_name,
        "project_file_identity": project_file_identity,
        "unit_system": _safe_text(unit_system),
        "analysis_count": analysis_count,
        "geometry_import_count": geometry_import_count,
        "body_count": body_count,
        "bodies": bodies,
        "is_empty": (
            complete
            and analysis_count == 0
            and geometry_import_count == 0
            and body_count == 0
        ),
        "errors": errors,
    }
""".strip()

_INSPECTION_BODY = f"""
import hashlib
import json
import os

{_STATE_HELPERS}

return json.dumps({{"state": _capture_state()}})
""".strip()

MECHANICAL_GEOMETRY_IMPORT_INSPECTION_SCRIPT = (
    f"def {_INSPECT_FUNCTION_NAME}():\n"
    "    try:\n"
    f"{textwrap.indent(_INSPECTION_BODY, '        ')}\n"
    "    finally:\n"
    "        try:\n"
    f"            del globals()['{_INSPECT_FUNCTION_NAME}']\n"
    "        except Exception:\n"
    "            pass\n"
    f"{_INSPECT_FUNCTION_NAME}()"
)


def inspect_geometry_import_state(session: Any) -> ToolResult:
    """Return strict native project/body evidence without mutation."""
    execution = execute_mechanical_script(
        session,
        script=MECHANICAL_GEOMETRY_IMPORT_INSPECTION_SCRIPT,
    )
    if not execution.success:
        return ToolResult(
            success=False,
            message="Mechanical geometry inspection failed during script execution.",
            data={"execution": execution.to_dict()},
            error="MECHANICAL_GEOMETRY_INSPECTION_EXECUTION_FAILED",
        )
    return _parse_payload(
        execution.data.get("result"),
        success_message="Mechanical geometry inspected successfully.",
        parse_error="MECHANICAL_GEOMETRY_INSPECTION_PARSE_FAILED",
        normalizer=_normalize_state_payload,
    )


def apply_geometry_import(
    session: Any,
    *,
    input_path: Path,
    output_path: Path,
    expected_sha256: str,
    expected_project: dict[str, Any],
) -> ToolResult:
    """Run exactly one import/save script and return native post-import evidence."""
    script = _build_apply_script(
        input_path=input_path,
        output_path=output_path,
        expected_sha256=expected_sha256,
        expected_project=expected_project,
    )
    execution = execute_mechanical_script(session, script=script)
    if not execution.success:
        execution_data = _redact_paths(
            execution.to_dict(),
            input_path=input_path,
            output_path=output_path,
        )
        return ToolResult(
            success=False,
            message=(
                "Mechanical geometry import failed. The project may have changed; "
                "the operation will not be retried automatically."
            ),
            data={
                "execution": execution_data,
                "mutation_status": "unknown",
            },
            error="MECHANICAL_GEOMETRY_IMPORT_EXECUTION_FAILED",
        )
    return _parse_payload(
        execution.data.get("result"),
        success_message="Geometry imported once and saved to a new Mechanical project.",
        parse_error="MECHANICAL_GEOMETRY_IMPORT_READBACK_FAILED",
        normalizer=_normalize_apply_payload,
    )


def _build_apply_script(
    *,
    input_path: Path,
    output_path: Path,
    expected_sha256: str,
    expected_project: dict[str, Any],
) -> str:
    input_literal = json.dumps(str(input_path), ensure_ascii=True)
    output_literal = json.dumps(str(output_path), ensure_ascii=True)
    expected_sha256_literal = json.dumps(expected_sha256, ensure_ascii=True)
    expected_literal = json.dumps(
        json.dumps(expected_project, allow_nan=False, sort_keys=True),
        ensure_ascii=True,
    )
    body = f"""
import hashlib
import json
import os

{_STATE_HELPERS}

input_path = {input_literal}
output_path = {output_literal}
expected_sha256 = {expected_sha256_literal}
expected_project = json.loads({expected_literal})

if not os.path.isfile(input_path):
    raise RuntimeError("CAD_INPUT_MISSING_BEFORE_IMPORT")
if _file_sha256(input_path) != expected_sha256:
    raise RuntimeError("CAD_INPUT_CHANGED_BEFORE_IMPORT")
if os.path.exists(output_path):
    raise RuntimeError("CAD_IMPORT_OUTPUT_EXISTS_BEFORE_IMPORT")
if os.listdir(os.path.dirname(output_path)):
    raise RuntimeError("CAD_IMPORT_OUTPUT_DIRECTORY_NOT_EMPTY_BEFORE_IMPORT")

before = _capture_state()
actual_project = {{
    "product_version": before["product_version"],
    "project_file_name": before["project_file_name"],
    "project_file_identity": before["project_file_identity"],
    "analysis_count": before["analysis_count"],
    "geometry_import_count": before["geometry_import_count"],
    "body_count": before["body_count"],
    "body_ids": [body["object_id"] for body in before["bodies"]],
}}
if before["inspection_status"] != "complete" or actual_project != expected_project:
    raise RuntimeError("CAD_IMPORT_PLAN_STALE_IN_MECHANICAL")
if not before["is_empty"]:
    raise RuntimeError("MECHANICAL_PROJECT_NOT_EMPTY_BEFORE_IMPORT")

geometry_import = Model.GeometryImportGroup.AddGeometryImport()
geometry_format = Ansys.Mechanical.DataModel.Enums.GeometryImportPreference.Format.Automatic
preferences = Ansys.ACT.Mechanical.Utilities.GeometryImportPreferences()
preferences.ProcessNamedSelections = False
preferences.ProcessCoordinateSystems = False
preferences.ProcessMaterialProperties = False
geometry_import.Import(input_path, geometry_format, preferences)

after_import = _capture_state()
if after_import["inspection_status"] != "complete" or after_import["body_count"] < 1:
    raise RuntimeError("MECHANICAL_GEOMETRY_IMPORT_NATIVE_READBACK_FAILED")

project = ExtAPI.DataModel.Project
project.SaveAs(output_path, False)
after_save = _capture_state()
payload = {{
    "state": after_save,
    "import": {{
        "object_id": _safe_int(_safe_attr(geometry_import, "ObjectId")[1]),
        "format": "Automatic",
        "source_sha256": _file_sha256(input_path),
        "output_created": os.path.isfile(output_path),
        "overwrite": False,
    }},
}}
return json.dumps(payload)
""".strip()
    return (
        f"def {_APPLY_FUNCTION_NAME}():\n"
        "    try:\n"
        f"{textwrap.indent(body, '        ')}\n"
        "    finally:\n"
        "        try:\n"
        f"            del globals()['{_APPLY_FUNCTION_NAME}']\n"
        "        except Exception:\n"
        "            pass\n"
        f"{_APPLY_FUNCTION_NAME}()"
    )


def _parse_payload(
    raw_result: Any,
    *,
    success_message: str,
    parse_error: str,
    normalizer: Any,
) -> ToolResult:
    if not isinstance(raw_result, str) or not raw_result.strip():
        return ToolResult(
            success=False,
            message="Mechanical did not return JSON text.",
            data={"raw_result_type": type(raw_result).__name__},
            error=parse_error,
        )
    try:
        payload = normalizer(json.loads(raw_result))
        json.loads(json.dumps(payload, allow_nan=False))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return ToolResult(
            success=False,
            message=f"Mechanical returned invalid geometry JSON: {exc}",
            data={"raw_result": raw_result},
            error=parse_error,
        )
    return ToolResult(success=True, message=success_message, data=payload)


def _normalize_state_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
        raise ValueError("payload must contain a 'state' object")
    return {"state": _normalize_state(payload["state"])}


def _normalize_apply_payload(payload: Any) -> dict[str, Any]:
    normalized = _normalize_state_payload(payload)
    import_data = payload.get("import")
    if not isinstance(import_data, dict):
        raise ValueError("payload must contain an 'import' object")
    if import_data.get("output_created") is not True:
        raise ValueError("Mechanical did not confirm creation of the output project")
    if import_data.get("overwrite") is not False:
        raise ValueError("Mechanical import readback must confirm overwrite=false")
    normalized["import"] = {
        "object_id": _optional_int(import_data.get("object_id"), "import.object_id"),
        "format": _optional_string(import_data.get("format"), "import.format"),
        "source_sha256": _required_string(
            import_data.get("source_sha256"),
            "import.source_sha256",
        ),
        "output_created": True,
        "overwrite": False,
    }
    return normalized


def _normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    status = state.get("inspection_status")
    if status not in {"complete", "partial"}:
        raise ValueError("state.inspection_status must be 'complete' or 'partial'")
    bodies = state.get("bodies")
    errors = state.get("errors")
    if not isinstance(bodies, list) or not isinstance(errors, list):
        raise ValueError("state.bodies and state.errors must be lists")
    normalized_bodies = []
    for index, body in enumerate(bodies):
        if not isinstance(body, dict):
            raise ValueError(f"state.bodies[{index}] must be an object")
        normalized_bodies.append(
            {
                "object_id": _optional_int(body.get("object_id"), f"bodies[{index}].object_id"),
                "name": _optional_string(body.get("name"), f"bodies[{index}].name"),
                "type": _optional_string(body.get("type"), f"bodies[{index}].type"),
                "material": _optional_string(body.get("material"), f"bodies[{index}].material"),
            }
        )
    normalized_errors = [
        _required_string(value, f"state.errors[{index}]") for index, value in enumerate(errors)
    ]
    normalized = {
        "inspection_status": status,
        "product_version": _optional_string(state.get("product_version"), "product_version"),
        "project_file_name": _optional_string(
            state.get("project_file_name"),
            "project_file_name",
        ),
        "project_file_identity": _optional_string(
            state.get("project_file_identity"),
            "project_file_identity",
        ),
        "unit_system": _optional_string(state.get("unit_system"), "unit_system"),
        "analysis_count": _optional_int(state.get("analysis_count"), "analysis_count"),
        "geometry_import_count": _optional_int(
            state.get("geometry_import_count"),
            "geometry_import_count",
        ),
        "body_count": _optional_int(state.get("body_count"), "body_count"),
        "bodies": normalized_bodies,
        "is_empty": state.get("is_empty") is True,
        "errors": normalized_errors,
    }
    if status == "complete":
        for field in ("analysis_count", "geometry_import_count", "body_count"):
            if normalized[field] is None:
                raise ValueError(f"complete state requires state.{field}")
        if normalized["body_count"] != len(normalized_bodies):
            raise ValueError("state.body_count does not match state.bodies")
    return normalized


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string or null")
    return value


def _optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer or null")
    return value


def _redact_paths(value: Any, *, input_path: Path, output_path: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_paths(item, input_path=input_path, output_path=output_path)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_paths(item, input_path=input_path, output_path=output_path)
            for item in value
        ]
    if isinstance(value, str):
        redacted = value
        for path, replacement in (
            (input_path, "<cad-input>"),
            (output_path, "<project-output>"),
        ):
            redacted = redacted.replace(str(path), replacement)
            redacted = redacted.replace(path.as_posix(), replacement)
        return redacted
    return value
