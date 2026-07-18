import pytest

from ansys_mechanical_mcp.core.tool_result import ToolResult


def test_tool_result_to_dict() -> None:
    result = ToolResult(success=True, message="ok", data={"value": 1})

    assert result.to_dict() == {
        "success": True,
        "message": "ok",
        "data": {"value": 1},
        "error": None,
    }


def test_tool_result_normalizes_to_strict_json_native_values() -> None:
    result = ToolResult(success=True, message="ok", data={7: (1, 2)})  # type: ignore[dict-item]

    assert result.to_dict()["data"] == {"7": [1, 2]}


def test_tool_result_rejects_nonfinite_numbers() -> None:
    result = ToolResult(success=True, message="ok", data={"value": float("nan")})

    with pytest.raises(ValueError):
        result.to_dict()
