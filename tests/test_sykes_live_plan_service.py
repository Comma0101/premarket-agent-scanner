from app.models import (
    CatalystEvent,
    SmallCapCandidate,
    SmallCapEvidence,
    SmallCapScanOutput,
)
from services.sykes_live_plan_service import SykesLivePlanService


def test_sykes_live_plan_builds_intraday_and_swing_watchlists():
    output = SykesLivePlanService(
        scanner_service=FakeSmallCapScannerService([
            _candidate(
                "HOT",
                grade="A_WATCH",
                score=92,
                matched=["small_cap_fit", "strong_gap", "high_rvol", "fresh_hard_catalyst"],
                evidence=SmallCapEvidence(
                    ticker="HOT",
                    float_shares=8_000_000,
                    is_low_float=True,
                    float_rotation=1.4,
                    catalysts=[
                        CatalystEvent(
                            ticker="HOT",
                            headline="Contract win",
                            published_at="2026-07-06T13:05:00Z",
                            source="PRNewswire",
                            catalyst_quality="hard",
                            recency_minutes=20,
                        )
                    ],
                    missing_fields=["filings", "short_interest"],
                    sources=["fmp", "news_rss"],
                ),
            ),
            _candidate(
                "LATE",
                grade="B_WATCH",
                score=72,
                gap_basis="last_trade",
                matched=["small_cap_fit", "gap_up", "rvol_confirmed"],
            ),
        ])
    ).run(tickers="HOT,LATE", summary_limit=5)

    assert output["agent_name"] == "timothy_sykes"
    assert output["mode"] == "live_and_swing"
    assert output["desk_read"]["one_liner"] == "2 intraday watch, 1 swing watch, 0 blocked."
    assert output["intraday_watchlist"][0]["ticker"] == "HOT"
    assert output["intraday_watchlist"][0]["state"] == "primary_live_watch"
    assert output["intraday_watchlist"][0]["setup"] == "catalyst_spiker_watch"
    assert output["intraday_watchlist"][0]["data_quality"]["gap_basis"] == "premarket"
    assert output["intraday_watchlist"][0]["evidence"]["float_rotation"] == 1.4
    assert output["swing_watchlist"][0]["ticker"] == "HOT"
    assert output["swing_watchlist"][0]["state"] == "next_session_watch"
    assert output["swing_watchlist"][0]["setup"] == "catalyst_continuation_watch"
    assert output["auto_slices"][0]["ticker"] == "HOT"
    assert "catalyst_spiker_watch" in output["auto_slices"][0]["why"]
    assert output["scanner"]["live_intraday"] is True
    assert output["disclaimer"] == "Matches your filter - not buy/sell advice. Verify before acting."


def test_sykes_live_plan_blocks_bad_data_quality():
    output = SykesLivePlanService(
        scanner_service=FakeSmallCapScannerService([
            _candidate(
                "BAD",
                grade="REJECT",
                confidence="STALE_DATA",
                matched=["unusable_confidence"],
                risk_notes=["Rejected because confidence is STALE_DATA."],
            )
        ])
    ).run(tickers="BAD", include_rejected=True)

    assert output["intraday_watchlist"] == []
    assert output["swing_watchlist"] == []
    assert output["blocked"][0]["ticker"] == "BAD"
    assert output["blocked"][0]["state"] == "blocked_data_quality"


class FakeSmallCapScannerService:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = []

    def scan(self, **kwargs):
        self.calls.append(kwargs)
        return SmallCapScanOutput(
            preset=kwargs["preset_name"],
            run_ids=["run-1"],
            candidate_count=len([c for c in self.candidates if c.grade != "REJECT"]),
            candidates=[c for c in self.candidates if c.grade != "REJECT"],
            rejected=[c for c in self.candidates if c.grade == "REJECT"],
            rejected_count=len([c for c in self.candidates if c.grade == "REJECT"]),
            notes=["fake scan"],
        )


def _candidate(
    ticker,
    *,
    grade="A_WATCH",
    score=90,
    confidence="OK",
    gap_basis="premarket",
    matched=None,
    risk_notes=None,
    evidence=None,
):
    return SmallCapCandidate(
        ticker=ticker,
        name=None,
        market_cap=100_000_000,
        gap_pct=12.0,
        gap_dollar=1.2,
        volume=2_000_000,
        rel_volume=5.0,
        rel_volume_basis="session_volume_vs_average_daily_volume",
        confidence=confidence,
        score=score,
        grade=grade,
        gap_basis=gap_basis,
        matched_signals=list(matched or ["small_cap_fit", "strong_gap", "high_rvol"]),
        missing_fields=["float", "catalyst", "filings"],
        risk_notes=list(risk_notes or []),
        sources=["fake"],
        evidence=evidence,
        timestamp="2026-07-06T13:30:00Z",
    )
