import hashlib
import json
from pathlib import Path

import pytest

from ansys_mechanical_mcp.products.mechanical.geometry_import import (
    MECHANICAL_GEOMETRY_IMPORT_INSPECTION_SCRIPT,
    inspect_geometry_import_state,
)
from ansys_mechanical_mcp.workflows.cad_import import CadImportConfig, CadImportWorkflow


def _empty_state() -> dict:
    return {
        "inspection_status": "complete",
        "product_version": "2025 R1",
        "project_file_name": None,
        "project_file_identity": None,
        "unit_system": "StandardNMM",
        "analysis_count": 0,
        "geometry_import_count": 0,
        "body_count": 0,
        "bodies": [],
        "is_empty": True,
        "errors": [],
    }


class FakeMechanicalSession:
    def __init__(
        self,
        *,
        output_path: Path | None = None,
        state: dict | None = None,
        fail_apply: bool = False,
    ) -> None:
        self.output_path = output_path
        self.state = state or _empty_state()
        self.fail_apply = fail_apply
        self.inspection_calls = 0
        self.apply_calls = 0
        self.scripts: list[str] = []

    def run_python_script(self, script: str, **_kwargs) -> str:
        self.scripts.append(script)
        if "__ansys_mechanical_mcp_inspect_geometry_import" in script:
            self.inspection_calls += 1
            return json.dumps({"state": self.state})
        if "__ansys_mechanical_mcp_apply_geometry_import" not in script:
            raise AssertionError("unexpected Mechanical script")

        self.apply_calls += 1
        if self.fail_apply:
            raise RuntimeError(
                f"translator stopped at {self.output_path} after an unknown mutation boundary"
            )
        if self.output_path is None:
            raise AssertionError("fake apply requires an output path")
        self.output_path.write_bytes(b"fake-mechdb")
        source_path = next(
            path
            for path in self.output_path.parent.parent.rglob("*.step")
            if path.is_file()
        )
        self.state = {
            **_empty_state(),
            "project_file_name": self.output_path.name,
            "project_file_identity": "saved-project-identity",
            "geometry_import_count": 1,
            "body_count": 1,
            "bodies": [
                {
                    "object_id": 42,
                    "name": "Ring",
                    "type": "Solid",
                    "material": "Structural Steel",
                }
            ],
            "is_empty": False,
        }
        return json.dumps(
            {
                "state": self.state,
                "import": {
                    "object_id": 17,
                    "format": "Automatic",
                    "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "output_created": True,
                    "overwrite": False,
                },
            }
        )


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    input_root.mkdir()
    output_root.mkdir()
    return input_root, output_root


def _workflow(roots: tuple[Path, Path]) -> CadImportWorkflow:
    return CadImportWorkflow(CadImportConfig(input_root=roots[0], output_root=roots[1]))


def test_intake_returns_only_safe_metadata(roots: tuple[Path, Path]) -> None:
    input_root, _ = roots
    cad = input_root / "ring.step"
    cad.write_bytes(b"ISO-10303-21;")

    result = _workflow(roots).intake("ring.step")

    assert result.success is True
    assert result.data["input"] == {
        "relative_path": "ring.step",
        "extension": ".step",
        "size_bytes": 13,
        "sha256": hashlib.sha256(b"ISO-10303-21;").hexdigest(),
    }
    serialized = json.dumps(result.to_dict(), allow_nan=False)
    assert str(input_root) not in serialized
    assert "ISO-10303-21" not in serialized


@pytest.mark.parametrize("value", ["/tmp/ring.step", "../ring.step"])
def test_intake_rejects_absolute_and_parent_paths(
    roots: tuple[Path, Path],
    value: str,
) -> None:
    result = _workflow(roots).intake(value)

    assert result.success is False
    assert result.error in {
        "CAD_IMPORT_ABSOLUTE_PATH_REJECTED",
        "CAD_IMPORT_PARENT_PATH_REJECTED",
    }


def test_intake_rejects_symlink_escape(roots: tuple[Path, Path], tmp_path: Path) -> None:
    input_root, _ = roots
    outside = tmp_path / "outside.step"
    outside.write_bytes(b"private")
    (input_root / "alias.step").symlink_to(outside)

    result = _workflow(roots).intake("alias.step")

    assert result.success is False
    assert result.error == "CAD_INPUT_PATH_ESCAPE"


