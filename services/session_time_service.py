from __future__ import annotations

from dataclasses import is_dataclass
from datetime import datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
UTC = timezone.utc
SessionMode = Literal["PRE_MARKET", "MARKET_OPEN", "POST_MARKET", "OFF_SESSION"]


def parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_et(
    value: str | datetime | None,
    *,
    now: datetime | None = None,
) -> str | None:
    parsed = _coerce(value, now=now)
    if parsed is None:
        return None
    ny = parsed.astimezone(NY_TZ)
    hour12 = ny.hour % 12 or 12
    suffix = "AM" if ny.hour < 12 else "PM"
    return f"{ny.strftime('%b')} {ny.day} {hour12}:{ny.minute:02d} {suffix} ET"


def ny_date_for(value: str | datetime | None = None, *, now: datetime | None = None) -> str | None:
    parsed = _coerce(value, now=now)
    if parsed is None:
        return None
    return parsed.astimezone(NY_TZ).date().isoformat()


def market_session_context_for(
    value: str | datetime | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    parsed = _coerce(value, now=now) or datetime.now(UTC)
    mode = session_mode_for(parsed)
    return {
        "session_mode": mode,
        "as_of_et": format_et(parsed),
        "trading_date": parsed.astimezone(NY_TZ).date().isoformat(),
        "is_market_open": mode == "MARKET_OPEN",
        "is_market_holiday": False,
        "market_closed_reason": None,
    }


def session_mode_for(
    value: str | datetime | None,
    *,
    now: datetime | None = None,
) -> SessionMode:
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


def session_banner_for(
    value: str | datetime | None,
    *,
    now: datetime | None = None,
) -> str:
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
    halt_status: object | None = None,
    now: datetime | None = None,
) -> str | None:
    halt_caveat = halt_caveat_for(halt_status)
    if halt_caveat is not None:
        return halt_caveat

    parsed = _coerce(timestamp, now=now)
    mode = session_mode_for(parsed)
    et_label = format_et(parsed)
    as_of = f"as of {et_label}" if et_label is not None else "as of unknown time"
    if gap_basis == "premarket" and confidence == "OK":
        return None

    basis_label = gap_basis or "unknown"
    confidence_label = confidence or "unknown"
    if gap_basis == "last_trade" and confidence == "STALE_DATA":
        return (
            f"{mode}: {basis_label} / {confidence_label} {as_of}. "
            "Not a live premarket gap."
        )
    if gap_basis == "last_trade":
        if mode == "MARKET_OPEN":
            return (
                f"{mode}: {basis_label} regular-session quote vs prior close "
                f"{as_of}. Not a premarket gap."
            )
        return (
            f"{mode}: {basis_label} vs prior close {as_of}. "
            "Off-session; not a confirmed premarket move."
        )
    if gap_basis is None:
        return f"{mode}: no effective price / {confidence_label} {as_of}."
    return f"{mode}: {basis_label} / {confidence_label} {as_of}."


def halt_caveat_for(halt_status: object | None) -> str | None:
    if not is_active_halt(halt_status):
        return None
    halt_time = _halt_value(halt_status, "halt_time")
    reason_code = _halt_value(halt_status, "reason_code")
    status = _halt_value(halt_status, "status") or "HALTED"
    et_label = format_et(str(halt_time)) if halt_time else None
    code = f" {reason_code}" if reason_code else ""
    as_of = f" as of {et_label}" if et_label else ""
    return f"HALTED{code}{as_of}: {status}. Verify halt/resume status before acting."


def is_active_halt(halt_status: object | None) -> bool:
    return bool(_halt_value(halt_status, "is_active"))


def _halt_value(halt_status: object | None, key: str) -> object | None:
    if halt_status is None:
        return None
    if isinstance(halt_status, dict):
        return halt_status.get(key)
    if is_dataclass(halt_status) or hasattr(halt_status, key):
        return getattr(halt_status, key, None)
    return None


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
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)
    return None
