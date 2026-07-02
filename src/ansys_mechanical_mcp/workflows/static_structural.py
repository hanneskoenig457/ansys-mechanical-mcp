"""Static Structural workflow helpers.

The helpers in this module operate on injected Mechanical-like sessions. They
intentionally avoid importing PyMechanical so unit tests can run without an
Ansys installation or license.
"""

from __future__ import annotations

import json
from typing import Any

from ansys_mechanical_mcp.core.tool_result import ToolResult


STATIC_STRUCTURAL_SOLVE_SCRIPT_TEMPLATE = r"""
# Solve one existing Static Structural analysis selected by Python-side inputs.
import json

TARGET_NAME = __TARGET_NAME__
TARGET_OBJECT_ID = __TARGET_OBJECT_ID__
WAIT_FOR_SOLVE = __WAIT_FOR_SOLVE__


def _safe_getattr(obj, name):
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _safe_call(obj, name):
    method = _safe_getattr(obj, name)
    if not callable(method):
        return None
    try:
        return method()
    except Exception:
        return None


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


def _compact_text(value):
    text = _safe_text(value)
    if text is None:
        return ""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _analysis_type_text(analysis):
    analysis_type = (
        _safe_text(_safe_getattr(analysis, "AnalysisType"))
        or _safe_text(_safe_getattr(analysis, "PhysicsType"))
        or _safe_text(_safe_getattr(analysis, "Type"))
    )
    if analysis_type is not None:
        return analysis_type

    dotnet_type = _safe_call(analysis, "GetType")
    return _safe_text(_safe_getattr(dotnet_type, "Name")) or _safe_text(dotnet_type)


def _analysis_metadata(analysis):
    object_id = _safe_int(_safe_getattr(analysis, "ObjectId"))
    if object_id is None:
        object_id = _safe_int(_safe_getattr(analysis, "Id"))

    return {
        "name": _safe_text(_safe_getattr(analysis, "Name")),
        "object_id": object_id,
        "type": _analysis_type_text(analysis),
        "caption": (
            _safe_text(_safe_getattr(analysis, "Caption"))
            or _safe_text(_safe_getattr(analysis, "SystemCaption"))
        ),
    }


def _is_static_structural(meta):
    for value in (meta.get("type"), meta.get("name"), meta.get("caption")):
        compact = _compact_text(value)
        if "staticstructural" in compact:
            return True
        if "static" in compact and "structural" in compact:
            return True
    return False


def _matches_selector(meta):
    if TARGET_OBJECT_ID is not None:
        return meta.get("object_id") == TARGET_OBJECT_ID

    if TARGET_NAME is not None:
        target = _safe_text(TARGET_NAME).lower()
        for value in (meta.get("name"), meta.get("caption")):
            text = _safe_text(value)
            if text is not None and text.lower() == target:
                return True
        return False

    return True


data_model = ExtAPI.DataModel
project = _safe_getattr(data_model, "Project")
model = _safe_getattr(project, "Model")
analysis_list = (
    _safe_getattr(model, "Analyses")
    or _safe_getattr(model, "Environments")
    or _safe_getattr(data_model, "AnalysisList")
    or []
)

entries = []
for analysis in analysis_list:
    meta = _analysis_metadata(analysis)
    entries.append(
        {
            "analysis": analysis,
            "metadata": meta,
            "matches_selector": _matches_selector(meta),
            "is_static_structural": _is_static_structural(meta),
        }
    )

selector_matches = [entry for entry in entries if entry["matches_selector"]]
static_matches = [entry for entry in selector_matches if entry["is_static_structural"]]

if TARGET_OBJECT_ID is not None or TARGET_NAME is not None:
    if not selector_matches:
        payload = {
            "status": "not_found",
            "selector": {"name": TARGET_NAME, "object_id": TARGET_OBJECT_ID},
            "analyses": [entry["metadata"] for entry in entries],
        }
    elif not static_matches:
        payload = {
            "status": "not_static_structural",
            "selector": {"name": TARGET_NAME, "object_id": TARGET_OBJECT_ID},
            "analyses": [entry["metadata"] for entry in selector_matches],
        }
    elif len(static_matches) > 1:
        payload = {
            "status": "multiple_matches",
            "selector": {"name": TARGET_NAME, "object_id": TARGET_OBJECT_ID},
            "analyses": [entry["metadata"] for entry in static_matches],
        }
    else:
        selected = static_matches[0]
        selected["analysis"].Solve(WAIT_FOR_SOLVE)
        payload = {
            "status": "ok",
            "selector": {"name": TARGET_NAME, "object_id": TARGET_OBJECT_ID},
            "analysis": selected["metadata"],
            "solved": True,
            "wait": WAIT_FOR_SOLVE,
        }
else:
    if not static_matches:
        payload = {
            "status": "not_found",
            "selector": {"name": None, "object_id": None},
            "analyses": [entry["metadata"] for entry in entries],
        }
    elif len(static_matches) > 1:
        payload = {
            "status": "multiple_matches",
            "selector": {"name": None, "object_id": None},
            "analyses": [entry["metadata"] for entry in static_matches],
        }
    else:
        selected = static_matches[0]
        selected["analysis"].Solve(WAIT_FOR_SOLVE)
        payload = {
            "status": "ok",
            "selector": {"name": None, "object_id": None},
            "analysis": selected["metadata"],
            "solved": True,
            "wait": WAIT_FOR_SOLVE,
        }

json.dumps(payload)
""".strip()


