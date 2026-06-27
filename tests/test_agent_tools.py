"""Agent tool-layer tests: JSON tools, the dispatcher, and the runner loop.

All offline. Tools run against injected fake providers; the runner is exercised
with a stub Anthropic client so we verify the tool-use loop without a key.
"""

from __future__ import annotations

from agent_tools import definitions, tools
from agent_tools.runner import PremarketAgent
from app.models import ProviderPriceData, utc_now_iso
from services.scanner_service import ScannerService
from services.snapshot_service import SnapshotService
from services.universe_service import UniverseService


class FakePriceProvider:
    source_name = "fake"

    def __init__(self, quotes):
        self._quotes = quotes

    def get_snapshot(self, ticker):
        t = ticker.upper()
        if t in self._quotes:
            return self._quotes[t]
        return ProviderPriceData(ticker=t, source=self.source_name, error="not_found")


def _quote(ticker, prev, pre, cap):
    return ProviderPriceData(
        ticker=ticker,
        source="yfinance",
        previous_close=prev,
        premarket_price=pre,
        latest_price=pre,
        volume=2_000_000,
        timestamp=utc_now_iso(),
        raw={"marketCap": cap},
    )


def _scanner(quotes):
    return ScannerService(
        UniverseService(),
        SnapshotService(yf_provider=FakePriceProvider(quotes)),
        persist=False,
    )


def test_scan_premarket_tool_returns_json_dict():
    quotes = {
        "NVDA": _quote("NVDA", 100.0, 107.0, 3.0e12),  # +7%
        "AMD": _quote("AMD", 100.0, 100.5, 2.5e11),  # +0.5%
    }
    out = tools.scan_premarket(
        tickers="NVDA,AMD", min_gap_abs=5.0, direction="up", service=_scanner(quotes)
    )
    assert out["result_count"] == 1
    assert out["results"][0]["ticker"] == "NVDA"
    assert out["results"][0]["gap_pct"] == 7.0
    assert out["status"] == "OK"


def test_scan_premarket_tool_validates_selection_and_direction():
    assert "error" in tools.scan_premarket()
    assert "error" in tools.scan_premarket(tickers="NVDA", direction="sideways")


def test_list_universes_tool_shape():
    out = tools.list_universes(service=UniverseService())
    assert "MAG7" in out["universes"]
    assert out["universes"]["MAG7"]["count"] == len(out["universes"]["MAG7"]["tickers"])


def test_get_ticker_snapshot_tool():
    quotes = {"NVDA": _quote("NVDA", 100.0, 104.0, 3.0e12)}
    snap_service = SnapshotService(yf_provider=FakePriceProvider(quotes))
    out = tools.get_ticker_snapshot(ticker="NVDA", snapshot_service=snap_service)
    assert out["ticker"] == "NVDA"
    assert out["gap_pct"] == 4.0
    assert out["confidence"] == "OK"


def test_dispatch_unknown_tool():
    assert "error" in definitions.dispatch("nope", {})


def test_tool_definitions_are_well_formed():
    names = {t["name"] for t in definitions.TOOLS}
    assert names == {"scan_premarket", "list_universes", "get_ticker_snapshot"}
    for tool in definitions.TOOLS:
        assert tool["description"]
        assert tool["input_schema"]["type"] == "object"
        assert "properties" in tool["input_schema"]


# --- Runner loop with a stubbed Anthropic client -------------------------------


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Response:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class _StubMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _StubClient:
    def __init__(self, responses):
        self.messages = _StubMessages(responses)


def test_runner_executes_tool_then_returns_answer():
    # Turn 1: Claude asks to call list_universes. Turn 2: Claude answers.
    responses = [
        _Response(
            content=[_Block(type="tool_use", id="t1", name="list_universes", input={})],
            stop_reason="tool_use",
        ),
        _Response(
            content=[_Block(type="text", text="There are several AI universes defined.")],
            stop_reason="end_turn",
        ),
    ]
    agent = PremarketAgent(client=_StubClient(responses))
    answer = agent.ask("What universes exist?")

    assert answer == "There are several AI universes defined."
    # Second call must carry the tool_result back to the model.
    second_call_messages = agent._client.messages.calls[1]["messages"]
    tool_result_blocks = [
        block
        for m in second_call_messages
        if isinstance(m["content"], list)
        for block in m["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]
    assert len(tool_result_blocks) == 1
    assert tool_result_blocks[0]["tool_use_id"] == "t1"
