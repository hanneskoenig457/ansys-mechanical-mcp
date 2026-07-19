import json
import os
from importlib import metadata

import pytest

import ansys_mechanical_mcp.core.environment as environment_module
from ansys_mechanical_mcp.core.environment import check_environment, collect_environment


def test_collect_environment_reports_supported_python_and_packages() -> None:
    def version_lookup(name: str) -> str:
        versions = {
            "mcp": "1.0.0",
            "ansys-mechanical-core": "0.12.0",
        }
        if name not in versions:
            raise metadata.PackageNotFoundError(name)
        return versions[name]

    data = collect_environment(
        optional_packages=("ansys-mechanical-core", "ansys-dpf-core"),
        executable_names=("ansys-mechanical",),
        environ={"AWP_ROOT261": "/opt/ansys_inc/v261", "ANSYSLMD_LICENSE_FILE": "1055@host"},
        version_lookup=version_lookup,
        executable_lookup=lambda name: f"/usr/bin/{name}",
        python_version_info=(3, 12, 1),
    )

    assert data["python"]["supported"] is True
    assert data["packages"]["required"]["mcp"] == {"installed": True, "version": "1.0.0"}
    assert data["packages"]["optional"]["ansys-dpf-core"] == {
        "installed": False,
        "version": None,
    }
    assert data["packages"]["missing_optional"] == ["ansys-dpf-core"]
    assert data["executables"]["ansys-mechanical"]["available"] is True
    assert data["executables"]["ansys-mechanical"]["source"] == "path"
    assert data["executables"]["ansys-mechanical"]["kind"] == "pymechanical_cli"
    assert data["ansys_environment"]["detected_variables"] == [
        "ANSYSLMD_LICENSE_FILE",
        "AWP_ROOT261",
    ]
    assert data["ansys_environment"]["license_variable_present"] is True


def test_collect_environment_reports_missing_required_package() -> None:
    def version_lookup(name: str) -> str:
        raise metadata.PackageNotFoundError(name)

    data = collect_environment(
        optional_packages=(),
        executable_names=(),
        environ={},
        version_lookup=version_lookup,
        python_version_info=(3, 10, 0),
    )

    assert data["packages"]["missing_required"] == ["mcp"]


def test_collect_environment_reports_unsupported_python() -> None:
    data = collect_environment(
        required_packages=(),
        optional_packages=(),
        executable_names=(),
        environ={},
        python_version_info=(3, 9, 18),
    )

    assert data["python"]["supported"] is False


def test_executable_diagnostic_falls_back_to_running_python_scripts_directory() -> None:
    calls = []
    scripts_path = os.path.join("repo", ".venv", "Scripts")
    candidate = os.path.join(scripts_path, "ansys-mechanical")

    def executable_lookup(name: str) -> str | None:
        calls.append(name)
        if name == f"{candidate}.exe":
            return name
        return None

    data = collect_environment(
        required_packages=(),
        optional_packages=(),
        executable_names=("ansys-mechanical",),
        environ={},
        executable_lookup=executable_lookup,
        python_scripts_path=scripts_path,
        platform_system_name="Windows",
    )

    assert calls == ["ansys-mechanical", candidate, f"{candidate}.exe"]
    assert data["executables"]["ansys-mechanical"] == {
        "available": True,
        "path": f"{candidate}.exe",
        "source": "python_scripts",
        "kind": "pymechanical_cli",
        "applicable": True,
        "note": None,
    }
    assert data["platform"]["system"] == "Windows"


def test_executable_diagnostic_reports_complete_miss_without_product_claim() -> None:
    data = collect_environment(
        required_packages=(),
        optional_packages=(),
        executable_names=("ansys-mechanical",),
        environ={},
        executable_lookup=lambda _name: None,
        python_scripts_path="/repo/.venv/bin",
        platform_system_name="Linux",
    )

    assert data["executables"]["ansys-mechanical"]["available"] is False
    assert data["executables"]["ansys-mechanical"]["source"] is None
    assert "does not prove" in data["executable_diagnostic_scope"]
    assert json.loads(json.dumps(data, allow_nan=False)) == data


def test_mechanical_env_is_marked_not_applicable_on_windows_without_lookup() -> None:
    calls = []
    data = collect_environment(
        required_packages=(),
        optional_packages=(),
        executable_names=("mechanical-env",),
        environ={},
        executable_lookup=lambda name: calls.append(name),
        platform_system_name="Windows",
    )

    assert calls == []
    assert data["executables"]["mechanical-env"] == {
        "available": False,
        "path": None,
        "source": None,
        "kind": "pymechanical_cli",
        "applicable": False,
        "note": "mechanical-env is a Linux-only PyMechanical embedding helper.",
    }


def test_ready_status_only_claims_python_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = collect_environment(
        required_packages=(),
        optional_packages=(),
        executable_names=(),
        environ={},
        python_version_info=(3, 12, 0),
    )
    monkeypatch.setattr(environment_module, "collect_environment", lambda: data)

    result = check_environment()

    assert result.success is True
    assert result.data["ready"] == {
        "mcp_server": True,
        "ansys_workflows": True,
        "ansys_workflows_scope": "python_dependencies_only",
        "mechanical_product": None,
        "mechanical_license": None,
        "mechanical_runtime": None,
    }
    assert result.data["mechanical_runtime"] == {
        "product_installation": "not_checked",
        "license": "not_checked",
        "grpc_connectivity": "not_checked",
    }
    assert "were not checked" in result.message
