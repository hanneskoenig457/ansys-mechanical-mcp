from ansys_mechanical_mcp.core.tool_result import ToolResult


def test_tool_result_to_dict() -> None:
    result = ToolResult(success=True, message="ok", data={"value": 1})

    assert result.to_dict() == {
        "success": True,
        "message": "ok",
        "data": {"value": 1},
        "error": None,
    }

