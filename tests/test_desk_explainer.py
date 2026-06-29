from services.desk_explainer import build_breitstein_ticker_explanation


def _snapshot(**overrides):
    base = {
        "ticker": "MRVL",
        "previous_close": 266.77,
        "premarket_price": None,
        "latest_price": 277.75,
        "gap_pct": 4.12,
        "gap_dollar": 10.98,
        "gap_basis": "last_trade",
        "market_cap": 243_184_893_952.0,
        "volume": 31_025_441.0,
        "rel_volume": 0.72,
        "confidence": "STALE_DATA",
        "sources": ["yfinance"],
        "timestamp": "2026-06-29T20:00:00+00:00",
        "notes": [],
    }
    base.update(overrides)
    return base


def test_breitstein_explainer_makes_stale_last_trade_readable() -> None:
    explanation = build_breitstein_ticker_explanation(
        snapshot=_snapshot(),
        scan_output={
            "preset": "breitstein_mean_reversion_v0",
            "phase": "1",
            "candidate_count": 0,
            "candidates": [],
            "notes": ["Phase 1 underlying watchlist only."],
        },
    )

    assert explanation["ticker"] == "MRVL"
    assert explanation["trader"] == "lance_breitstein"
    assert explanation["verdict"] == "No Phase 1 setup"
    assert explanation["moment_state"] == "not_ready_data_quality"
    assert explanation["data_card"]["source"] == "yfinance"
    assert explanation["data_card"]["session"] == "regular_close"
    assert explanation["data_card"]["price_read"] == "last_trade"
    assert explanation["data_card"]["gap_basis"] == "last_trade"
    assert explanation["data_card"]["confidence"] == "STALE_DATA"

    stack = {item["label"]: item for item in explanation["setup_stack"]}
    assert stack["Universe fit"]["status"] == "PASS"
    assert stack["Move size"]["status"] == "PARTIAL"
    assert stack["Participation"]["status"] == "FAIL"
    assert stack["Premarket data quality"]["status"] == "BLOCKED"
    assert stack["Catalyst context"]["status"] == "UNKNOWN"
    assert stack["Intraday trigger"]["status"] == "UNKNOWN"

    assert "Fresh premarket quote" in explanation["next_needed"]
    assert "Catalyst classification" in explanation["next_needed"]
    assert "2-minute bars and VWAP trigger check" in explanation["next_needed"]
    assert explanation["disclaimer"].startswith("Matches your filter")


def test_breitstein_explainer_summarizes_phase_one_candidate() -> None:
    explanation = build_breitstein_ticker_explanation(
        snapshot=_snapshot(
            ticker="FLUSH",
            gap_basis="premarket",
            confidence="OK",
            premarket_price=47.0,
            latest_price=47.0,
            gap_pct=-6.0,
            gap_dollar=-3.0,
            rel_volume=5.0,
            market_cap=50_000_000_000.0,
            timestamp="2026-06-29T13:30:00+00:00",
        ),
        scan_output={
            "preset": "breitstein_mean_reversion_v0",
            "phase": "1",
            "candidate_count": 1,
            "candidates": [
                {
                    "ticker": "FLUSH",
                    "grade": "A_WATCH",
                    "score": 100,
                    "cap_tier": "large",
                    "abnormal_move": True,
                    "has_catalyst": True,
                    "matched_signals": ["gap_down_flush", "fresh_catalyst_context"],
                    "missing_fields": ["intraday_bars", "vwap"],
                    "risk_notes": [],
                }
            ],
            "notes": [],
        },
    )

    assert explanation["verdict"] == "Phase 1 candidate: A_WATCH"
    assert explanation["moment_state"] == "building_intraday_confirmation"
    assert explanation["candidate"]["score"] == 100
    stack = {item["label"]: item for item in explanation["setup_stack"]}
    assert stack["Premarket data quality"]["status"] == "PASS"
    assert stack["Participation"]["status"] == "PASS"
    assert stack["Catalyst context"]["status"] == "PASS"
    assert stack["Intraday trigger"]["status"] == "UNKNOWN"
