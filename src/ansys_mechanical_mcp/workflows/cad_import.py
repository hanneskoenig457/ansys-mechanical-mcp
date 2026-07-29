"""Safe local CAD intake and confirmed Mechanical import workflow."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from ansys_mechanical_mcp.core.tool_result import ToolResult
from ansys_mechanical_mcp.products.mechanical.geometry_import import (
    apply_geometry_import,
    inspect_geometry_import_state,
)

CAD_IMPORT_SCHEMA_VERSION = "1.0"
SUPPORTED_CAD_EXTENSIONS = frozenset({".step", ".stp"})
SUPPORTED_PROJECT_EXTENSION = ".mechdb"
_HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(slots=True, frozen=True)
class CadImportConfig:
    """Explicit local filesystem boundary for Stage-1 CAD import."""

    input_root: Path | None = None
    output_root: Path | None = None


@dataclass(slots=True)
class _StoredImportPlan:
    public_plan: dict[str, Any]
    input_path: Path
    output_path: Path
    project_fingerprint: dict[str, Any]


class CadImportWorkflow:
    """Own deterministic import plans for one MCP application lifespan."""

    def __init__(self, config: CadImportConfig | None = None) -> None:
        self._config = config or CadImportConfig()
        self._plans: dict[str, _StoredImportPlan] = {}
        self._used_plan_ids: set[str] = set()

    def intake(self, input_path: str) -> ToolResult:
        """Return safe metadata for one configured local STEP file."""
        roots = self._resolve_roots()
        if isinstance(roots, ToolResult):
            return roots
        input_root, _ = roots

        resolved = _resolve_input_path(input_root, input_path)
        if isinstance(resolved, ToolResult):
            return resolved

        return ToolResult(
            success=True,
            message="Local CAD file inspected without reading it into Mechanical.",
            data={"input": _file_metadata(resolved, input_root)},
        )

    def preview(self, session: Any, *, input_path: str, output_project: str) -> ToolResult:
        """Build and retain a deterministic, read-only import plan."""
        roots = self._resolve_roots()
        if isinstance(roots, ToolResult):
            return roots
        input_root, output_root = roots

        resolved_input = _resolve_input_path(input_root, input_path)
        if isinstance(resolved_input, ToolResult):
            return resolved_input
        resolved_output = _resolve_output_path(output_root, output_project)
        if isinstance(resolved_output, ToolResult):
            return resolved_output

        state_result = inspect_geometry_import_state(session)
        if not state_result.success:
            return state_result
        state = state_result.data["state"]
        if state["inspection_status"] != "complete":
            return _failure(
                "MECHANICAL_PROJECT_STATE_UNKNOWN",
                "Mechanical project state is incomplete; import preview fails closed.",
                state=state,
            )
        if not state["is_empty"]:
            return _failure(
                "MECHANICAL_PROJECT_NOT_EMPTY",
                "Geometry import requires a new or proven-empty Mechanical project.",
                state=state,
            )

        input_metadata = _file_metadata(resolved_input, input_root)
        output_metadata = {
            "relative_path": resolved_output.relative_to(output_root).as_posix(),
            "extension": resolved_output.suffix.lower(),
            "exists": False,
            "parent_directory_empty": True,
        }
        project_fingerprint = _project_fingerprint(state)
        plan_body = {
            "schema_version": CAD_IMPORT_SCHEMA_VERSION,
            "operation": "import_step_geometry_once",
            "input": input_metadata,
            "output": output_metadata,
            "project": project_fingerprint,
            "mechanical_import": {
                "format": "Automatic",
                "process_named_selections": False,
                "process_coordinate_systems": False,
                "process_material_properties": False,
                "overwrite": False,
                "attempt_limit": 1,
                "automatic_retry": False,
            },
            "assumptions": [
                "The configured Mechanical instance is local to these filesystem roots.",
                "Project.SaveAs is supported only for independently opened Mechanical.",
                "STEP translation and native body/unit readback still require licensed validation.",
            ],
            "warnings": [
                "Confirmation imports geometry and saves a new Mechanical project.",
                "A failed apply is treated as possibly mutating and cannot be retried automatically.",
            ],
        }
        plan_id = _plan_id(plan_body)
        public_plan = {**plan_body, "plan_id": plan_id}

        if plan_id in self._used_plan_ids:
            return _failure(
                "CAD_IMPORT_PLAN_ALREADY_USED",
                "This exact deterministic plan was already applied or attempted in this server run.",
                plan_id=plan_id,
            )

        self._plans[plan_id] = _StoredImportPlan(
            public_plan=public_plan,
            input_path=resolved_input,
            output_path=resolved_output,
            project_fingerprint=project_fingerprint,
        )
        return ToolResult(
            success=True,
            message="Geometry import plan prepared without model mutation.",
            data={
                "plan": public_plan,
                "confirmation": {
                    "required": True,
                    "argument": "plan_id",
                    "value": plan_id,
                },
                "state": state,
            },
        )

    def validate_preview_request(
        self,
        *,
        input_path: str,
        output_project: str,
    ) -> ToolResult | None:
        """Reject invalid local paths before establishing Mechanical."""
        roots = self._resolve_roots()
        if isinstance(roots, ToolResult):
            return roots
        input_root, output_root = roots
        resolved_input = _resolve_input_path(input_root, input_path)
        if isinstance(resolved_input, ToolResult):
            return resolved_input
        resolved_output = _resolve_output_path(output_root, output_project)
        if isinstance(resolved_output, ToolResult):
            return resolved_output
        return None

    def validate_confirmation(self, plan_id: str) -> ToolResult | None:
        """Reject missing, unknown, or consumed confirmations before session access."""
        if not isinstance(plan_id, str) or not plan_id.strip():
            return _failure(
                "CAD_IMPORT_CONFIRMATION_INVALID",
                "'plan_id' must be the exact non-empty identifier returned by preview.",
            )
        if plan_id in self._used_plan_ids:
            return _failure(
                "CAD_IMPORT_PLAN_ALREADY_USED",
                "This import plan was already applied or attempted; automatic retry is forbidden.",
                plan_id=plan_id,
                retry_allowed=False,
            )
        if plan_id not in self._plans:
            return _failure(
                "CAD_IMPORT_CONFIRMATION_INVALID",
                "No unconsumed preview matches the supplied plan ID.",
                plan_id=plan_id,
            )
        return None

    def apply(self, session: Any, *, plan_id: str) -> ToolResult:
        """Apply one retained plan at most once after complete revalidation."""
        confirmation_error = self.validate_confirmation(plan_id)
        if confirmation_error is not None:
            return confirmation_error
        stored = self._plans[plan_id]

        if _plan_id({key: value for key, value in stored.public_plan.items() if key != "plan_id"}) != (
            plan_id
        ):
            self._plans.pop(plan_id, None)
            return _failure(
                "CAD_IMPORT_PLAN_TAMPERED",
                "The retained import plan no longer matches its deterministic identifier.",
                plan_id=plan_id,
            )

        current_input = _revalidate_input(stored)
        if isinstance(current_input, ToolResult):
            self._plans.pop(plan_id, None)
            return current_input
        if stored.output_path.exists() or stored.output_path.is_symlink():
            self._plans.pop(plan_id, None)
            return _failure(
                "CAD_IMPORT_OUTPUT_EXISTS",
                "The planned output now exists; overwrite is never permitted.",
                relative_path=stored.public_plan["output"]["relative_path"],
            )
        if any(stored.output_path.parent.iterdir()):
            self._plans.pop(plan_id, None)
            return _failure(
                "CAD_IMPORT_OUTPUT_DIRECTORY_NOT_EMPTY",
                "The planned output directory is no longer empty; create a new isolated target.",
                relative_path=stored.public_plan["output"]["relative_path"],
            )

        state_result = inspect_geometry_import_state(session)
        if not state_result.success:
            return state_result
        state = state_result.data["state"]
        if state["inspection_status"] != "complete":
            self._plans.pop(plan_id, None)
            return _failure(
                "MECHANICAL_PROJECT_STATE_UNKNOWN",
                "Mechanical project state is incomplete; confirmed import fails closed.",
                state=state,
            )
        if _project_fingerprint(state) != stored.project_fingerprint:
            self._plans.pop(plan_id, None)
            return _failure(
                "CAD_IMPORT_PLAN_STALE",
                "Mechanical project identity or emptiness changed after preview.",
                expected=stored.project_fingerprint,
                actual=_project_fingerprint(state),
            )

        # From this point onward a transport failure may have happened after
        # Mechanical mutation. Consume before the call and never auto-retry.
        self._used_plan_ids.add(plan_id)
        self._plans.pop(plan_id, None)
        result = apply_geometry_import(
            session,
            input_path=stored.input_path,
            output_path=stored.output_path,
            expected_sha256=stored.public_plan["input"]["sha256"],
            expected_project=stored.project_fingerprint,
        )
        result.data["plan_id"] = plan_id
        result.data["attempt_count"] = 1
        result.data["retry_allowed"] = False
        if result.success:
            if result.data["import"]["source_sha256"] != stored.public_plan["input"]["sha256"]:
                return _post_apply_failure(
                    "CAD_IMPORT_SOURCE_READBACK_MISMATCH",
                    "Mechanical import readback did not match the confirmed source SHA-256.",
                    plan_id,
                )
            state = result.data["state"]
            if (
                state["inspection_status"] != "complete"
                or state["body_count"] < 1
                or state["geometry_import_count"] < 1
            ):
                return _post_apply_failure(
                    "CAD_IMPORT_NATIVE_READBACK_FAILED",
                    "Mechanical did not return complete native import/body evidence.",
                    plan_id,
                )
            if state["project_file_name"] != stored.output_path.name:
                return _post_apply_failure(
                    "CAD_IMPORT_PROJECT_READBACK_MISMATCH",
                    "Mechanical project readback did not match the confirmed output filename.",
                    plan_id,
                )
            if not stored.output_path.is_file():
                return _post_apply_failure(
                    "CAD_IMPORT_OUTPUT_READBACK_FAILED",
                    "Mechanical reported success but the planned project output was not created.",
                    plan_id,
                )
        return result

    def inspect(self, session: Any) -> ToolResult:
        """Inspect native Mechanical geometry without changing it."""
        return inspect_geometry_import_state(session)

    def _resolve_roots(self) -> tuple[Path, Path] | ToolResult:
        input_root = self._config.input_root
        output_root = self._config.output_root
        if input_root is None or output_root is None:
            return _failure(
                "CAD_IMPORT_ROOTS_CONFIGURATION_REQUIRED",
                "Configure both the local CAD input root and the separate project output root.",
            )

        try:
            resolved_input = Path(input_root).resolve(strict=True)
            resolved_output = Path(output_root).resolve(strict=True)
        except OSError as exc:
            return _failure(
                "CAD_IMPORT_ROOT_INVALID",
                f"A configured CAD root cannot be resolved: {exc}",
            )
        if not resolved_input.is_dir() or not resolved_output.is_dir():
            return _failure(
                "CAD_IMPORT_ROOT_INVALID",
                "Configured CAD input and output roots must both be existing directories.",
            )
        if _paths_overlap(resolved_input, resolved_output):
            return _failure(
                "CAD_IMPORT_ROOTS_NOT_SEPARATE",
                "CAD input and output roots must be distinct and non-overlapping.",
            )
        return resolved_input, resolved_output


def _resolve_input_path(root: Path, relative_path: str) -> Path | ToolResult:
    validation = _validate_relative_path(relative_path, field="input_path")
    if validation is not None:
        return validation
    candidate = root / relative_path
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        return _failure("CAD_INPUT_NOT_FOUND", f"CAD input cannot be resolved: {exc}")
    if not _is_within(resolved, root):
        return _failure("CAD_INPUT_PATH_ESCAPE", "CAD input resolves outside the configured root.")
    if not resolved.is_file():
        return _failure("CAD_INPUT_NOT_FILE", "CAD input must resolve to a regular file.")
    if resolved.suffix.lower() not in SUPPORTED_CAD_EXTENSIONS:
        return _failure(
            "CAD_INPUT_FORMAT_UNSUPPORTED",
            "Stage 1 accepts only STEP geometry with a .step or .stp extension.",
            extension=resolved.suffix.lower(),
            supported_extensions=sorted(SUPPORTED_CAD_EXTENSIONS),
        )
    return resolved


def _resolve_output_path(root: Path, relative_path: str) -> Path | ToolResult:
    validation = _validate_relative_path(relative_path, field="output_project")
    if validation is not None:
        return validation
    raw = root / relative_path
    if raw.suffix.lower() != SUPPORTED_PROJECT_EXTENSION:
        return _failure(
            "CAD_IMPORT_OUTPUT_FORMAT_UNSUPPORTED",
            "The Stage-1 output project must use the .mechdb extension.",
        )
    try:
        parent = raw.parent.resolve(strict=True)
    except OSError as exc:
        return _failure(
            "CAD_IMPORT_OUTPUT_PARENT_INVALID",
            f"The output parent directory cannot be resolved: {exc}",
        )
    if not _is_within(parent, root):
        return _failure(
            "CAD_IMPORT_OUTPUT_PATH_ESCAPE",
            "Project output resolves outside the configured output root.",
        )
    candidate = parent / raw.name
    if candidate.exists() or candidate.is_symlink():
        return _failure(
            "CAD_IMPORT_OUTPUT_EXISTS",
            "The project output already exists; overwrite is never permitted.",
        )
    if any(parent.iterdir()):
        return _failure(
            "CAD_IMPORT_OUTPUT_DIRECTORY_NOT_EMPTY",
            "The output directory must be empty so Mechanical side files cannot be overwritten.",
        )
    return candidate


def _validate_relative_path(value: str, *, field: str) -> ToolResult | None:
    if not isinstance(value, str) or not value.strip():
        return _failure("CAD_IMPORT_PATH_INVALID", f"'{field}' must be a non-empty relative path.")
    path = Path(value)
    if path.is_absolute() or PurePath(value).anchor:
        return _failure("CAD_IMPORT_ABSOLUTE_PATH_REJECTED", f"'{field}' must not be absolute.")
    if ".." in PurePath(value).parts:
        return _failure("CAD_IMPORT_PARENT_PATH_REJECTED", f"'{field}' must not contain '..'.")
    return None


def _file_metadata(path: Path, root: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "sha256": _sha256(path),
    }


def _revalidate_input(stored: _StoredImportPlan) -> dict[str, Any] | ToolResult:
    try:
        current = {
            "size_bytes": stored.input_path.stat().st_size,
            "sha256": _sha256(stored.input_path),
        }
    except OSError as exc:
        return _failure("CAD_INPUT_CHANGED", f"The planned CAD input is unavailable: {exc}")
    planned = stored.public_plan["input"]
    if current["size_bytes"] != planned["size_bytes"] or current["sha256"] != planned["sha256"]:
        return _failure(
            "CAD_INPUT_CHANGED",
            "The CAD input size or SHA-256 changed after preview; create a new plan.",
            planned={
                "size_bytes": planned["size_bytes"],
                "sha256": planned["sha256"],
            },
            current=current,
        )
    return current


def _project_fingerprint(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_version": state["product_version"],
        "project_file_name": state["project_file_name"],
        "project_file_identity": state["project_file_identity"],
        "analysis_count": state["analysis_count"],
        "geometry_import_count": state["geometry_import_count"],
        "body_count": state["body_count"],
        "body_ids": [body["object_id"] for body in state["bodies"]],
    }


def _plan_id(plan: dict[str, Any]) -> str:
    canonical = json.dumps(
        plan,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _paths_overlap(first: Path, second: Path) -> bool:
    return _is_within(first, second) or _is_within(second, first)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _failure(code: str, message: str, **details: Any) -> ToolResult:
    return ToolResult(
        success=False,
        message=message,
        data=details,
        error=code,
    )


def _post_apply_failure(code: str, message: str, plan_id: str) -> ToolResult:
    return _failure(
        code,
        message,
        plan_id=plan_id,
        attempt_count=1,
        retry_allowed=False,
        mutation_status="unknown",
    )
