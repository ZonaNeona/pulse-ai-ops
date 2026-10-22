"""MCP server over the tool registry, for Hermes Agent and any MCP client (Claude Desktop, IDE agents).

Hermes spawns it over stdio. The tool list is generated from `tools.TOOLS` — there is no second copy of
names, descriptions or schemas to drift apart. The visitor session of the current turn comes from the
turn file written by `agents.hermes`, so drafts land in the right visitor's list.

    python -m pulse.agents.mcp_server
"""

import json
from typing import Any

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from pulse.agents import tools


async def list_tools(ctx: Any, params: types.PaginatedRequestParams | None) -> types.ListToolsResult:
    return types.ListToolsResult(
        tools=[
            types.Tool(name=t.name, description=t.description, input_schema=t.parameters) for t in tools.TOOLS.values()
        ]
    )


async def call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
    if params.name not in tools.TOOLS:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Нет инструмента {params.name}")], is_error=True
        )
    token = tools.session.set(tools.current_session())
    try:
        result = await tools.run(params.name, dict(params.arguments or {}))
    finally:
        tools.session.reset(token)
    failed = isinstance(result, dict) and "error" in result
    text = json.dumps(result, ensure_ascii=False, default=str)
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=failed)


server = Server(
    "pulse-ops",
    version="1.0",
    instructions="Инструменты демо-стенда «Пульс»: CRM, 1С, документы, регламенты.",
    on_list_tools=list_tools,
    on_call_tool=call_tool,
)


async def serve() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(serve)
