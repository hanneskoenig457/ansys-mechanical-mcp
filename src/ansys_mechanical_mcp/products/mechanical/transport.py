"""Preflight helpers for Mechanical gRPC transport selection."""

from __future__ import annotations

import ipaddress
import platform
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


MechanicalTransportMode = Literal["auto", "insecure", "mtls", "wnua"]
MechanicalTransportPreflightStatus = Literal[
    "supported",
    "unsupported",
    "incompatible",
    "unknown",
    "not_run",
]

_SECURE_SERVICE_PACKS = {
    242: "SP05",
    251: "SP04",
    252: "SP03",
}


@dataclass(slots=True, frozen=True)
class MechanicalTransportPreflight:
    """Evidence used to choose a transport before starting Mechanical."""

    status: MechanicalTransportPreflightStatus
    executable_path: str | None = None
    exact_executable_validated: bool = False
    detected_revision: int | None = None
    secure_transport_supported: bool | None = None
    required_secure_service_pack: str | None = None
    detected_service_pack: str | None = None
    builddate_path: str | None = None
    source: str = "pymechanical"
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible diagnostic."""
        return {
            "status": self.status,
            "executable_path": self.executable_path,
            "exact_executable_validated": self.exact_executable_validated,
            "detected_revision": self.detected_revision,
            "secure_transport_supported": self.secure_transport_supported,
            "required_secure_service_pack": self.required_secure_service_pack,
            "detected_service_pack": self.detected_service_pack,
            "builddate_path": self.builddate_path,
            "source": self.source,
            "message": self.message,
        }


def discover_start_transport(
    exec_file: str | None = None,
    requested_revision: int | None = None,
    *,
    system_name: str | None = None,
    executable_lookup: Callable[[int | None], str | None] | None = None,
    version_lookup: Callable[[str, str], int] | None = None,
    grpc_support_lookup: Callable[[int], bool] | None = None,
) -> MechanicalTransportPreflight:
    """Inspect the exact local executable that would be passed to PyMechanical.

    The function deliberately returns ``unknown`` rather than interpreting
    missing path or build metadata as permission to weaken transport security.
    Imports remain lazy so environment checks and ordinary fake tests do not
    require PyMechanical.
    """
    if executable_lookup is None or version_lookup is None or grpc_support_lookup is None:
        try:
            from ansys.mechanical.core.misc import has_grpc_service_pack
            from ansys.tools.common.path import get_mechanical_path, version_from_path
        except ImportError as exc:
            return MechanicalTransportPreflight(
                status="unknown",
                source="pymechanical_import",
                message=f"PyMechanical transport preflight is unavailable: {exc}",
            )

        if executable_lookup is None:

            def _executable_lookup(revision: int | None) -> str | None:
                return get_mechanical_path(allow_input=False, version=revision)

            executable_lookup = _executable_lookup
        if version_lookup is None:
            version_lookup = version_from_path
        if grpc_support_lookup is None:
            grpc_support_lookup = has_grpc_service_pack

    if executable_lookup is None or version_lookup is None or grpc_support_lookup is None:
        return MechanicalTransportPreflight(
            status="unknown",
            source="pymechanical_import",
            message="PyMechanical transport preflight dependencies could not be resolved.",
        )

    try:
        resolved_path = exec_file or executable_lookup(requested_revision)
    except Exception as exc:  # noqa: BLE001 - preserve third-party discovery details.
        return MechanicalTransportPreflight(
            status="unknown",
            source="ansys_tools_path",
            message=f"Mechanical executable discovery failed: {exc}",
        )

    if not resolved_path:
        return MechanicalTransportPreflight(
            status="unknown",
            source="ansys_tools_path",
            message="PyMechanical could not resolve a local Mechanical executable without input.",
        )

    executable_path = str(resolved_path)
    if not Path(executable_path).is_file():
        return MechanicalTransportPreflight(
            status="unknown",
            executable_path=executable_path,
            source="ansys_tools_path",
            message="The resolved Mechanical executable path is not a file.",
        )

    try:
        revision = int(version_lookup("mechanical", executable_path))
    except Exception as exc:  # noqa: BLE001 - preserve third-party path parsing details.
        return MechanicalTransportPreflight(
            status="unknown",
            executable_path=executable_path,
            exact_executable_validated=True,
            source="ansys_tools_path.version_from_path",
            message=f"Mechanical revision detection failed: {exc}",
        )

    if requested_revision is not None and revision != requested_revision:
        return MechanicalTransportPreflight(
            status="incompatible",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            source="exact_executable_revision_mismatch",
            message=(
                f"Requested Mechanical revision {requested_revision}, but the resolved exact "
                f"executable is revision {revision}."
            ),
        )

    required_service_pack = _SECURE_SERVICE_PACKS.get(revision)
    if revision < 242:
        return MechanicalTransportPreflight(
            status="incompatible",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            secure_transport_supported=False,
            source="pymechanical_version_matrix",
            message=(
                "PyMechanical 0.12.12 supports Mechanical 2024 R2 revision 242 or later."
            ),
        )

    if revision >= 261:
        return MechanicalTransportPreflight(
            status="supported",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            secure_transport_supported=True,
            source="pymechanical_version_matrix",
            message="This Mechanical revision supports secure gRPC transport.",
        )

    if required_service_pack is None:
        return MechanicalTransportPreflight(
            status="unknown",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            source="pymechanical_version_matrix",
            message="PyMechanical has no secure-transport service-pack rule for this revision.",
        )

    builddate_path = _builddate_path(executable_path, system_name or platform.system())
    if builddate_path is None or not builddate_path.is_file():
        return MechanicalTransportPreflight(
            status="unknown",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            required_secure_service_pack=required_service_pack,
            builddate_path=str(builddate_path) if builddate_path is not None else None,
            source="mechanical_builddate",
            message=(
                "Mechanical build metadata is unavailable; automatic transport preflight "
                "cannot complete and no process is started."
            ),
        )

    try:
        detected_service_pack_number = _read_service_pack(builddate_path)
    except Exception as exc:  # noqa: BLE001 - preserve third-party preflight details.
        return MechanicalTransportPreflight(
            status="unknown",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            required_secure_service_pack=required_service_pack,
            builddate_path=str(builddate_path),
            source="exact_executable_builddate",
            message=f"Mechanical service-pack detection failed: {exc}",
        )

    if detected_service_pack_number is None:
        return MechanicalTransportPreflight(
            status="unknown",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            required_secure_service_pack=required_service_pack,
            builddate_path=str(builddate_path),
            source="exact_executable_builddate",
            message=(
                "The exact executable build metadata contains no explicit service-pack marker; "
                "automatic transport preflight cannot complete and no process is started."
            ),
        )

    detected_service_pack = f"SP{detected_service_pack_number:02d}"
    exact_executable_supported = detected_service_pack_number >= int(
        required_service_pack.removeprefix("SP")
    )

    try:
        pymechanical_supported = bool(grpc_support_lookup(revision))
    except Exception as exc:  # noqa: BLE001 - preserve third-party preflight details.
        return MechanicalTransportPreflight(
            status="unknown",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            required_secure_service_pack=required_service_pack,
            detected_service_pack=detected_service_pack,
            builddate_path=str(builddate_path),
            source="pymechanical.has_grpc_service_pack",
            message=f"PyMechanical service-pack cross-check failed: {exc}",
        )

    if pymechanical_supported != exact_executable_supported:
        return MechanicalTransportPreflight(
            status="unknown",
            executable_path=executable_path,
            exact_executable_validated=True,
            detected_revision=revision,
            required_secure_service_pack=required_service_pack,
            detected_service_pack=detected_service_pack,
            builddate_path=str(builddate_path),
            source="exact_executable_pymechanical_cross_check",
            message=(
                "The exact executable build metadata and PyMechanical's path-based service-pack "
                "check disagree; automatic transport preflight cannot complete and no process "
                "is started."
            ),
        )

    secure_supported = exact_executable_supported

    return MechanicalTransportPreflight(
        status="supported" if secure_supported else "unsupported",
        executable_path=executable_path,
        exact_executable_validated=True,
        detected_revision=revision,
        secure_transport_supported=secure_supported,
        required_secure_service_pack=required_service_pack,
        detected_service_pack=detected_service_pack,
        builddate_path=str(builddate_path),
        source="exact_executable_pymechanical_cross_check",
        message=(
            "PyMechanical classified the installed service pack as secure-transport capable."
            if secure_supported
            else (
                "PyMechanical classified the installed service pack as below the secure "
                f"transport requirement ({required_service_pack})."
            )
        ),
    )


def platform_secure_transport(system_name: str) -> Literal["mtls", "wnua"]:
    """Return PyMechanical's documented secure platform default."""
    normalized = system_name.strip().lower()
    if normalized == "windows":
        return "wnua"
    if normalized == "linux":
        return "mtls"
    msg = (
        "Automatic Mechanical transport selection supports Windows and Linux only; "
        "choose an explicit transport mode on this platform."
    )
    raise ValueError(msg)


