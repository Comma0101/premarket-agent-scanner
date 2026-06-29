from __future__ import annotations

import json

from typer.testing import CliRunner

from agent_orchestrator.models import AgentRunPacket
from agent_orchestrator.trading_agent import TradingAgentOrchestrator


def _candidate(
    *,
    ticker: str = "HOT",
    grade: str = "A_WATCH",
    score: int = 92,
    missing_fields: list[str] | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "name": f"{ticker} Corp.",
        "market_cap": 95_000_000,
        "gap_pct": 18.5,
        "gap_dollar": 0.74,
        "volume": 8_500_000,
        "rel_volume": 6.2,
        "confidence": "OK",
        "score": score,
        "grade": grade,
        "matched_signals": ["small_cap_fit", "strong_gap", "high_rvol"],
        "missing_fields": missing_fields or ["short_interest", "borrow_cost"],
        "risk_notes": ["short_interest is unknown; do not infer it from price or volume."],
        "sources": ["fake"],
        "evidence": {
            "ticker": ticker,
            "float_shares": 8_000_000,
            "shares_outstanding": 20_000_000,
            "float_source": "fake-profile",
            "exchange": "NASDAQ",
            "is_low_float": True,
            "filings": [
                {
                    "ticker": ticker,
                    "form_type": "S-1",
                    "filed_at": "2026-06-28",
                    "accession_number": "0000000000-26-000001",
                    "description": "Registration statement",
                    "source_url": "https://www.sec.gov/Archives/example",
                    "risk_tags": ["offering"],
                }
            ],
            "catalysts": [
                {
                    "ticker": ticker,
                    "headline": "Announces contract",
                    "published_at": "2026-06-28T12:00:00Z",
                    "source": "PR",
                    "url": "https://example.test/news",
                    "summary": "Contract headline",
                    "confidence": "OK",
                }
            ],
            "former_runner": {
                "ticker": ticker,
                "event_date": "2026-06-01",
                "max_gap_pct": 180.0,
                "max_volume": 12_000_000,
                "source_run_id": "run123",
                "notes": ["prior large gap"],
            },
            "missing_fields": missing_fields or ["short_interest", "borrow_cost"],
            "risk_notes": ["offering filing present"],
            "sources": ["fake-profile", "sec"],
            "updated_at": "2026-06-28T12:30:00Z",
        },
        "timestamp": "2026-06-28T12:00:00Z",
    }


def test_orchestrator_calls_small_cap_tool_and_buckets_candidates():
    calls = []

    def fake_dispatch(name, tool_input, *, user_query=None, db_path=None):
        calls.append((name, tool_input, user_query, db_path))
        return {
            "preset": "sykes_small_cap_v0",
            "run_ids": ["run-1"],
            "candidate_count": 2,
            "candidates": [
                _candidate(ticker="HOT", grade="A_WATCH", score=92),
                _candidate(ticker="COOL", grade="B_WATCH", score=68),
            ],
            "notes": ["watchlist context only"],
        }

    packet = TradingAgentOrchestrator(dispatcher=fake_dispatch).run_sykes_small_cap_watchlist(
        tickers="HOT,COOL",
        user_query="find small-cap watchlist names",
        db_path="agent.sqlite",
    )

    assert calls == [
        (
            "scan_small_caps",
            {
                "preset_name": "sykes_small_cap_v0",
                "tickers": "HOT,COOL",
            },
            "find small-cap watchlist names",
            "agent.sqlite",
        )
    ]
    assert packet.status == "OK"
    assert packet.agent_name == "sykes_style_small_cap_agent"
    assert packet.strategy == "sykes_small_cap_watchlist"
    assert packet.tool_calls[0].result_summary == "2 candidate(s)"
    assert packet.watchlist["primary_watch"][0].ticker == "HOT"
    assert packet.watchlist["secondary_watch"][0].ticker == "COOL"
    assert packet.watchlist["context_watch"] == []
    assert any("buy/sell" in guardrail for guardrail in packet.guardrails)
    assert any("HOT missing evidence: short_interest, borrow_cost" == warning for warning in packet.warnings)
    assert any("COOL missing evidence: short_interest, borrow_cost" == warning for warning in packet.warnings)

    as_dict = packet.to_dict()
    hot = as_dict["watchlist"]["primary_watch"][0]
    assert hot["evidence_summary"] == (
        "float=8.0M low; catalyst=PR: Announces contract; "
        "filing_risk=offering; former_runner=yes"
    )
    assert "Use only the scanner packet" in as_dict["handoff_prompt"]


def test_orchestrator_can_run_market_scan():
    calls = []

    def fake_dispatch(name, tool_input, *, user_query=None, db_path=None):
        calls.append((name, tool_input))
        return {
            "preset": "sykes_small_cap_v0",
            "run_ids": [],
            "candidate_count": 0,
            "candidates": [],
            "notes": ["Market universe us-listed resolved 4000 symbol(s)."],
        }

    packet = TradingAgentOrchestrator(dispatcher=fake_dispatch).run_sykes_small_cap_watchlist(
        market="us-listed",
        market_limit=100,
    )

    assert calls == [
        (
            "scan_small_caps",
            {
                "preset_name": "sykes_small_cap_v0",
                "market": "us-listed",
                "market_limit": 100,
            },
        )
    ]
    assert packet.status == "OK"
    assert packet.notes == ["Market universe us-listed resolved 4000 symbol(s)."]


def test_orchestrator_returns_error_packet_for_tool_error():
    def fake_dispatch(name, tool_input, *, user_query=None, db_path=None):
        return {"error": "scan_small_caps failed: provider offline"}

    packet = TradingAgentOrchestrator(dispatcher=fake_dispatch).run_sykes_small_cap_watchlist(
        tickers="HOT"
    )

    assert packet.status == "ERROR"
    assert packet.watchlist == {
        "primary_watch": [],
        "secondary_watch": [],
        "context_watch": [],
    }
    assert packet.tool_calls[0].result_summary == "scan_small_caps failed: provider offline"
    assert packet.warnings == ["scan_small_caps failed: provider offline"]


def test_orchestrator_requires_selection_before_calling_tool():
    calls = []

    def fake_dispatch(name, tool_input, *, user_query=None, db_path=None):
        calls.append(name)
        return {}

    packet = TradingAgentOrchestrator(dispatcher=fake_dispatch).run_sykes_small_cap_watchlist()

    assert calls == []
    assert packet.status == "ERROR"
    assert packet.tool_calls == []
    assert packet.warnings == [
        "Pick a selection: tickers, universe, watchlist, market, or all_universes."
    ]


def test_run_agent_cli_json_output(monkeypatch):
    from cli import run_agent

    class FakeOrchestrator:
        def run_sykes_small_cap_watchlist(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 25
            return AgentRunPacket(
                agent_name="sykes_style_small_cap_agent",
                strategy="sykes_small_cap_watchlist",
                status="OK",
                tool_calls=[],
                watchlist={
                    "primary_watch": [],
                    "secondary_watch": [],
                    "context_watch": [],
                },
                guardrails=["No execution advice."],
                warnings=[],
                notes=["fake"],
                handoff_prompt="Use only the scanner packet.",
            )

    monkeypatch.setattr(run_agent, "TradingAgentOrchestrator", FakeOrchestrator)

    result = CliRunner().invoke(
        run_agent.app,
        ["--market", "us-listed", "--market-limit", "25", "--json"],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["agent_name"] == "sykes_style_small_cap_agent"
    assert data["status"] == "OK"
    assert data["notes"] == ["fake"]
