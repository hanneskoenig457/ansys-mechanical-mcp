from pathlib import Path

from ansys_mechanical_mcp.products.mechanical.tools import execute_mechanical_script


class FakeMechanicalSession:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = []
        self.fail = fail

    def run_python_script(self, script, **kwargs):
        self.calls.append(("run_python_script", script, kwargs))
        if self.fail:
            raise RuntimeError("license unavailable")
        return "inline-result"

    def run_python_script_from_file(self, file_path, **kwargs):
        self.calls.append(("run_python_script_from_file", file_path, kwargs))
        if self.fail:
            raise RuntimeError("connection lost")
        return "file-result"


def test_execute_mechanical_script_runs_inline_script_with_options() -> None:
    session = FakeMechanicalSession()

    result = execute_mechanical_script(
        session,
        script="2 + 3",
        enable_logging=True,
        log_level="info",
        progress_interval=500,
    )

    assert result.success is True
    assert result.error is None
    assert result.data == {
        "execution_mode": "script",
        "result": "inline-result",
        "enable_logging": True,
        "log_level": "INFO",
        "progress_interval": 500,
    }
    assert session.calls == [
        (
            "run_python_script",
            "2 + 3",
            {
                "enable_logging": True,
                "log_level": "INFO",
                "progress_interval": 500,
            },
        )
    ]


def test_execute_mechanical_script_runs_script_file_with_options(tmp_path: Path) -> None:
    session = FakeMechanicalSession()
    script_file = tmp_path / "inspect_model.py"
    script_file.write_text("2 + 3\n", encoding="utf-8")

    result = execute_mechanical_script(
        session,
        script_file=script_file,
        enable_logging=False,
        log_level="WARNING",
        progress_interval=2000,
    )

    assert result.success is True
    assert result.data["execution_mode"] == "script_file"
    assert result.data["result"] == "file-result"
    assert session.calls == [
        (
            "run_python_script_from_file",
            str(script_file),
            {
                "enable_logging": False,
                "log_level": "WARNING",
                "progress_interval": 2000,
            },
        )
    ]


def test_execute_mechanical_script_rejects_missing_script_inputs() -> None:
    result = execute_mechanical_script(FakeMechanicalSession())

    assert result.success is False
    assert result.error == "MECHANICAL_SCRIPT_INPUT_ERROR"
    assert "exactly one" in result.message


def test_execute_mechanical_script_rejects_multiple_script_inputs() -> None:
    result = execute_mechanical_script(
        FakeMechanicalSession(),
        script="2 + 3",
        script_file="inspect_model.py",
    )

    assert result.success is False
    assert result.error == "MECHANICAL_SCRIPT_INPUT_ERROR"
    assert "exactly one" in result.message


def test_execute_mechanical_script_rejects_empty_inline_script() -> None:
    result = execute_mechanical_script(FakeMechanicalSession(), script="  ")

    assert result.success is False
    assert result.error == "MECHANICAL_SCRIPT_INPUT_ERROR"
    assert "must not be empty" in result.message


def test_execute_mechanical_script_rejects_missing_script_file() -> None:
    result = execute_mechanical_script(FakeMechanicalSession(), script_file=Path("missing.py"))

    assert result.success is False
    assert result.error == "MECHANICAL_SCRIPT_INPUT_ERROR"
    assert "existing file" in result.message


def test_execute_mechanical_script_rejects_invalid_log_level() -> None:
    result = execute_mechanical_script(
        FakeMechanicalSession(),
        script="2 + 3",
        log_level="TRACE",
    )

    assert result.success is False
    assert result.error == "MECHANICAL_SCRIPT_INPUT_ERROR"
    assert "log_level" in result.message


def test_execute_mechanical_script_rejects_invalid_progress_interval() -> None:
    result = execute_mechanical_script(
        FakeMechanicalSession(),
        script="2 + 3",
        progress_interval=0,
    )

    assert result.success is False
    assert result.error == "MECHANICAL_SCRIPT_INPUT_ERROR"
    assert "progress_interval" in result.message


def test_execute_mechanical_script_reports_missing_session_method() -> None:
    result = execute_mechanical_script(object(), script="2 + 3")

    assert result.success is False
    assert result.error == "MECHANICAL_SESSION_METHOD_MISSING"
    assert "run_python_script" in result.message


def test_execute_mechanical_script_wraps_session_errors() -> None:
    result = execute_mechanical_script(
        FakeMechanicalSession(fail=True),
        script="2 + 3",
    )

    assert result.success is False
    assert result.error == "MECHANICAL_SCRIPT_EXECUTION_FAILED"
    assert "license unavailable" in result.message


def test_execute_mechanical_script_result_is_json_compatible() -> None:
    result = execute_mechanical_script(FakeMechanicalSession(), script="2 + 3")

    assert result.to_dict() == {
        "success": True,
        "message": "Mechanical script executed successfully.",
        "data": {
            "execution_mode": "script",
            "result": "inline-result",
            "enable_logging": False,
            "log_level": "WARNING",
            "progress_interval": 2000,
        },
        "error": None,
    }
