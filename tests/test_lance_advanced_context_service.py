from __future__ import annotations

from app.db import (
    get_lance_outcomes,
    initialize_database,
    insert_lance_outcome,
)
from app.models import CatalystEvent
from services.lance_advanced_context_service import LanceAdvancedContextService


class FakeMarketScanService:
    def scan(self, **kwargs):
        assert kwargs["max_candidates"] == 3
        return {
            "agent_name": "lance_intraday",
            "session_id": "session-1",
            "status": "OK",
            "scanned_count": 3,
            "candidate_count": 3,
            "watchlist": [
                _candidate("NVDA", gap_pct=6.0, rel_volume=3.4, state="setup_forming"),
                _candidate("AMD", gap_pct=4.0, rel_volume=2.1, state="watching"),
                _candidate("TSLA", gap_pct=-5.0, rel_volume=3.8, state="triggered_reference"),
            ],
            "notes": [],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


class FakeUniverseService:
    def memberships_for_ticker(self, ticker: str) -> list[str]:
        return {
            "NVDA": ["AI_SEMIS_MEMORY", "MAG7"],
            "AMD": ["AI_SEMIS_MEMORY"],
            "TSLA": ["MAG7"],
        }.get(ticker, [])


class FakeBenchmarkService:
    def benchmark_moves(self):
        return {
            "SPY": {"gap_pct": 1.0, "confidence": "OK", "gap_basis": "last_trade"},
            "QQQ": {"gap_pct": 2.0, "confidence": "OK", "gap_basis": "last_trade"},
            "SMH": {"gap_pct": 3.0, "confidence": "OK", "gap_basis": "last_trade"},
        }


class FakeCatalystService:
    def get_recent_catalysts(self, ticker: str):
        if ticker == "NVDA":
            return [
                CatalystEvent(
                    ticker="NVDA",
                    headline="Nvidia raises guidance after earnings beat",
                    published_at="2026-07-01T12:00:00Z",
                    source="fake_news",
                    url="https://example.test/nvda",
                )
            ]
        if ticker == "TSLA":
            return [
                CatalystEvent(
                    ticker="TSLA",
                    headline="Tesla recalls vehicles after regulator review",
                    published_at="2026-07-01T12:10:00Z",
                    source="fake_news",
                    url="https://example.test/tsla",
                )
            ]
        return []


def _candidate(ticker: str, *, gap_pct: float, rel_volume: float, state: str) -> dict:
    return {
        "ticker": ticker,
        "state": state,
        "score": 80,
        "playbook": "mean_reversion_after_capitulation",
        "why_watching": f"{ticker}: {gap_pct}% move, {rel_volume}x RVOL.",
        "invalidates_if": "Invalidation text.",
        "next_step": "Next step.",
        "gap_pct": gap_pct,
        "rel_volume": rel_volume,
        "data_quality": {
            "gap_pct": gap_pct,
            "rel_volume": rel_volume,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 1 10:00 AM ET",
            "sources": ["fake"],
        },
        "conditions": {
            "volume_2x": {"status": "PASS"},
            "consecutive_pressure": {"status": "PASS"},
            "prior_bar_break": {"status": "PASS" if state == "triggered_reference" else "WAITING"},
            "chop_filter": {"status": "PASS"},
        },
        "trigger_reference": (
            {"direction": "long", "price": 101.0, "source": "prior_2min_bar_high_break"}
            if state == "triggered_reference"
            else None
        ),
        "plan": {
            "ticker": ticker,
            "state": state,
            "intraday": {"bar_count": 20, "chop": False},
        },
    }


def test_advanced_lance_scan_adds_market_context_theme_rotation_playbooks_and_memory(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    insert_lance_outcome(
        db_path,
        session_id="prior-session",
        ticker="NVDA",
        playbook="earnings_continuation",
        outcome="worked",
        notes="Prior earnings continuation held relative strength.",
        plan={"ticker": "NVDA", "state": "setup_forming"},
    )

    output = LanceAdvancedContextService(
        market_scan_service=FakeMarketScanService(),
        universe_service=FakeUniverseService(),
        benchmark_service=FakeBenchmarkService(),
        catalyst_service=FakeCatalystService(),
        db_path=db_path,
    ).scan(max_candidates=3)

    assert output["agent_name"] == "lance_intraday"
    assert output["mode"] == "advanced"
    assert output["market_context"]["benchmarks"]["QQQ"]["gap_pct"] == 2.0
    assert output["market_context"]["theme_rotation"][0]["theme"] == "AI_SEMIS_MEMORY"
    assert output["market_context"]["theme_rotation"][0]["ticker_count"] == 2

    nvda = output["watchlist"][0]
    assert nvda["ticker"] == "NVDA"
    assert nvda["relative_strength"]["vs_QQQ"] == 4.0
    assert nvda["relative_strength"]["sector_etf"] == "SMH"
    assert nvda["relative_strength"]["vs_sector_etf"] == 3.0
    assert nvda["relative_strength"]["classification"] == "strong"
    assert nvda["catalyst"]["primary_type"] == "earnings"
    assert nvda["playbook_fit"]["primary"] == "earnings_continuation"
    assert nvda["opening_range_regime"] == "inside_opening_range"
    assert nvda["market_memory"]["recent_outcomes_available"] is True
    assert nvda["market_memory"]["recent_outcomes"][0]["outcome"] == "worked"

    tsla = next(row for row in output["watchlist"] if row["ticker"] == "TSLA")
    assert tsla["relative_strength"]["vs_QQQ"] == -7.0
    assert tsla["relative_strength"]["classification"] == "weak"
    assert tsla["opening_range_regime"] == "range_break"
    assert tsla["playbook_fit"]["primary"] == "mean_reversion_after_capitulation"


def test_lance_outcome_journal_persists_and_reads_rows(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="NVDA",
        playbook="earnings_continuation",
        outcome="worked",
        notes="Held relative strength above QQQ.",
        plan={"ticker": "NVDA", "state": "setup_forming"},
    )

    rows = get_lance_outcomes(db_path, ticker="NVDA")

    assert len(rows) == 1
    assert rows[0]["ticker"] == "NVDA"
    assert rows[0]["outcome"] == "worked"
    assert rows[0]["playbook"] == "earnings_continuation"
    assert rows[0]["plan"]["state"] == "setup_forming"
