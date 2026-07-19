"""Environment discovery for the MCP server."""

from __future__ import annotations

import os
import platform
import shutil
import sys
import sysconfig
from collections.abc import Callable, Iterable, Mapping
from importlib import metadata
from typing import Any

from ansys_mechanical_mcp.core.tool_result import ToolResult

MINIMUM_PYTHON = (3, 10)
REQUIRED_PACKAGES = ("mcp",)
OPTIONAL_PACKAGES = (
    "ansys-mechanical-core",
    "ansys-dpf-core",
)
MECHANICAL_EXECUTABLES = ("ansys-mechanical", "mechanical-env")
ANSYS_ENV_PREFIXES = ("AWP_ROOT",)
ANSYS_ENV_NAMES = ("ANSYSLMD_LICENSE_FILE",)

VersionLookup = Callable[[str], str]
ExecutableLookup = Callable[[str], str | None]


def collect_environment(
    *,
    required_packages: Iterable[str] = REQUIRED_PACKAGES,
    optional_packages: Iterable[str] = OPTIONAL_PACKAGES,
    executable_names: Iterable[str] = MECHANICAL_EXECUTABLES,
    environ: Mapping[str, str] | None = None,
    version_lookup: VersionLookup = metadata.version,
    executable_lookup: ExecutableLookup = shutil.which,
    python_version_info: tuple[int, int, int] | None = None,
    python_scripts_path: str | None = None,
    platform_system_name: str | None = None,
) -> dict[str, Any]:
    """Collect JSON-compatible environment details.

    The check uses package metadata and executable lookup only. It does not import
    PyMechanical, PyDPF, or Ansys modules, which keeps it safe on machines without
    Ansys products installed.
    """
    current_python = python_version_info or sys.version_info[:3]
    env = environ if environ is not None else os.environ
    required = tuple(required_packages)
    optional = tuple(optional_packages)
    scripts_path = python_scripts_path or sysconfig.get_path("scripts")
    system_name = platform_system_name or platform.system()

    required_status = {name: _package_status(name, version_lookup) for name in required}
    optional_status = {name: _package_status(name, version_lookup) for name in optional}
    executable_status = {
        name: _pymechanical_cli_status(
            name,
            executable_lookup=executable_lookup,
            python_scripts_path=scripts_path,
            platform_system_name=system_name,
        )
        for name in executable_names
    }

    return {
        "python": {
            "supported": current_python >= MINIMUM_PYTHON,
            "minimum": _version_tuple_to_string(MINIMUM_PYTHON),
            "version": platform.python_version(),
            "version_info": list(current_python),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "platform": {
            "system": system_name,
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "packages": {
            "required": required_status,
            "optional": optional_status,
            "missing_required": [
                name for name, status in required_status.items() if not status["installed"]
            ],
            "missing_optional": [
                name for name, status in optional_status.items() if not status["installed"]
            ],
        },
        "executables": executable_status,
        "executable_diagnostic_scope": (
            "PyMechanical Python CLI commands only; this does not prove that the Mechanical "
            "product or a license is installed."
        ),
        "mechanical_runtime": {
            "product_installation": "not_checked",
            "license": "not_checked",
            "grpc_connectivity": "not_checked",
        },
        "ansys_environment": _ansys_environment(env),
    }


def check_environment() -> ToolResult:
    """Return a structured environment check result."""
    data = collect_environment()
    missing_required = data["packages"]["missing_required"]
    python_supported = data["python"]["supported"]
    mcp_server_ready = python_supported and not missing_required
    ansys_workflow_ready = mcp_server_ready and not data["packages"]["missing_optional"]

    data["ready"] = {
        "mcp_server": mcp_server_ready,
        "ansys_workflows": ansys_workflow_ready,
        "ansys_workflows_scope": "python_dependencies_only",
        "mechanical_product": None,
        "mechanical_license": None,
        "mechanical_runtime": None,
    }

    if not python_supported:
        return ToolResult(
            success=False,
            message="Python version is below the supported minimum.",
            data=data,
            error="unsupported_python",
        )

    if missing_required:
        return ToolResult(
            success=False,
            message="Environment is missing required MCP server dependencies.",
            data=data,
            error="missing_required_packages",
        )

    if not ansys_workflow_ready:
        return ToolResult(
            success=True,
            message="MCP base environment is usable; Ansys workflow dependencies are incomplete.",
            data=data,
        )

    return ToolResult(
        success=True,
        message=(
            "Python dependencies for the v0.1 Ansys Mechanical workflow are installed; "
            "the Mechanical product, license, and runtime connectivity were not checked."
        ),
        data=data,
    )


def _package_status(name: str, version_lookup: VersionLookup) -> dict[str, str | bool | None]:
    try:
        version = version_lookup(name)
    except metadata.PackageNotFoundError:
        return {"installed": False, "version": None}
    except Exception as exc:  # pragma: no cover - defensive around third-party metadata
        return {"installed": False, "version": None, "error": str(exc)}

    return {"installed": True, "version": version}


def _pymechanical_cli_status(
    name: str,
    *,
    executable_lookup: ExecutableLookup,
    python_scripts_path: str,
    platform_system_name: str,
) -> dict[str, str | bool | None]:
    """Locate a PyMechanical CLI on PATH or beside the running venv Python."""
    applicable = not (name == "mechanical-env" and platform_system_name != "Linux")
    if not applicable:
        return {
            "available": False,
            "path": None,
            "source": None,
            "kind": "pymechanical_cli",
            "applicable": False,
            "note": "mechanical-env is a Linux-only PyMechanical embedding helper.",
        }

    path = executable_lookup(name)
    source = "path" if path is not None else None
    if path is None:
        scripts_candidate = os.path.join(python_scripts_path, name)
        path = executable_lookup(scripts_candidate)
        if (
            path is None
            and platform_system_name == "Windows"
            and not scripts_candidate.lower().endswith(".exe")
        ):
            # Python 3.10/3.11 do not apply PATHEXT when shutil.which() receives
            # a command containing a directory component. Check pip's Windows
            # console-script suffix explicitly while retaining the injectable
            # one-argument lookup used by environment tests.
            path = executable_lookup(f"{scripts_candidate}.exe")
        if path is not None:
            source = "python_scripts"

    return {
        "available": path is not None,
        "path": path,
        "source": source,
        "kind": "pymechanical_cli",
        "applicable": True,
        "note": None,
    }


def _ansys_environment(environ: Mapping[str, str]) -> dict[str, Any]:
    names = sorted(
        name
        for name in environ
        if name in ANSYS_ENV_NAMES or any(name.startswith(prefix) for prefix in ANSYS_ENV_PREFIXES)
    )
    return {
        "detected_variables": names,
        "license_variable_present": "ANSYSLMD_LICENSE_FILE" in environ,
    }


def _version_tuple_to_string(version: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in version)