def test_intake_rejects_unsupported_geometry(roots: tuple[Path, Path]) -> None:
    input_root, _ = roots
    (input_root / "ring.iges").write_bytes(b"iges")

    result = _workflow(roots).intake("ring.iges")

    assert result.success is False
    assert result.error == "CAD_INPUT_FORMAT_UNSUPPORTED"
    assert result.data["supported_extensions"] == [".step", ".stp"]


def test_roots_must_be_configured_and_non_overlapping(tmp_path: Path) -> None:
    missing = CadImportWorkflow().intake("ring.step")
    overlap = CadImportWorkflow(
        CadImportConfig(input_root=tmp_path, output_root=tmp_path)
    ).intake("ring.step")

    assert missing.error == "CAD_IMPORT_ROOTS_CONFIGURATION_REQUIRED"
    assert overlap.error == "CAD_IMPORT_ROOTS_NOT_SEPARATE"


def test_preview_is_deterministic_and_read_only(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    session = FakeMechanicalSession(output_path=output_root / "ring.mechdb")
    workflow = _workflow(roots)

    first = workflow.preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )
    second = workflow.preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )

    assert first.success is True
    assert second.success is True
    assert first.data["plan"]["plan_id"] == second.data["plan"]["plan_id"]
    assert first.data["confirmation"]["value"] == first.data["plan"]["plan_id"]
    assert session.apply_calls == 0
    assert not (output_root / "ring.mechdb").exists()
    assert json.loads(json.dumps(first.to_dict(), allow_nan=False)) == first.to_dict()


def test_preview_fails_closed_for_non_empty_project(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    state = {
        **_empty_state(),
        "body_count": 1,
        "bodies": [{"object_id": 7, "name": "Existing", "type": "Solid", "material": None}],
        "is_empty": False,
    }
    session = FakeMechanicalSession(output_path=output_root / "ring.mechdb", state=state)

    result = _workflow(roots).preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )

    assert result.success is False
    assert result.error == "MECHANICAL_PROJECT_NOT_EMPTY"
    assert session.apply_calls == 0


