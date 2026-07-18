"""Controlled Mechanical helper operations.

These helpers intentionally operate on an injected Mechanical-like session object
instead of importing PyMechanical. Keep this module small until the MCP tool layer
needs a broader workflow.
"""

from __future__ import annotations

import json
import math
import textwrap
from pathlib import Path
from typing import Any

from ansys_mechanical_mcp.core.tool_result import ToolResult

DEFAULT_LOG_LEVEL = "WARNING"
DEFAULT_PROGRESS_INTERVAL = 2000

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})
_INSPECTION_FUNCTION_NAME = "__ansys_mechanical_mcp_inspect_model_v1"


_MECHANICAL_MODEL_INSPECTION_BODY = """
# Conservative read-only inspection using ExtAPI.DataModel.
import json


def _safe_getattr(obj, name):
    try:
        return getattr(obj, name)
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


def _analysis_metadata(analysis):
    object_id = _safe_int(_safe_getattr(analysis, "ObjectId"))
    if object_id is None:
        object_id = _safe_int(_safe_getattr(analysis, "Id"))

    analysis_type = _safe_text(_safe_getattr(analysis, "AnalysisType"))
    if analysis_type is None:
        analysis_type = _safe_text(_safe_getattr(analysis, "PhysicsType"))

    return {
        "name": (
            _safe_text(_safe_getattr(analysis, "Name"))
            or _safe_text(_safe_getattr(analysis, "SystemCaption"))
        ),
        "object_id": object_id,
        "type": analysis_type,
        "category": _safe_text(_safe_getattr(analysis, "DataModelObjectCategory")),
    }


data_model = ExtAPI.DataModel
project = _safe_getattr(data_model, "Project")
model = _safe_getattr(project, "Model")
analysis_list = (
    _safe_getattr(model, "Analyses")
    or _safe_getattr(model, "Environments")
    or _safe_getattr(data_model, "AnalysisList")
    or []
)

payload = {
    "product_version": _safe_text(_safe_getattr(project, "ProductVersion")),
    "analyses": [_analysis_metadata(analysis) for analysis in analysis_list],
}

""".strip()

MECHANICAL_MODEL_INSPECTION_SCRIPT = (
    f"def {_INSPECTION_FUNCTION_NAME}():\n"
    "    def _inspect():\n"
    f"{textwrap.indent(_MECHANICAL_MODEL_INSPECTION_BODY, '        ')}\n"
    "        return json.dumps(payload)\n"
    "    try:\n"
    "        return _inspect()\n"
    "    finally:\n"
    "        try:\n"
    f"            del globals()['{_INSPECTION_FUNCTION_NAME}']\n"
    "        except Exception:\n"
    "            pass\n"
    f"{_INSPECTION_FUNCTION_NAME}()"
)


def execute_mechanical_script(
    session: Any,
    *,
    script: str | None = None,
    script_file: str | Path | None = None,
    enable_logging: bool = False,
    log_level: str = DEFAULT_LOG_LEVEL,
    progress_interval: int = DEFAULT_PROGRESS_INTERVAL,
) -> ToolResult:
    """Run a controlled Mechanical script fallback on an injected session.

    The supplied session must provide PyMechanical-compatible
    ``run_python_script`` and ``run_python_script_from_file`` methods. This is a
    narrow escape hatch for Mechanical scripting and is not an MCP-facing
    arbitrary execution API.
    """

    validation_error = _validate_script_request(
        script=script,
        script_file=script_file,
        log_level=log_level,
        progress_interval=progress_interval,
    )
    if validation_error is not None:
        return validation_error

    call_options = {
        "enable_logging": enable_logging,
        "log_level": log_level.upper(),
        "progress_interval": progress_interval,
    }

    try:
        if script is not None:
            method = _get_required_method(session, "run_python_script")
            script_result = method(script, **call_options)
            execution_mode = "script"
        else:
            method = _get_required_method(session, "run_python_script_from_file")
            script_result = method(str(script_file), **call_options)
            execution_mode = "script_file"
    except AttributeError as exc:
        return ToolResult(
            success=False,
            message=str(exc),
            error="MECHANICAL_SESSION_METHOD_MISSING",
        )
    except Exception as exc:  # noqa: BLE001 - preserve Mechanical/transport failure details.
        return ToolResult(
            success=False,
            message=f"Mechanical script execution failed: {exc}",
            error="MECHANICAL_SCRIPT_EXECUTION_FAILED",
        )

    return ToolResult(
        success=True,
        message="Mechanical script executed successfully.",
        data={
            "execution_mode": execution_mode,
            "result": script_result,
            "enable_logging": enable_logging,
            "log_level": call_options["log_level"],
            "progress_interval": progress_interval,
        },
    )


