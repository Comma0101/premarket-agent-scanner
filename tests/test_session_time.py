"""Offline tests for the NY time / session context helper."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.session_time_service import (
    NY_TZ,
    data_caveat_for,
    format_et,
    parse_iso_utc,
    session_banner_for,
    session_mode_for,
)


def test_parse_iso_utc_handles_z_suffix():
    parsed = parse_iso_utc("2026-06-29T20:00:00Z")
    assert parsed == datetime(2026, 6, 29, 20, 0, tzinfo=timezone.utc)


def test_parse_iso_utc_handles_offset():
    parsed = parse_iso_utc("2026-06-29T20:00:00+00:00")
    assert parsed == datetime(2026, 6, 29, 20, 0, tzinfo=timezone.utc)


def test_parse_iso_utc_returns_none_for_missing_or_bad_value():
    assert parse_iso_utc(None) is None
    assert parse_iso_utc("") is None
    assert parse_iso_utc("not-a-timestamp") is None


def test_format_et_converts_utc_to_new_york():
    # 20:00 UTC == 16:00 ET (same day)
    assert format_et("2026-06-29T20:00:00Z") == "Jun 29 4:00 PM ET"


def test_format_et_handles_midnight_et():
    # 04:00 UTC == 00:00 ET on the same calendar day
    assert format_et("2026-06-29T04:00:00Z") == "Jun 29 12:00 AM ET"


def test_format_et_handles_evening_et_previous_day_calendar():
    # 02:00 UTC on Jun 30 == 22:00 ET on Jun 29
    assert format_et("2026-06-30T02:00:00Z") == "Jun 29 10:00 PM ET"


def test_format_et_handles_noon_et():
    # 16:00 UTC == 12:00 ET
    assert format_et("2026-06-29T16:00:00Z") == "Jun 29 12:00 PM ET"


def test_format_et_returns_none_for_missing_timestamp():
    assert format_et(None) is None
    assert format_et("") is None
    assert format_et("not-a-timestamp") is None


@pytest.mark.parametrize(
    "utc_iso, expected_mode",
    [
        ("2026-06-29T08:00:00Z", "PRE_MARKET"),    # 04:00 ET
        ("2026-06-29T13:29:00Z", "PRE_MARKET"),    # 09:29 ET
        ("2026-06-29T13:30:00Z", "MARKET_OPEN"),   # 09:30 ET
        ("2026-06-29T19:59:00Z", "MARKET_OPEN"),   # 15:59 ET
        ("2026-06-29T20:00:00Z", "POST_MARKET"),   # 16:00 ET
        ("2026-06-29T23:59:00Z", "POST_MARKET"),   # 19:59 ET
        ("2026-06-30T00:00:00Z", "OFF_SESSION"),   # 20:00 ET
        ("2026-06-29T07:59:00Z", "OFF_SESSION"),   # 03:59 ET
    ],
)
def test_session_mode_for(utc_iso, expected_mode):
    assert session_mode_for(utc_iso) == expected_mode


def test_session_mode_for_unknown_timestamp_is_off_session():
    assert session_mode_for(None) == "OFF_SESSION"


def test_session_banner_includes_mode_et_time_and_suffix():
    banner = session_banner_for("2026-06-29T23:00:00Z")  # 19:00 ET = POST_MARKET
    assert banner.startswith("POST_MARKET, Jun 29 7:00 PM ET. ")
    assert "last_trade" in banner


def test_session_banner_premarket_mentions_eligibility():
    banner = session_banner_for("2026-06-29T12:00:00Z")  # 08:00 ET = PRE_MARKET
    assert banner.startswith("PRE_MARKET, Jun 29 8:00 AM ET. ")
    assert "premarket" in banner.lower()


def test_session_banner_handles_missing_timestamp():
    assert session_banner_for(None).startswith("OFF_SESSION")


def test_data_caveat_is_none_for_clean_premarket():
    assert (
        data_caveat_for(
            "2026-06-29T12:00:00Z",
            gap_basis="premarket",
            confidence="OK",
        )
        is None
    )


def test_data_caveat_last_trade_stale_includes_session_mode():
    caveat = data_caveat_for(
        "2026-06-29T23:00:00Z",
        gap_basis="last_trade",
        confidence="STALE_DATA",
    )
    assert caveat is not None
    assert caveat.startswith("POST_MARKET:")
    assert "last_trade" in caveat
    assert "STALE_DATA" in caveat
    assert "Jun 29 7:00 PM ET" in caveat
    assert "Not a live premarket gap" in caveat


def test_data_caveat_last_trade_during_market_open():
    caveat = data_caveat_for(
        "2026-06-29T15:00:00Z",
        gap_basis="last_trade",
        confidence="OK",
    )
    assert caveat is not None
    assert caveat.startswith("MARKET_OPEN:")
    assert "regular-session quote" in caveat
    assert "Off-session" not in caveat


def test_data_caveat_missing_basis():
    caveat = data_caveat_for(
        "2026-06-29T12:00:00Z",
        gap_basis=None,
        confidence="OK",
    )
    assert caveat is not None
    assert "no effective price" in caveat


def test_format_et_accepts_datetime_input():
    dt = datetime(2026, 6, 29, 20, 0, tzinfo=timezone.utc)
    assert format_et(dt) == "Jun 29 4:00 PM ET"


def test_format_et_accepts_naive_datetime_as_utc():
    dt = datetime(2026, 6, 29, 20, 0)
    assert format_et(dt) == "Jun 29 4:00 PM ET"


def test_format_et_accepts_et_datetime():
    dt = datetime(2026, 6, 29, 16, 0, tzinfo=NY_TZ)
    assert format_et(dt) == "Jun 29 4:00 PM ET"
