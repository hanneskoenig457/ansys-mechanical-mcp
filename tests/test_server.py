import pytest

from ansys_mechanical_mcp.server import create_mcp_server


@pytest.mark.anyio
async def test_server_registers_check_environment_tool() -> None:
    server = create_mcp_server()

    tools = await server.list_tools()

    assert [tool.name for tool in tools] == ["check_environment"]


@pytest.mark.anyio
async def test_check_environment_tool_returns_structured_payload() -> None:
    server = create_mcp_server()

    _content, structured = await server.call_tool("check_environment", {})

    assert structured["success"] is True
    assert structured["data"]["ready"]["mcp_server"] is True
    assert "packages" in structured["data"]
