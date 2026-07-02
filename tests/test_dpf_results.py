import builtins
import json
from types import SimpleNamespace

import pytest

from ansys_mechanical_mcp.products.dpf.results import summarize_result_file


class FakeResultProvider:
    def eval(self):  # pragma: no cover - must not be called by metadata summary.
        raise AssertionError("result fields should not be evaluated")


class FakeResults:
    displacement = FakeResultProvider()
    stress = FakeResultProvider()

    def __dir__(self):
        return [
            "_private",
            "connector",
            "displacement",
            "mesh_by_default",
            "stress",
        ]

    def __iter__(self):
        return iter([SimpleNamespace(name="temperature")])


class BrokenMetadataModel:
    @property
    def metadata(self):
        raise RuntimeError("metadata server unavailable")


def _fake_model() -> SimpleNamespace:
    return SimpleNamespace(
        metadata=SimpleNamespace(
            result_info=SimpleNamespace(
                analysis_type="static",
                physics_type="mechanical",
                n_results=3,
                unit_system="MKS: m, kg, N, s, V, A, degC",
                unit_system_name="MKS",
                solver_version="2025 R2",
                job_name="file",
                main_title="Static Structural",
            ),
            meshed_region=SimpleNamespace(
                nodes=SimpleNamespace(n_nodes=42),
                elements=SimpleNamespace(n_elements=11),
                unit="m",
            ),
            time_freq_support=SimpleNamespace(n_sets=1),
        ),
        results=FakeResults(),
    )


def test_summarize_result_file_extracts_metadata_with_injected_model_factory(tmp_path) -> None:
    result_file = tmp_path / "file.rst"
    result_file.write_bytes(b"fake rst placeholder")
    calls = []

    def model_factory(path: str) -> SimpleNamespace:
        calls.append(path)
        return _fake_model()

    result = summarize_result_file(result_file, model_factory=model_factory)

    assert result.success is True
    assert result.error is None
    assert result.message == "PyDPF result metadata summary extracted successfully."
    assert result.data == {
        "result_file": str(result_file),
        "result_info": {
            "analysis_type": "static",
            "physics_type": "mechanical",
            "n_results": 3,
            "unit_system": "MKS: m, kg, N, s, V, A, degC",
            "unit_system_name": "MKS",
            "solver_version": "2025 R2",
            "job_name": "file",
            "main_title": "Static Structural",
        },
        "mesh": {
            "node_count": 42,
            "element_count": 11,
            "unit": "m",
        },
        "time_freq": {"n_sets": 1},
        "available_results": ["displacement", "stress", "temperature"],
    }
    assert calls == [str(result_file)]
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()


def test_summarize_result_file_does_not_import_dpf_when_model_factory_is_injected(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_file = tmp_path / "file.rst"
    result_file.write_bytes(b"fake rst placeholder")
    original_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("ansys.dpf"):
            raise AssertionError("ansys.dpf must not be imported with an injected factory")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    result = summarize_result_file(result_file, model_factory=lambda _path: _fake_model())

    assert result.success is True


def test_summarize_result_file_rejects_empty_path() -> None:
    result = summarize_result_file(" ")

    assert result.success is False
    assert result.error == "DPF_RESULT_SUMMARY_INPUT_ERROR"
    assert "must not be empty" in result.message


def test_summarize_result_file_rejects_missing_path(tmp_path) -> None:
    result_file = tmp_path / "missing.rst"

    result = summarize_result_file(result_file)

    assert result.success is False
    assert result.error == "DPF_RESULT_SUMMARY_INPUT_ERROR"
    assert "does not exist" in result.message
    assert result.data == {"result_file": str(result_file)}


def test_summarize_result_file_wraps_missing_pydpf_dependency(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_file = tmp_path / "file.rst"
    result_file.write_bytes(b"fake rst placeholder")
    original_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("ansys.dpf"):
            raise ImportError("blocked PyDPF import")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    result = summarize_result_file(result_file)

    assert result.success is False
    assert result.error == "DPF_RESULT_SUMMARY_DEPENDENCY_MISSING"
    assert "PyDPF is not installed" in result.message


def test_summarize_result_file_wraps_model_load_errors(tmp_path) -> None:
    result_file = tmp_path / "file.rst"
    result_file.write_bytes(b"fake rst placeholder")

    def model_factory(_path: str):
        raise RuntimeError("not a supported result file")

    result = summarize_result_file(result_file, model_factory=model_factory)

    assert result.success is False
    assert result.error == "DPF_RESULT_SUMMARY_MODEL_LOAD_FAILED"
    assert "not a supported result file" in result.message
    assert result.data == {"result_file": str(result_file)}


def test_summarize_result_file_wraps_metadata_extraction_errors(tmp_path) -> None:
    result_file = tmp_path / "file.rst"
    result_file.write_bytes(b"fake rst placeholder")

    result = summarize_result_file(result_file, model_factory=lambda _path: BrokenMetadataModel())

    assert result.success is False
    assert result.error == "DPF_RESULT_SUMMARY_METADATA_FAILED"
    assert "metadata server unavailable" in result.message
    assert result.data == {"result_file": str(result_file)}
