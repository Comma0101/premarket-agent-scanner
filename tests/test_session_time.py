from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from services.session_time_service import (
    data_caveat_for,
    format_et,
    session_banner_for,
    session_mode_for,
)


def test_format_et_preserves_raw_time_meaning_in_new_york() -> None:
    assert format_et("2026-06-30T12:28:00Z") == "Jun 30 8:28 AM ET"


def test_session_mode_for_premarket_market_open_and_postmarket() -> None:
    assert session_mode_for("2026-06-30T12:28:00Z") == "PRE_MARKET"
    assert session_mode_for("2026-06-30T15:00:00Z") == "MARKET_OPEN"
    assert session_mode_for("2026-06-29T23:30:00Z") == "POST_MARKET"


def test_session_banner_explains_last_trade_after_hours() -> None:
    banner = session_banner_for("2026-06-29T23:30:00Z")

    assert banner.startswith("POST_MARKET, Jun 29 7:30 PM ET.")
    assert "last_trade means prior/last-session move" in banner


def test_data_caveat_silent_for_clean_premarket_quote() -> None:
    assert (
        data_caveat_for(
            "2026-06-30T12:28:00Z",
            gap_basis="premarket",
            confidence="OK",
        )
        is None
    )


def test_data_caveat_flags_stale_last_trade_with_et_time() -> None:
    caveat = data_caveat_for(
        "2026-06-29T23:30:00Z",
        gap_basis="last_trade",
        confidence="STALE_DATA",
    )

    assert caveat == (
        "POST_MARKET: last_trade / STALE_DATA as of Jun 29 7:30 PM ET. "
        "Not a live premarket gap."
    )


def test_datetime_inputs_are_supported() -> None:
    value = datetime(2026, 6, 30, 8, 28, tzinfo=ZoneInfo("America/New_York"))

    assert format_et(value) == "Jun 30 8:28 AM ET"
    assert session_mode_for(value) == "PRE_MARKET"