def inspect_mechanical_model(session: Any) -> ToolResult:
    """Inspect basic Mechanical model metadata through ``ExtAPI.DataModel``.

    The injected session must provide PyMechanical-compatible
    ``run_python_script``. The Mechanical-side script returns JSON text, which
    this function parses and validates before exposing as a structured
    ``ToolResult``.
    """

    execution = execute_mechanical_script(
        session,
        script=MECHANICAL_MODEL_INSPECTION_SCRIPT,
    )
    if not execution.success:
        return ToolResult(
            success=False,
            message="Mechanical model inspection failed during script execution.",
            data={"execution": execution.to_dict()},
            error="MECHANICAL_MODEL_INSPECTION_EXECUTION_FAILED",
        )

    raw_result = execution.data.get("result")
    if not isinstance(raw_result, str) or not raw_result.strip():
        return ToolResult(
            success=False,
            message="Mechanical model inspection did not return JSON text.",
            data={"raw_result": _json_diagnostic(raw_result)},
            error="MECHANICAL_MODEL_INSPECTION_PARSE_FAILED",
        )

    try:
        payload = json.loads(raw_result)
        inspection_data = _normalize_model_inspection_payload(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return ToolResult(
            success=False,
            message=f"Mechanical model inspection returned invalid JSON: {exc}",
            data={"raw_result": raw_result},
            error="MECHANICAL_MODEL_INSPECTION_PARSE_FAILED",
        )

    return ToolResult(
        success=True,
        message="Mechanical model inspected successfully.",
        data=inspection_data,
    )


def _validate_script_request(
    *,
    script: str | None,
    script_file: str | Path | None,
    log_level: str,
    progress_interval: int,
) -> ToolResult | None:
    has_script = script is not None
    has_script_file = script_file is not None

    if has_script == has_script_file:
        return ToolResult(
            success=False,
            message="Provide exactly one of 'script' or 'script_file'.",
            error="MECHANICAL_SCRIPT_INPUT_ERROR",
        )

    if has_script and not script.strip():
        return ToolResult(
            success=False,
            message="'script' must not be empty.",
            error="MECHANICAL_SCRIPT_INPUT_ERROR",
        )

    if has_script_file and not str(script_file).strip():
        return ToolResult(
            success=False,
            message="'script_file' must not be empty.",
            error="MECHANICAL_SCRIPT_INPUT_ERROR",
        )

    if has_script_file and not Path(script_file).is_file():
        return ToolResult(
            success=False,
            message="'script_file' must point to an existing file.",
            error="MECHANICAL_SCRIPT_INPUT_ERROR",
        )

    if log_level.upper() not in _VALID_LOG_LEVELS:
        return ToolResult(
            success=False,
            message="'log_level' must be one of DEBUG, INFO, WARNING, or ERROR.",
            error="MECHANICAL_SCRIPT_INPUT_ERROR",
        )

    if progress_interval <= 0:
        return ToolResult(
            success=False,
            message="'progress_interval' must be a positive integer.",
            error="MECHANICAL_SCRIPT_INPUT_ERROR",
        )

    return None


def _normalize_model_inspection_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("inspection payload must be a JSON object")

    analyses = payload.get("analyses")
    if not isinstance(analyses, list):
        raise ValueError("'analyses' must be a list")

    normalized_analyses = []
    for index, analysis in enumerate(analyses):
        if not isinstance(analysis, dict):
            raise ValueError(f"'analyses[{index}]' must be a JSON object")

        normalized_analyses.append(
            {
                "name": analysis.get("name"),
                "object_id": analysis.get("object_id"),
                "type": analysis.get("type"),
                "category": analysis.get("category"),
            }
        )

    return {
        "product_version": payload.get("product_version"),
        "analyses": normalized_analyses,
    }


def _get_required_method(session: Any, method_name: str) -> Any:
    method = getattr(session, method_name, None)
    if not callable(method):
        raise AttributeError(f"Mechanical session must provide a callable '{method_name}' method.")
    return method


def _json_diagnostic(value: Any) -> Any:
    """Return a JSON-compatible diagnostic without leaking native proxy objects."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"python_type": "float", "text": str(value)}
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    try:
        text = str(value)
    except Exception:  # pragma: no cover - defensive around native proxy repr/str.
        text = None
    return {"python_type": type(value).__name__, "text": text}