def test_preview_rejects_existing_output(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    (output_root / "ring.mechdb").write_bytes(b"existing")

    result = _workflow(roots).preview(
        FakeMechanicalSession(),
        input_path="ring.step",
        output_project="ring.mechdb",
    )

    assert result.success is False
    assert result.error == "CAD_IMPORT_OUTPUT_EXISTS"


def test_preview_rejects_non_empty_output_directory(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    (output_root / "unrelated.txt").write_text("keep")

    result = _workflow(roots).preview(
        FakeMechanicalSession(),
        input_path="ring.step",
        output_project="ring.mechdb",
    )

    assert result.success is False
    assert result.error == "CAD_IMPORT_OUTPUT_DIRECTORY_NOT_EMPTY"


def test_preview_rejects_output_symlink_escape(
    roots: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    outside = tmp_path / "outside"
    outside.mkdir()
    (output_root / "linked").symlink_to(outside, target_is_directory=True)

    result = _workflow(roots).preview(
        FakeMechanicalSession(),
        input_path="ring.step",
        output_project="linked/ring.mechdb",
    )

    assert result.success is False
    assert result.error == "CAD_IMPORT_OUTPUT_PATH_ESCAPE"


def test_preview_rejects_partial_project_state(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    session = FakeMechanicalSession(
        output_path=output_root / "ring.mechdb",
        state={
            **_empty_state(),
            "inspection_status": "partial",
            "analysis_count": None,
            "is_empty": False,
            "errors": ["Model.Analyses unavailable"],
        },
    )

    result = _workflow(roots).preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )

    assert result.success is False
    assert result.error == "MECHANICAL_PROJECT_STATE_UNKNOWN"


def test_apply_rejects_changed_input_and_invalidates_plan(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    cad = input_root / "ring.step"
    cad.write_bytes(b"before")
    session = FakeMechanicalSession(output_path=output_root / "ring.mechdb")
    workflow = _workflow(roots)
    preview = workflow.preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )
    cad.write_bytes(b"after")

    first = workflow.apply(session, plan_id=preview.data["plan"]["plan_id"])
    second = workflow.apply(session, plan_id=preview.data["plan"]["plan_id"])

    assert first.error == "CAD_INPUT_CHANGED"
    assert second.error == "CAD_IMPORT_CONFIRMATION_INVALID"
    assert session.apply_calls == 0


def test_apply_rejects_tampered_retained_plan(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    session = FakeMechanicalSession(output_path=output_root / "ring.mechdb")
    workflow = _workflow(roots)
    preview = workflow.preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )
    preview.data["plan"]["mechanical_import"]["format"] = "Changed"

    result = workflow.apply(session, plan_id=preview.data["plan"]["plan_id"])

    assert result.error == "CAD_IMPORT_PLAN_TAMPERED"
    assert session.apply_calls == 0


def test_apply_rejects_stale_project_state(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    session = FakeMechanicalSession(output_path=output_root / "ring.mechdb")
    workflow = _workflow(roots)
    preview = workflow.preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )
    session.state = {
        **_empty_state(),
        "analysis_count": 1,
        "is_empty": False,
    }

    result = workflow.apply(session, plan_id=preview.data["plan"]["plan_id"])

    assert result.error == "CAD_IMPORT_PLAN_STALE"
    assert session.apply_calls == 0


def test_apply_runs_once_and_returns_native_readback(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    output = output_root / "ring.mechdb"
    session = FakeMechanicalSession(output_path=output)
    workflow = _workflow(roots)
    preview = workflow.preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )
    plan_id = preview.data["plan"]["plan_id"]

    first = workflow.apply(session, plan_id=plan_id)
    second = workflow.apply(session, plan_id=plan_id)

    assert first.success is True
    assert first.data["plan_id"] == plan_id
    assert first.data["attempt_count"] == 1
    assert first.data["retry_allowed"] is False
    assert first.data["state"]["body_count"] == 1
    assert first.data["state"]["bodies"][0]["name"] == "Ring"
    assert first.data["import"]["output_created"] is True
    assert first.data["import"]["overwrite"] is False
    assert second.error == "CAD_IMPORT_PLAN_ALREADY_USED"
    assert session.apply_calls == 1
    assert output.is_file()
    assert str(input_root) not in json.dumps(first.to_dict(), allow_nan=False)


def test_apply_failure_is_consumed_and_never_retried(roots: tuple[Path, Path]) -> None:
    input_root, output_root = roots
    (input_root / "ring.step").write_bytes(b"ring")
    session = FakeMechanicalSession(
        output_path=output_root / "ring.mechdb",
        fail_apply=True,
    )
    workflow = _workflow(roots)
    preview = workflow.preview(
        session,
        input_path="ring.step",
        output_project="ring.mechdb",
    )
    plan_id = preview.data["plan"]["plan_id"]

    first = workflow.apply(session, plan_id=plan_id)
    second = workflow.apply(session, plan_id=plan_id)

    assert first.error == "MECHANICAL_GEOMETRY_IMPORT_EXECUTION_FAILED"
    assert first.data["mutation_status"] == "unknown"
    assert first.data["attempt_count"] == 1
    assert first.data["retry_allowed"] is False
    assert second.error == "CAD_IMPORT_PLAN_ALREADY_USED"
    assert session.apply_calls == 1
    assert str(output_root) not in json.dumps(first.to_dict(), allow_nan=False)


def test_inspection_parser_rejects_non_json() -> None:
    class BadSession:
        def run_python_script(self, *_args, **_kwargs):
            return "not-json"

    result = inspect_geometry_import_state(BadSession())

    assert result.success is False
    assert result.error == "MECHANICAL_GEOMETRY_INSPECTION_PARSE_FAILED"


def test_inspection_script_cleans_up_its_global_helper() -> None:
    class Empty:
        pass

    ext_api = Empty()
    ext_api.DataModel = Empty()
    ext_api.DataModel.Project = Empty()
    ext_api.DataModel.Project.Model = Empty()
    ext_api.DataModel.Project.Model.Analyses = []
    ext_api.DataModel.Project.Model.GeometryImportGroup = Empty()
    ext_api.DataModel.Project.Model.GeometryImportGroup.Children = []
    ext_api.DataModel.GeoData = Empty()
    ext_api.DataModel.GeoData.Assemblies = []

    script_body, call = MECHANICAL_GEOMETRY_IMPORT_INSPECTION_SCRIPT.rsplit("\n", 1)
    namespace = {"ExtAPI": ext_api}
    exec(f"{script_body}\n__result = {call}", namespace)

    assert json.loads(namespace["__result"])["state"]["is_empty"] is True
    assert not any(name.startswith("__ansys_mechanical_mcp_inspect_geometry") for name in namespace)
