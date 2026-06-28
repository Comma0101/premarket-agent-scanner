"""Agent-callable tool layer.

Public surface:
- ``tools``        — JSON tool functions (scan_premarket, list_universes, get_ticker_snapshot)
- ``definitions``  — tool-use schemas (TOOLS) and ``dispatch``

These wrappers are called directly by whatever agent drives the scanner
(opencode, Claude, Codex, etc.). There is no built-in LLM/API loop: the agent
invokes ``dispatch(name, input)`` or the functions in ``tools`` and reads the
JSON result as ground truth.
"""

from agent_tools import definitions, tools

__all__ = ["tools", "definitions"]