def solve_static_structural_analysis(
    session: Any,
    *,
    name: str | None = None,
    object_id: int | None = None,
    wait: bool = True,
) -> ToolResult:
    """Solve one existing Static Structural analysis through Mechanical scripting.

    The injected session must provide a PyMechanical-compatible
    ``run_python_script`` method. This helper selects an existing analysis only;
    it does not create analyses, fake solver status, or infer completion beyond
    the return from ``analysis.Solve(wait)`` inside Mechanical.
    """

    validation_error = _validate_solve_request(name=name, object_id=object_id, wait=wait)
    if validation_error is not None:
        return validation_error

    script = _build_static_structural_solve_script(
        name=name,
        object_id=object_id,
        wait=wait,
    )

    try:
        run_python_script = _get_required_method(session, "run_python_script")
        raw_result = run_python_script(script)
    except AttributeError as exc:
        return ToolResult(
            success=False,
            message=str(exc),
            error="STATIC_STRUCTURAL_SOLVE_SESSION_METHOD_MISSING",
        )
    except Exception as exc:  # noqa: BLE001 - expose Mechanical/script/solver failure details.
        return ToolResult(
            success=False,
            message=f"Static Structural solve script execution failed: {exc}",
            error="STATIC_STRUCTURAL_SOLVE_EXECUTION_FAILED",
        )

    payload_result = _parse_static_structural_solve_result(raw_result)
    if not payload_result.success:
        return payload_result

    payload = payload_result.data["payload"]
    status = payload.get("status")
    if status == "ok":
        analysis = payload["analysis"]
        return ToolResult(
            success=True,
            message="Static Structural analysis solved successfully.",
            data={
                "analysis": analysis,
                "selector": payload.get("selector", {}),
                "solved": True,
                "wait": payload.get("wait"),
            },
        )

    return _solve_status_error(payload)


def _validate_solve_request(
    *,
    name: str | None,
    object_id: int | None,
    wait: bool,
) -> ToolResult | None:
    if name is not None and object_id is not None:
        return ToolResult(
            success=False,
            message="Provide at most one selector: 'name' or 'object_id'.",
            error="STATIC_STRUCTURAL_SOLVE_INPUT_ERROR",
        )

    if name is not None and not name.strip():
        return ToolResult(
            success=False,
            message="'name' must not be empty.",
            error="STATIC_STRUCTURAL_SOLVE_INPUT_ERROR",
        )

    if object_id is not None and (isinstance(object_id, bool) or not isinstance(object_id, int)):
        return ToolResult(
            success=False,
            message="'object_id' must be an integer.",
            error="STATIC_STRUCTURAL_SOLVE_INPUT_ERROR",
        )

    if not isinstance(wait, bool):
        return ToolResult(
            success=False,
            message="'wait' must be a boolean.",
            error="STATIC_STRUCTURAL_SOLVE_INPUT_ERROR",
        )

    if wait is not True:
        return ToolResult(
            success=False,
            message="'wait=False' is not supported until asynchronous solve status is implemented.",
            error="STATIC_STRUCTURAL_SOLVE_INPUT_ERROR",
        )

    return None


def _build_static_structural_solve_script(
    *,
    name: str | None,
    object_id: int | None,
    wait: bool,
) -> str:
    return (
        STATIC_STRUCTURAL_SOLVE_SCRIPT_TEMPLATE.replace("__TARGET_NAME__", _python_literal(name))
        .replace("__TARGET_OBJECT_ID__", _python_literal(object_id))
        .replace("__WAIT_FOR_SOLVE__", _python_literal(wait))
    )


