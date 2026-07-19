import json
from pathlib import Path

import pytest

from ansys_mechanical_mcp.products.mechanical.transport import (
    discover_start_transport,
    is_loopback_host,
    is_wnua_loopback_host,
    platform_secure_transport,
)


def _windows_mechanical_executable(tmp_path: Path, revision: int) -> Path:
    executable = (
        tmp_path
        / f"v{revision}"
        / "aisol"
        / "bin"
        / "winx64"
        / "AnsysWBU.exe"
    )
    executable.parent.mkdir(parents=True)
    executable.write_text("fake executable", encoding="utf-8")
    return executable


def test_discover_start_transport_reports_supported_modern_revision(tmp_path: Path) -> None:
    executable = _windows_mechanical_executable(tmp_path, 261)
    grpc_calls = []

    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: str(executable),
        version_lookup=lambda product, path: 261,
        grpc_support_lookup=lambda revision: grpc_calls.append(revision) or True,
    )

    assert result.status == "supported"
    assert result.detected_revision == 261
    assert result.secure_transport_supported is True
    assert result.executable_path == str(executable)
    assert grpc_calls == []


@pytest.mark.parametrize("revision", [231, 241])
def test_discover_start_transport_rejects_revision_outside_client_support(
    tmp_path: Path,
    revision: int,
) -> None:
    executable = _windows_mechanical_executable(tmp_path, revision)

    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: str(executable),
        version_lookup=lambda product, path: revision,
        grpc_support_lookup=lambda revision: False,
    )

    assert result.status == "incompatible"
    assert result.detected_revision == revision
    assert "revision 242 or later" in result.message


def test_discover_start_transport_uses_pymechanical_service_pack_check(
    tmp_path: Path,
) -> None:
    executable = _windows_mechanical_executable(tmp_path, 251)
    builddate = tmp_path / "v251" / "builddate.txt"
    builddate.write_text("Release 2025 R1 SP03\nR251RC2P03\n", encoding="utf-8")
    grpc_calls = []

    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: str(executable),
        version_lookup=lambda product, path: 251,
        grpc_support_lookup=lambda revision: grpc_calls.append(revision) or False,
    )

    assert result.status == "unsupported"
    assert result.secure_transport_supported is False
    assert result.required_secure_service_pack == "SP04"
    assert result.detected_service_pack == "SP03"
    assert result.builddate_path == str(builddate)
    assert result.source == "exact_executable_pymechanical_cross_check"
    assert grpc_calls == [251]
    assert json.loads(json.dumps(result.to_dict(), allow_nan=False)) == result.to_dict()


def test_discover_start_transport_accepts_matching_supported_service_pack(
    tmp_path: Path,
) -> None:
    executable = _windows_mechanical_executable(tmp_path, 251)
    builddate = tmp_path / "v251" / "builddate.txt"
    builddate.write_text("Release 2025 R1 SP04\nBuild\n", encoding="utf-8")

    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: str(executable),
        version_lookup=lambda product, path: 251,
        grpc_support_lookup=lambda revision: True,
    )

    assert result.status == "supported"
    assert result.secure_transport_supported is True


def test_discover_start_transport_does_not_downgrade_without_build_metadata(
    tmp_path: Path,
) -> None:
    executable = _windows_mechanical_executable(tmp_path, 251)
    grpc_calls = []

    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: str(executable),
        version_lookup=lambda product, path: 251,
        grpc_support_lookup=lambda revision: grpc_calls.append(revision) or False,
    )

    assert result.status == "unknown"
    assert result.secure_transport_supported is None
    assert result.required_secure_service_pack == "SP04"
    assert grpc_calls == []


def test_discover_start_transport_does_not_treat_unparseable_build_as_old_sp(
    tmp_path: Path,
) -> None:
    executable = _windows_mechanical_executable(tmp_path, 251)
    builddate = tmp_path / "v251" / "builddate.txt"
    builddate.write_text("Release 2025 R1\nR251RC2P03\n", encoding="utf-8")
    grpc_calls = []

    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: str(executable),
        version_lookup=lambda product, path: 251,
        grpc_support_lookup=lambda revision: grpc_calls.append(revision) or False,
    )

    assert result.status == "unknown"
    assert result.detected_service_pack is None
    assert "no explicit service-pack marker" in result.message
    assert grpc_calls == []


