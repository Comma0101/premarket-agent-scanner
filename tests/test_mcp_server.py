"""MCP transport tests.

Offline. They verify the server advertises exactly the agent tool schemas and
routes calls through dispatch() — the protocol plumbing — without touching the
network. The scanner/dispatch behavior itself is covered by test_agent_tools.
"""

from __future__ import annotations

import json

import anyio

import mcp_server.server as mcp_server
from agent_tools import definitions


def test_list_tools_matches_tool_definitions():
    tools = anyio.run(mcp_server.list_tools)
    names = {t.name for t in tools}
    assert names == {t["name"] for t in definitions.TOOLS}
    for tool in tools:
        assert tool.description
        assert tool.inputSchema["type"] == "object"


def test_call_tool_routes_through_dispatch(monkeypatch):
    captured: dict = {}

    def fake_dispatch(name, arguments, **kwargs):
        captured["name"] = name
        captured["arguments"] = arguments
        return {"ok": True, "echo": arguments}

    monkeypatch.setattr(mcp_server, "dispatch", fake_dispatch)

    out = anyio.run(mcp_server.call_tool, "scan_premarket", {"tickers": "NVDA"})

    assert captured["name"] == "scan_premarket"
    assert captured["arguments"] == {"tickers": "NVDA"}
    assert len(out) == 1
    payload = json.loads(out[0].text)
    assert payload == {"ok": True, "echo": {"tickers": "NVDA"}}


def test_call_tool_tolerates_missing_arguments(monkeypatch):
    monkeypatch.setattr(mcp_server, "dispatch", lambda name, arguments, **kw: {"name": name, "args": arguments})
    out = anyio.run(mcp_server.call_tool, "list_universes", None)
    payload = json.loads(out[0].text)
    assert payload == {"name": "list_universes", "args": {}}
