from importlib import metadata

from ansys_mechanical_mcp.core.environment import collect_environment


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