def test_real_r251rc2p03_build_lines_remain_unknown_without_explicit_sp_marker(
    tmp_path: Path,
) -> None:
    executable = _windows_mechanical_executable(tmp_path, 251)
    builddate = tmp_path / "v251" / "builddate.txt"
    builddate.write_text(
        "Unified Package Created: 202412031843P03\n"
        "Unified Package Name: R251RC2P03\n",
        encoding="utf-8",
    )
    grpc_calls = []

    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: str(executable),
        version_lookup=lambda product, path: 251,
        grpc_support_lookup=lambda revision: grpc_calls.append(revision) or False,
    )

    assert result.status == "unknown"
    assert result.detected_revision == 251
    assert result.required_secure_service_pack == "SP04"
    assert result.detected_service_pack is None
    assert result.source == "exact_executable_builddate"
    assert grpc_calls == []
    assert json.loads(json.dumps(result.to_dict(), allow_nan=False)) == result.to_dict()


def test_discover_start_transport_stops_when_exact_path_and_helper_disagree(
    tmp_path: Path,
) -> None:
    executable = _windows_mechanical_executable(tmp_path, 251)
    builddate = tmp_path / "v251" / "builddate.txt"
    builddate.write_text("Release 2025 R1 SP04\nBuild\n", encoding="utf-8")

    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: str(executable),
        version_lookup=lambda product, path: 251,
        grpc_support_lookup=lambda revision: False,
    )

    assert result.status == "unknown"
    assert result.secure_transport_supported is None
    assert "disagree" in result.message


def test_discover_start_transport_reports_missing_executable_as_unknown() -> None:
    result = discover_start_transport(
        system_name="Windows",
        executable_lookup=lambda _requested_revision: None,
        version_lookup=lambda product, path: 251,
        grpc_support_lookup=lambda revision: False,
    )

    assert result.status == "unknown"
    assert result.executable_path is None
    assert "could not resolve" in result.message


def test_explicit_executable_is_the_exact_preflight_target(tmp_path: Path) -> None:
    executable = _windows_mechanical_executable(tmp_path, 261)

    result = discover_start_transport(
        str(executable),
        system_name="Windows",
        executable_lookup=lambda _requested_revision: pytest.fail(
            "path discovery must not replace exec_file"
        ),
        version_lookup=lambda product, path: 261,
        grpc_support_lookup=lambda revision: True,
    )

    assert result.executable_path == str(executable)


def test_requested_revision_is_used_for_discovery_and_mismatch_blocks(
    tmp_path: Path,
) -> None:
    executable = _windows_mechanical_executable(tmp_path, 261)
    requested = []

    result = discover_start_transport(
        requested_revision=251,
        system_name="Windows",
        executable_lookup=lambda revision: requested.append(revision) or str(executable),
        version_lookup=lambda product, path: 261,
        grpc_support_lookup=lambda revision: True,
    )

    assert requested == [251]
    assert result.status == "incompatible"
    assert result.source == "exact_executable_revision_mismatch"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (None, True),
        ("localhost", True),
        ("LOCALHOST.", True),
        ("127.0.0.1", True),
        ("127.5.6.7", True),
        ("::1", True),
        ("[::1]", True),
        ("mechanical.example.test", False),
        ("192.0.2.10", False),
    ],
)
def test_loopback_classification_does_not_use_dns(host: str | None, expected: bool) -> None:
    assert is_loopback_host(host) is expected


def test_platform_secure_transport_uses_documented_defaults() -> None:
    assert platform_secure_transport("Windows") == "wnua"
    assert platform_secure_transport("Linux") == "mtls"
    with pytest.raises(ValueError, match="Windows and Linux only"):
        platform_secure_transport("Darwin")


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (None, True),
        ("localhost", True),
        ("127.0.0.1", True),
        ("LOCALHOST.", False),
        ("127.5.6.7", False),
        ("::1", False),
    ],
)
def test_wnua_endpoint_matches_pymechanical_constraint(
    host: str | None,
    expected: bool,
) -> None:
    assert is_wnua_loopback_host(host) is expected
