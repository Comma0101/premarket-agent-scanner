"""NY time / session context helpers for human-facing Desk output.

The data layer records everything in UTC. The Desk and CLI render in America/New_York
and want to know whether a price is a live premarket print, a regular-session quote, or
a stale off-session move. This module is the single place that derives that context.

Prime directive guardrail: every value here is *derived* from a UTC timestamp already
in the data layer. We do not invent prices, gaps, or confidence labels — we only format
and bucket existing timestamps.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo


NY_TZ = ZoneInfo("America/New_York")
UTC = timezone.utc

SessionMode = Literal["PRE_MARKET", "MARKET_OPEN", "POST_MARKET", "OFF_SESSION"]


def parse_iso_utc(value: str | None) -> datetime | None:
    """Parse an ISO timestamp into a tz-aware UTC datetime.

    Returns None when the value is missing or unparseable — callers should treat that
    as "timestamp unknown" and surface it as such, never invent one.
    """
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_et(value: str | datetime | None, *, now: datetime | None = None) -> str | None:
    """Format a UTC timestamp as a short human-readable ET string.

    Example: ``2026-06-29T20:00:00Z`` -> ``"Jun 29 4:00 PM ET"``.
    Returns None when the timestamp is missing/unparseable.
    """
    parsed = _coerce(value, now=now)
    if parsed is None:
        return None
    ny = parsed.astimezone(NY_TZ)
    # %-I / %-M are platform-dependent; build the string manually for stability.
    hour12 = ny.hour % 12 or 12
    minute = ny.minute
    suffix = "AM" if ny.hour < 12 else "PM"
    return f"{ny.strftime('%b %-d')} {hour12}:{minute:02d} {suffix} ET"


def session_mode_for(value: str | datetime | None, *, now: datetime | None = None) -> SessionMode:
    """Bucket a UTC timestamp into the active US equity session.

    Rules (ET clock time, no holiday calendar in this PR):
      - PRE_MARKET  : 04:00 <= t < 09:30
      - MARKET_OPEN : 09:30 <= t < 16:00
      - POST_MARKET : 16:00 <= t < 20:00
      - OFF_SESSION : everything else
    """
    parsed = _coerce(value, now=now)
    if parsed is None:
        return "OFF_SESSION"
    ny_time = parsed.astimezone(NY_TZ).time()
    if time(4, 0) <= ny_time < time(9, 30):
        return "PRE_MARKET"
    if time(9, 30) <= ny_time < time(16, 0):
        return "MARKET_OPEN"
    if time(16, 0) <= ny_time < time(20, 0):
        return "POST_MARKET"
    return "OFF_SESSION"


def session_banner_for(value: str | datetime | None, *, now: datetime | None = None) -> str:
    """One-line session banner for the top of a morning brief.

    Example output: ``"POST_MARKET, Jun 29 7:48 PM ET. last_trade means prior/last-session move, not live premarket."``
    """
    parsed = _coerce(value, now=now)
    if parsed is None:
        return "OFF_SESSION. timestamps unavailable."
    mode = session_mode_for(parsed)
    et_label = format_et(parsed)
    suffix = _session_suffix(mode)
    if et_label is None:
        return f"{mode}. {suffix}"
    return f"{mode}, {et_label}. {suffix}"


def data_caveat_for(
    timestamp: str | datetime | None,
    *,
    gap_basis: str | None,
    confidence: str | None,
    now: datetime | None = None,
) -> str | None:
    """Per-row human-readable caveat describing the data quality + session state.

    Returns None when the row is a clean premarket print (no caveat needed).
    Otherwise returns a single sentence so the desk can drop it into the table.
    """
    parsed = _coerce(timestamp, now=now)
    mode = session_mode_for(parsed)
    et_label = format_et(parsed)
    as_of = f"as of {et_label}" if et_label is not None else "as of unknown time"

    # Clean premarket: no caveat — silence is the signal.
    if gap_basis == "premarket" and confidence == "OK":
        return None

    basis_label = gap_basis or "unknown"
    confidence_label = confidence or "unknown"

    if gap_basis == "last_trade" and confidence == "STALE_DATA":
        return (
            f"{mode}: {basis_label} / {confidence_label} {as_of}. "
            "Not a live premarket gap."
        )
    if gap_basis == "last_trade" and mode == "MARKET_OPEN":
        return (
            f"{mode}: {basis_label} regular-session quote vs prior close {as_of}. "
            "Not a premarket gap."
        )
    if gap_basis == "last_trade":
        return (
            f"{mode}: {basis_label} vs prior close {as_of}. "
            "Off-session; not a confirmed premarket move."
        )
    if gap_basis is None:
        return f"{mode}: no effective price / {confidence_label} {as_of}."
    return f"{mode}: {basis_label} / {confidence_label} {as_of}."


def _session_suffix(mode: SessionMode) -> str:
    if mode == "PRE_MARKET":
        return "Live premarket quotes are eligible for premarket-gap grading."
    if mode == "MARKET_OPEN":
        return "Regular session; effective price is a regular-session quote."
    if mode == "POST_MARKET":
        return "last_trade means prior/last-session move, not live premarket."
    return "Outside US equity trading hours; effective price is not live."


def _coerce(
    value: str | datetime | None,
    *,
    now: datetime | None,
) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if value is not None:
        return parse_iso_utc(value)
    if now is not None:
        return now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
    return None


__all__ = [
    "NY_TZ",
    "SessionMode",
    "parse_iso_utc",
    "format_et",
    "session_mode_for",
    "session_banner_for",
    "data_caveat_for",
]
