from cli.lance_data_used import data_used_lines


def test_data_used_lines_include_lance_swing_bias():
    lines = data_used_lines({
        "data_used": {
            "candidate_rows": [
                {
                    "ticker": "APPS",
                    "intraday_state": "wait",
                    "swing_state": "mean_reversion_watch",
                    "swing_playbook": "swing_mean_reversion_reclaim",
                    "swing_bias": "long_bias",
                    "latest_price": 11.71,
                    "gap_pct": -7.91,
                    "rel_volume": 0.71,
                    "rel_volume_basis": "session_volume_vs_average_daily_volume",
                    "gap_basis": "last_trade",
                    "confidence": "OK",
                    "data_status": "live",
                    "as_of_et": "Jul 6 1:59 PM ET",
                    "sources": ["yfinance", "alpaca"],
                },
            ],
        },
    })

    assert "bias=long_bias" in lines[0]
    assert "rvol_basis=session_volume_vs_average_daily_volume" in lines[0]
