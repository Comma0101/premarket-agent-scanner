"""Thin Claude agent loop over the premarket tools.

This is the conversational layer: it hands Claude the tool definitions, runs the
manual tool-use loop, and feeds tool results back until Claude answers. It needs
the ``anthropic`` SDK installed and an ANTHROPIC_API_KEY in the environment —
add those when ready; the rest of the project (CLI, scanner, tools) works
without them.

Model defaults to claude-opus-4-8 with adaptive thinking.
"""

from __future__ import annotations

from typing import Any

from agent_tools.definitions import TOOLS, dispatch

DEFAULT_MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """\
You are a premarket stock scanner assistant. You answer questions about premarket
gaps, market caps, and data confidence for a personal, selected-universe scanner.

Rules:
- Never invent or estimate numbers. Every price, previous close, gap percent,
  market cap, volume, and confidence label MUST come from a tool result. If a
  tool did not return a value, say it is unavailable.
- Use scan_premarket for group/filter questions, get_ticker_snapshot for a single
  name, and list_universes when you need valid universe/watchlist names.
- Surface data-confidence labels honestly. If a row is LOW_CONFIDENCE, CONFLICT,
  STALE_DATA, or MISSING_MARKET_CAP, flag it rather than presenting it as solid.
- This is a data/query tool, not trading advice. Report matches to a filter; do
  not tell the user to buy or sell.
- Be concise. Lead with the answer, then the supporting rows.
"""


class PremarketAgent:
    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 8000,
        db_path: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.db_path = db_path
        self._client = client or _make_client()

    def ask(self, question: str, *, max_turns: int = 8) -> str:
        """Answer a single natural-language question using the tools."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

        for _ in range(max_turns):
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                thinking={"type": "adaptive"},
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                return _final_text(response)

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = dispatch(
                        block.name,
                        dict(block.input),
                        user_query=question,
                        db_path=self.db_path,
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": _json(result),
                        }
                    )
            messages.append({"role": "user", "content": tool_results})

        return "Stopped: reached the maximum number of tool-use turns without a final answer."


def _make_client() -> Any:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "The 'anthropic' package is required for the agent runner. "
            "Install it with: pip install anthropic"
        ) from exc
    return anthropic.Anthropic()


def _final_text(response: Any) -> str:
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip() or "(no text response)"


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
