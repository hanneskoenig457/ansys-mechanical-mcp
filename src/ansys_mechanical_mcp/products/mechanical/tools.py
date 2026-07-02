"""Controlled Mechanical helper operations.

These helpers intentionally operate on an injected Mechanical-like session object
instead of importing PyMechanical. Keep this module small until the MCP tool layer
needs a broader workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ansys_mechanical_mcp.core.tool_result import ToolResult

DEFAULT_LOG_LEVEL = "WARNING"
DEFAULT_PROGRESS_INTERVAL = 2000

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


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


def _get_required_method(session: Any, method_name: str) -> Any:
    method = getattr(session, method_name, None)
    if not callable(method):
        raise AttributeError(
            f"Mechanical session must provide a callable '{method_name}' method."
        )
    return method
