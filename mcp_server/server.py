"""MCP server exposing the premarket scanner's JSON tools.

This is a thin transport wrapper. It serves the exact tool schemas from
``agent_tools.definitions.TOOLS`` and routes every call through
``agent_tools.definitions.dispatch``, which is the same ground-truth path the
CLI and tests exercise. No prices, gaps, or caps are computed here — only
protocol plumbing — so every MCP frontend gets identical, tested behavior.

Run it directly (stdio transport):

    .venv/bin/python -m mcp_server.server

or register it in ``.mcp.json`` and let the agent frontend launch it.
"""

from __future__ import annotations

import json

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from agent_tools.definitions import TOOLS, dispatch

SERVER_NAME = "premarket-scanner"

server: Server = Server(SERVER_NAME)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise the scanner tools, reusing the single source of truth."""
    return [
        Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["input_schema"],
        )
        for tool in TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Execute a tool by name and return its JSON result as text content.

    ``dispatch`` is synchronous. Keep this wrapper direct so offline tests and
    stdio tool calls share the same deterministic path.
    """
    result = dispatch(name, arguments or {})
    return [TextContent(type="text", text=json.dumps(result, default=str))]


async def _amain() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    anyio.run(_amain)


if __name__ == "__main__":
    main()
