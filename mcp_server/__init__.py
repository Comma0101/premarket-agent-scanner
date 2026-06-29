"""MCP transport for the premarket scanner.

Exposes the existing agent tool layer (agent_tools) over the Model Context
Protocol so any MCP-capable agent — Claude Code, opencode, codex — can call the
same ground-truth tools the CLI and tests use. No scanner logic lives here.
"""

# Note: do NOT re-export the `server` Server instance here. Binding the name
# `server` in this package namespace would shadow the `mcp_server.server`
# submodule, breaking `import mcp_server.server`. Import the instance from the
# submodule directly if you need it.
from mcp_server.server import SERVER_NAME, main

__all__ = ["main", "SERVER_NAME"]
