"""PyDPF result metadata helpers.

This module imports PyDPF lazily so unit tests can inject model factories and
run without an Ansys installation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ansys_mechanical_mcp.core.tool_result import ToolResult


DpfModelFactory = Callable[[str], Any]


@dataclass(slots=True)
class ResultSummaryRequest:
    """Request for extracting a basic result summary from a result file."""

    result_file: str
    result_name: str | None = None


def summarize_result_file(
    result_file: str | Path,
    *,
    model_factory: DpfModelFactory | None = None,
) -> ToolResult:
    """Return a basic PyDPF metadata summary for an existing result file."""

    validation_error = _validate_result_file(result_file)
    if validation_error is not None:
        return validation_error

    result_path = Path(result_file)
    result_path_text = str(result_path)

    if model_factory is None:
        try:
            model_factory = _resolve_dpf_model_factory()
        except ImportError:
            return ToolResult(
                success=False,
                message=(
                    "PyDPF is not installed. Install ansys-dpf-core or the project's "
                    "'ansys' extra to summarize result files."
                ),
                error="DPF_RESULT_SUMMARY_DEPENDENCY_MISSING",
            )

    try:
        model = model_factory(result_path_text)
    except Exception as exc:  # noqa: BLE001 - expose DPF file/server/license details.
        return ToolResult(
            success=False,
            message=f"Failed to load result file with PyDPF: {exc}",
            data={"result_file": result_path_text},
            error="DPF_RESULT_SUMMARY_MODEL_LOAD_FAILED",
        )

    try:
        summary = _extract_model_summary(model)
    except Exception as exc:  # noqa: BLE001 - keep real DPF metadata failures visible.
        return ToolResult(
            success=False,
            message=f"Failed to extract PyDPF result metadata: {exc}",
            data={"result_file": result_path_text},
            error="DPF_RESULT_SUMMARY_METADATA_FAILED",
        )

    return ToolResult(
        success=True,
        message="PyDPF result metadata summary extracted successfully.",
        data={
            "result_file": result_path_text,
            **summary,
        },
    )


def _validate_result_file(result_file: str | Path) -> ToolResult | None:
    if result_file is None:
        return ToolResult(
            success=False,
            message="'result_file' must not be empty.",
            error="DPF_RESULT_SUMMARY_INPUT_ERROR",
        )

    result_path = Path(result_file)
    if not str(result_path).strip():
        return ToolResult(
            success=False,
            message="'result_file' must not be empty.",
            error="DPF_RESULT_SUMMARY_INPUT_ERROR",
        )

    if not result_path.exists():
        return ToolResult(
            success=False,
            message=f"Result file does not exist: {result_path}",
            data={"result_file": str(result_path)},
            error="DPF_RESULT_SUMMARY_INPUT_ERROR",
        )

    return None


def _resolve_dpf_model_factory() -> DpfModelFactory:
    from ansys.dpf.core import Model

    return Model


def _extract_model_summary(model: Any) -> dict[str, Any]:
    metadata = _optional_attr(model, "metadata")
    result_info = _optional_attr(metadata, "result_info")
    meshed_region = _optional_attr(metadata, "meshed_region")
    time_freq_support = _optional_attr(metadata, "time_freq_support")
    results = _optional_attr(model, "results")

    return {
        "result_info": _extract_result_info_summary(result_info),
        "mesh": _extract_mesh_summary(meshed_region),
        "time_freq": _extract_time_freq_summary(time_freq_support),
        "available_results": _extract_available_result_names(results),
    }


def _extract_result_info_summary(result_info: Any) -> dict[str, Any]:
    if result_info is None:
        return {}

    fields = (
        "analysis_type",
        "physics_type",
        "n_results",
        "unit_system",
        "unit_system_name",
        "solver_version",
        "solver_date",
        "solver_time",
        "user_name",
        "job_name",
        "product_name",
        "main_title",
        "cyclic_symmetry_type",
        "has_cyclic",
    )

    summary: dict[str, Any] = {}
    for field in fields:
        value = _optional_attr(result_info, field)
        if value is not None:
            summary[field] = _json_value(value)
    return summary


def _extract_mesh_summary(meshed_region: Any) -> dict[str, Any]:
    if meshed_region is None:
        return {}

    nodes = _optional_attr(meshed_region, "nodes")
    elements = _optional_attr(meshed_region, "elements")

    summary: dict[str, Any] = {
        "node_count": _entity_count(nodes, "n_nodes"),
        "element_count": _entity_count(elements, "n_elements"),
    }

    unit = _optional_attr(meshed_region, "unit")
    if unit is not None:
        summary["unit"] = _json_value(unit)

    return summary


def _extract_time_freq_summary(time_freq_support: Any) -> dict[str, Any]:
    if time_freq_support is None:
        return {}

    n_sets = _optional_attr(time_freq_support, "n_sets")
    if n_sets is None:
        return {}

    return {"n_sets": _json_int(n_sets)}


def _extract_available_result_names(results: Any) -> list[str]:
    if results is None:
        return []

    names: set[str] = set()

    for result in _iter_results(results):
        name = _first_text_attr(result, ("name", "scripting_name", "operator_name"))
        if name:
            names.add(name)

    for name in dir(results):
        if not _is_candidate_result_name(name):
            continue
        result = _optional_attr(results, name)
        if _looks_like_result_provider(result):
            names.add(name)

    return sorted(names)


def _iter_results(results: Any) -> list[Any]:
    try:
        return list(results)
    except TypeError:
        return []


def _first_text_attr(obj: Any, names: tuple[str, ...]) -> str | None:
    for name in names:
        value = _optional_attr(obj, name)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _is_candidate_result_name(name: str) -> bool:
    excluded_names = {
        "connector",
        "mesh_by_default",
        "result_info",
        "server",
    }
    return name.isidentifier() and not name.startswith("_") and name not in excluded_names


def _looks_like_result_provider(value: Any) -> bool:
    if value is None or isinstance(value, str | bytes | int | float | bool):
        return False

    if value.__class__.__name__ == "Result":
        return True

    return callable(_optional_attr(value, "eval"))


def _entity_count(container: Any, count_attr: str) -> int | None:
    if container is None:
        return None

    value = _optional_attr(container, count_attr)
    if value is not None:
        return _json_int(value)

    try:
        return _json_int(len(container))
    except TypeError:
        return None


def _optional_attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None

    try:
        return getattr(obj, name)
    except AttributeError:
        return None


def _json_int(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("boolean values are not valid integer counts")
    return int(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)
