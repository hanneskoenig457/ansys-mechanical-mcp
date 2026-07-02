import json

from ansys_mechanical_mcp.workflows.static_structural import (
    solve_static_structural_analysis,
)


class FakeMechanicalSession:
    def __init__(
        self,
        *,
        result: object,
        fail: bool = False,
    ) -> None:
        self.calls = []
        self.result = result
        self.fail = fail

    def run_python_script(self, script):
        self.calls.append(script)
        if self.fail:
            raise RuntimeError("solver license unavailable")
        return self.result


def _payload(**overrides):
    payload = {
        "status": "ok",
        "selector": {"name": None, "object_id": 17},
        "analysis": {
            "name": "Static Structural",
            "object_id": 17,
            "type": "StaticStructural",
            "caption": "Static Structural",
        },
        "solved": True,
        "wait": True,
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_solve_static_structural_analysis_runs_mechanical_script_by_object_id() -> None:
    session = FakeMechanicalSession(result=_payload())

    result = solve_static_structural_analysis(session, object_id=17)

    assert result.success is True
    assert result.error is None
    assert result.message == "Static Structural analysis solved successfully."
    assert result.data == {
        "analysis": {
            "name": "Static Structural",
            "object_id": 17,
            "type": "StaticStructural",
            "caption": "Static Structural",
        },
        "selector": {"name": None, "object_id": 17},
        "solved": True,
        "wait": True,
    }
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()

    assert len(session.calls) == 1
    script = session.calls[0]
    assert "ExtAPI.DataModel" in script
    assert "Project" in script
    assert "Model" in script
    assert "Analyses" in script
    assert "Environments" in script
    assert "AnalysisList" in script
    assert "TARGET_OBJECT_ID = 17" in script
    assert "analysis.Solve" not in script
    assert 'selected["analysis"].Solve(WAIT_FOR_SOLVE)' in script
    assert "TARGET_NAME = None" in script
    assert "WAIT_FOR_SOLVE = True" in script
    assert "AnalysisType" in script
    assert "Name" in script
    assert "Caption" in script
    assert "SystemCaption" in script


def test_solve_static_structural_analysis_embeds_name_selector() -> None:
    session = FakeMechanicalSession(
        result=_payload(
            selector={"name": "My Static Structural", "object_id": None},
        )
    )

    result = solve_static_structural_analysis(
        session,
        name="My Static Structural",
    )

    assert result.success is True
    script = session.calls[0]
    assert "TARGET_NAME = 'My Static Structural'" in script
    assert "TARGET_OBJECT_ID = None" in script
    assert "WAIT_FOR_SOLVE = True" in script
    assert result.data["selector"] == {"name": "My Static Structural", "object_id": None}
    assert result.data["wait"] is True


def test_solve_static_structural_analysis_rejects_async_wait() -> None:
    session = FakeMechanicalSession(result=_payload())

    result = solve_static_structural_analysis(session, object_id=17, wait=False)

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_INPUT_ERROR"
    assert "asynchronous solve status" in result.message
    assert session.calls == []


def test_solve_static_structural_analysis_allows_unique_unselected_static_analysis() -> None:
    session = FakeMechanicalSession(
        result=_payload(selector={"name": None, "object_id": None})
    )

    result = solve_static_structural_analysis(session)

    assert result.success is True
    assert result.data["selector"] == {"name": None, "object_id": None}
    assert "TARGET_NAME = None" in session.calls[0]
    assert "TARGET_OBJECT_ID = None" in session.calls[0]


def test_solve_static_structural_analysis_rejects_multiple_selectors() -> None:
    session = FakeMechanicalSession(result=_payload())

    result = solve_static_structural_analysis(session, name="A", object_id=1)

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_INPUT_ERROR"
    assert "at most one" in result.message
    assert session.calls == []


def test_solve_static_structural_analysis_rejects_empty_name() -> None:
    result = solve_static_structural_analysis(FakeMechanicalSession(result=_payload()), name=" ")

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_INPUT_ERROR"
    assert "must not be empty" in result.message


def test_solve_static_structural_analysis_rejects_non_integer_object_id() -> None:
    result = solve_static_structural_analysis(
        FakeMechanicalSession(result=_payload()),
        object_id="17",
    )

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_INPUT_ERROR"
    assert "object_id" in result.message


def test_solve_static_structural_analysis_reports_missing_session_method() -> None:
    result = solve_static_structural_analysis(object(), object_id=17)

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_SESSION_METHOD_MISSING"
    assert "run_python_script" in result.message


def test_solve_static_structural_analysis_wraps_execution_errors() -> None:
    result = solve_static_structural_analysis(
        FakeMechanicalSession(result=_payload(), fail=True),
        object_id=17,
    )

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_EXECUTION_FAILED"
    assert "solver license unavailable" in result.message


def test_solve_static_structural_analysis_wraps_invalid_json() -> None:
    result = solve_static_structural_analysis(
        FakeMechanicalSession(result="not json"),
        object_id=17,
    )

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_PARSE_FAILED"
    assert "invalid JSON" in result.message
    assert result.data == {"raw_result": "not json"}


def test_solve_static_structural_analysis_requires_json_text() -> None:
    result = solve_static_structural_analysis(
        FakeMechanicalSession(result={"status": "ok"}),
        object_id=17,
    )

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_PARSE_FAILED"
    assert "JSON text" in result.message


def test_solve_static_structural_analysis_rejects_unsolved_ok_payload() -> None:
    result = solve_static_structural_analysis(
        FakeMechanicalSession(result=_payload(solved=False)),
        object_id=17,
    )

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_SOLVE_PARSE_FAILED"
    assert "must be true" in result.message


def test_solve_static_structural_analysis_wraps_no_match_status() -> None:
    raw = json.dumps(
        {
            "status": "not_found",
            "selector": {"name": "Missing", "object_id": None},
            "analyses": [
                {
                    "name": "Modal",
                    "object_id": 2,
                    "type": "Modal",
                    "caption": "Modal",
                }
            ],
        }
    )

    result = solve_static_structural_analysis(
        FakeMechanicalSession(result=raw),
        name="Missing",
    )

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_ANALYSIS_NOT_FOUND"
    assert "No matching" in result.message
    assert result.data == {
        "selector": {"name": "Missing", "object_id": None},
        "analyses": [
            {
                "name": "Modal",
                "object_id": 2,
                "type": "Modal",
                "caption": "Modal",
            }
        ],
    }


def test_solve_static_structural_analysis_wraps_multiple_match_status() -> None:
    raw = json.dumps(
        {
            "status": "multiple_matches",
            "selector": {"name": None, "object_id": None},
            "analyses": [
                {
                    "name": "Static Structural",
                    "object_id": 1,
                    "type": "StaticStructural",
                    "caption": "Static Structural",
                },
                {
                    "name": "Static Structural 2",
                    "object_id": 2,
                    "type": "Static Structural",
                    "caption": "Static Structural 2",
                },
            ],
        }
    )

    result = solve_static_structural_analysis(FakeMechanicalSession(result=raw))

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_ANALYSIS_MULTIPLE_MATCHES"
    assert "Multiple matching" in result.message
    assert [analysis["object_id"] for analysis in result.data["analyses"]] == [1, 2]


def test_solve_static_structural_analysis_wraps_not_static_status() -> None:
    raw = json.dumps(
        {
            "status": "not_static_structural",
            "selector": {"name": "Modal", "object_id": None},
            "analyses": [
                {
                    "name": "Modal",
                    "object_id": 3,
                    "type": "Modal",
                    "caption": "Modal",
                }
            ],
        }
    )

    result = solve_static_structural_analysis(
        FakeMechanicalSession(result=raw),
        name="Modal",
    )

    assert result.success is False
    assert result.error == "STATIC_STRUCTURAL_ANALYSIS_NOT_STATIC_STRUCTURAL"
    assert "not a Static Structural" in result.message
    assert result.data["analyses"][0]["type"] == "Modal"