def is_loopback_host(host: str | None) -> bool:
    """Classify only explicit loopback addresses as local without DNS lookup."""
    if host is None:
        return True
    normalized = host.strip().lower().rstrip(".")
    if normalized == "localhost":
        return True
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def is_wnua_loopback_host(host: str | None) -> bool:
    """Return whether PyMechanical accepts the endpoint for WNUA."""
    if host is None:
        return True
    return host.strip().lower() in ("localhost", "127.0.0.1")


def transport_security(mode: str | None) -> tuple[bool | None, str]:
    """Describe the security property of an effective transport mode."""
    if mode == "insecure":
        return False, "unencrypted_unauthenticated"
    if mode == "wnua":
        return True, "windows_named_user_authentication"
    if mode == "mtls":
        return True, "mutual_tls"
    return None, "unknown"


def _builddate_path(executable_path: str, system_name: str) -> Path | None:
    path = Path(executable_path)
    normalized = system_name.strip().lower()
    if normalized == "windows":
        try:
            return path.parent.parent.parent.parent / "builddate.txt"
        except IndexError:  # pragma: no cover - pathlib parents are practically unbounded.
            return None
    if normalized == "linux":
        try:
            return path.parent.parent / "builddate.txt"
        except IndexError:  # pragma: no cover - pathlib parents are practically unbounded.
            return None
    return None


def _read_service_pack(builddate_path: Path) -> int | None:
    """Read an explicit SP marker from the same metadata lines PyMechanical checks."""
    with builddate_path.open("r", encoding="utf-8", errors="ignore") as builddate_file:
        text = f"{builddate_file.readline()} {builddate_file.readline()}".upper()
    matches = [int(value) for value in re.findall(r"\bSP\s*0*(\d{1,2})\b", text)]
    return max(matches) if matches else None