def _python_literal(value: Any) -> str:
    if value is None:
        return "None"
    return repr(value)


def _parse_static_structural_solve_result(raw_result: Any) -> ToolResult:
    if not isinstance(raw_result, str) or not raw_result.strip():
        return ToolResult(
            success=False,
            message="Static Structural solve script did not return JSON text.",
            data={"raw_result": raw_result},
            error="STATIC_STRUCTURAL_SOLVE_PARSE_FAILED",
        )

    try:
        payload = json.loads(raw_result)
        normalized = _normalize_static_structural_solve_payload(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return ToolResult(
            success=False,
            message=f"Static Structural solve script returned invalid JSON: {exc}",
            data={"raw_result": raw_result},
            error="STATIC_STRUCTURAL_SOLVE_PARSE_FAILED",
        )

    return ToolResult(
        success=True,
        message="Static Structural solve script returned a valid payload.",
        data={"payload": normalized},
    )


def _normalize_static_structural_solve_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("solve payload must be a JSON object")

    status = payload.get("status")
    if not isinstance(status, str):
        raise ValueError("'status' must be a string")

    normalized: dict[str, Any] = {
        "status": status,
        "selector": _normalize_selector(payload.get("selector")),
    }

    if status == "ok":
        if payload.get("solved") is not True:
            raise ValueError("'solved' must be true after analysis.Solve returns")
        normalized["analysis"] = _normalize_analysis_metadata(payload.get("analysis"))
        normalized["solved"] = True
        normalized["wait"] = payload.get("wait")
        return normalized

    if status in {"not_found", "multiple_matches", "not_static_structural"}:
        normalized["analyses"] = _normalize_analysis_list(payload.get("analyses"))
        return normalized

    raise ValueError(f"unsupported solve status: {status}")


def _normalize_selector(selector: Any) -> dict[str, Any]:
    if selector is None:
        return {}
    if not isinstance(selector, dict):
        raise ValueError("'selector' must be a JSON object")
    return {
        "name": selector.get("name"),
        "object_id": selector.get("object_id"),
    }


def _normalize_analysis_list(analyses: Any) -> list[dict[str, Any]]:
    if not isinstance(analyses, list):
        raise ValueError("'analyses' must be a list")
    return [_normalize_analysis_metadata(analysis) for analysis in analyses]


def _normalize_analysis_metadata(analysis: Any) -> dict[str, Any]:
    if not isinstance(analysis, dict):
        raise ValueError("analysis metadata must be a JSON object")
    return {
        "name": analysis.get("name"),
        "object_id": analysis.get("object_id"),
        "type": analysis.get("type"),
        "caption": analysis.get("caption"),
    }


def _solve_status_error(payload: dict[str, Any]) -> ToolResult:
    status = payload["status"]
    analyses = payload.get("analyses", [])

    if status == "not_found":
        return ToolResult(
            success=False,
            message="No matching Static Structural analysis was found.",
            data={
                "selector": payload.get("selector", {}),
                "analyses": analyses,
            },
            error="STATIC_STRUCTURAL_ANALYSIS_NOT_FOUND",
        )

    if status == "multiple_matches":
        return ToolResult(
            success=False,
            message=(
                "Multiple matching Static Structural analyses were found; "
                "provide a unique name or object_id."
            ),
            data={
                "selector": payload.get("selector", {}),
                "analyses": analyses,
            },
            error="STATIC_STRUCTURAL_ANALYSIS_MULTIPLE_MATCHES",
        )

    if status == "not_static_structural":
        return ToolResult(
            success=False,
            message="The selected analysis is not a Static Structural analysis.",
            data={
                "selector": payload.get("selector", {}),
                "analyses": analyses,
            },
            error="STATIC_STRUCTURAL_ANALYSIS_NOT_STATIC_STRUCTURAL",
        )

    return ToolResult(
        success=False,
        message=f"Unsupported Static Structural solve status: {status}",
        data=payload,
        error="STATIC_STRUCTURAL_SOLVE_PARSE_FAILED",
    )


def _get_required_method(session: Any, method_name: str) -> Any:
    method = getattr(session, method_name, None)
    if not callable(method):
        raise AttributeError(
            f"Mechanical session must provide a callable '{method_name}' method."
        )
    return method
