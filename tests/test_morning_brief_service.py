from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from services.morning_brief_service import MorningBriefService


class FakeDeskRunService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "generated_at": "2026-06-30T12:28:15Z",
            "ticker_count": 3,
            "selection": {
                "source": "market_scan",
                "market": "us-listed",
                "preset": "sykes_small_cap_v0",
                "run_ids": ["run-1"],
                "candidate_count": 2,
                "candidates": [
                    {
                        "ticker": "HOT",
                        "grade": "A_WATCH",
                        "score": 95,
                        "gap_basis": "premarket",
                        "confidence": "OK",
                        "missing_fields": ["short_interest"],
                        "risk_notes": [],
                    },
                    {
                        "ticker": "WAIT",
                        "grade": "C_WATCH",
                        "score": 45,
                        "gap_basis": "premarket",
                        "confidence": "OK",
                        "missing_fields": ["intraday_bars"],
                        "risk_notes": ["Needs intraday confirmation."],
                    },
                ],
                "notes": ["market scan note"],
            },
            "trader_profiles": ["tim_grittani"],
            "tickers": [
                _desk_item(
                    ticker="HOT",
                    confidence="OK",
                    gap_basis="premarket",
                    gap_pct=18.4,
                    rvol=6.2,
                    market_cap=75_000_000.0,
                    missing_fields=["short_interest"],
                    verdict="Context ready",
                    moment_state="ready_for_profile_review",
                    setup_stack=[
                        {"label": "Data quality", "status": "PASS"},
                        {"label": "Small-cap fit", "status": "PASS"},
                        {"label": "Float / rotation", "status": "PASS"},
                        {"label": "Catalyst context", "status": "PASS"},
                        {"label": "Intraday context", "status": "UNKNOWN"},
                    ],
                ),
                _desk_item(
                    ticker="WAIT",
                    confidence="OK",
                    gap_basis="premarket",
                    gap_pct=8.0,
                    rvol=3.5,
                    market_cap=120_000_000.0,
                    missing_fields=["intraday_bars"],
                    verdict="Context ready",
                    moment_state="ready_for_profile_review",
                    setup_stack=[
                        {"label": "Data quality", "status": "PASS"},
                        {"label": "Small-cap fit", "status": "PASS"},
                        {"label": "Participation", "status": "PASS"},
                        {"label": "Intraday context", "status": "UNKNOWN"},
                    ],
                ),
                _desk_item(
                    ticker="STALE",
                    confidence="STALE_DATA",
                    gap_basis="last_trade",
                    gap_pct=12.0,
                    rvol=1.1,
                    market_cap=90_000_000.0,
                    missing_fields=["catalyst"],
                    verdict="Blocked by data quality",
                    moment_state="not_ready_data_quality",
                    setup_stack=[
                        {"label": "Data quality", "status": "BLOCKED"},
                        {"label": "Small-cap fit", "status": "PASS"},
                    ],
                ),
            ],
            "notes": ["Desk run note"],
            "disclaimer": "Matches your filter — not buy/sell advice. Verify before acting.",
        }


def _desk_item(
    *,
    ticker: str,
    confidence: str,
    gap_basis: str,
    gap_pct: float,
    rvol: float,
    market_cap: float,
    missing_fields: list[str],
    verdict: str,
    moment_state: str,
    setup_stack: list[dict[str, str]],
) -> dict:
    return {
        "ticker": ticker,
        "data_quality": {
            "gap_basis": gap_basis,
            "confidence": confidence,
            "as_of": "2026-06-30T12:28:00Z",
            "sources": ["fake"],
        },
        "views": {
            "tim_grittani": {
                "ticker": ticker,
                "trader": "tim_grittani",
                "verdict": verdict,
                "moment_state": moment_state,
                "data_card": {
                    "source": "fake",
                    "as_of": "2026-06-30T12:28:00Z",
                    "gap_pct": gap_pct,
                    "gap_dollar": 0.42,
                    "gap_basis": gap_basis,
                    "previous_close": 2.20,
                    "premarket_price": 2.62 if gap_basis == "premarket" else None,
                    "latest_price": 2.62,
                    "volume": 2_000_000.0,
                    "rel_volume": rvol,
                    "market_cap": market_cap,
                    "confidence": confidence,
                },
                "setup_stack": setup_stack,
                "what_we_lack": missing_fields,
                "next_needed": missing_fields,
                "disclaimer": "Matches your filter — not buy/sell advice. Verify before acting.",
            }
        },
        "missing_fields": missing_fields,
        "errors": [],
    }


def test_morning_brief_buckets_candidates_and_writes_journal(tmp_path) -> None:
    desk_service = FakeDeskRunService()
    service = MorningBriefService(
        desk_service=desk_service,
        journal_dir=tmp_path,
        now_provider=lambda: datetime(
            2026, 6, 30, 8, 28, tzinfo=ZoneInfo("America/New_York")
        ),
    )

    packet = service.run(profile="tim_grittani", market="us-listed", market_limit=25)

    assert desk_service.calls[0]["market"] == "us-listed"
    assert desk_service.calls[0]["trader_profiles"] == ["tim_grittani"]
    assert packet["agent_name"] == "premarket_desk"
    assert packet["strategy"] == "tim_grittani"
    assert packet["status"] == "OK"
    assert packet["session_mode"] == "PRE_MARKET"
    assert packet["market_opens_in_minutes"] == 62
    assert packet["session_id"] == "2026-06-30-pre-market"
    assert packet["scanned_count"] == 3
    assert packet["filtered_count"] == 2
    assert packet["analyzed_count"] == 3
    assert packet["watchlist"]["primary_watch"][0]["ticker"] == "HOT"
    assert packet["watchlist"]["primary_watch"][0]["grade"] == "A_WATCH"
    assert packet["watchlist"]["primary_watch"][0]["entry_reference"] is None
    assert packet["watchlist"]["monitoring"][0]["ticker"] == "WAIT"
    assert packet["watchlist"]["blocked_data_quality"][0]["ticker"] == "STALE"
    assert packet["data_caveats"] == [
        "STALE: gap_basis=last_trade, confidence=STALE_DATA, as_of=2026-06-30T12:28:00Z"
    ]
    assert packet["consensus_tickers"] == ["HOT", "WAIT"]
    assert "primary" in packet["brief_summary"]
    assert "not buy/sell advice" in packet["guardrails"][0]
    assert "Grittani" not in packet["watchlist"]["primary_watch"][0]["why"]
    assert "gap_basis=premarket" in packet["watchlist"]["primary_watch"][0]["why"]

    journal_path = tmp_path / "2026-06-30.json"
    assert journal_path.exists()
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert journal["session_id"] == "2026-06-30-pre-market"
    assert journal["primary_watch"][0]["ticker"] == "HOT"


def test_morning_brief_can_skip_journal(tmp_path) -> None:
    service = MorningBriefService(
        desk_service=FakeDeskRunService(),
        journal_dir=tmp_path,
        now_provider=lambda: datetime(
            2026, 6, 30, 11, 0, tzinfo=ZoneInfo("America/New_York")
        ),
    )

    packet = service.run(
        profile="default",
        tickers=["HOT"],
        save_journal=False,
    )

    assert packet["strategy"] == "default"
    assert packet["session_mode"] == "MARKET_OPEN"
    assert packet["session_id"] == "2026-06-30-market-open"
    assert not list(tmp_path.iterdir())
