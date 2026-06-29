from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_asset, get_connection, upsert_asset
from app.models import AssetProfile
from providers.fmp_provider import FMPProvider
from providers.yfinance_provider import YFinanceProvider

DEFAULT_PROFILE_MAX_AGE_DAYS = 7


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.rstrip("Z"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ProfileService:
    """Resolves company profiles with a DB cache and provider fallback.

    Order of preference: fresh cached profile -> FMP (budget-limited) ->
    yfinance -> stale cached profile. Market cap is the key field the scanner
    needs for filtering, so profiles without it are still cached (the scanner
    flags them via the MISSING_MARKET_CAP confidence label).
    """

    def __init__(
        self,
        *,
        fmp_provider: Any | None = None,
        yfinance_provider: Any | None = None,
        db_path: str | None = None,
        max_age_days: int = DEFAULT_PROFILE_MAX_AGE_DAYS,
    ) -> None:
        self.fmp_provider = fmp_provider if fmp_provider is not None else FMPProvider()
        self.yfinance_provider = yfinance_provider or YFinanceProvider()
        self.db_path = db_path
        self.max_age_days = max_age_days

    def get_profile(self, ticker: str, *, force_refresh: bool = False) -> AssetProfile | None:
        normalized = ticker.upper()

        if not force_refresh:
            cached = self._load_cached(normalized)
            if cached is not None and self._is_fresh(cached):
                return cached

        fresh = self._fetch_fresh(normalized)
        if fresh is not None:
            self._upsert(fresh)
            return fresh

        # No fresh data available; fall back to a stale cache entry if present.
        if not force_refresh:
            cached = self._load_cached(normalized)
            if cached is not None:
                return cached
        return None

    def refresh_profiles(
        self, tickers: list[str], *, force: bool = False
    ) -> list[AssetProfile]:
        results: list[AssetProfile] = []
        for ticker in tickers:
            profile = self.get_profile(ticker, force_refresh=force)
            if profile is not None:
                results.append(profile)
        return results

    def resolve_float(self, ticker: str) -> tuple[float | None, str | None]:
        normalized = ticker.upper()
        profile = self.get_profile(normalized)
        if profile is not None and profile.float_shares is not None:
            return profile.float_shares, profile.source

        try:
            yfinance_profile = self.yfinance_provider.get_profile(normalized)
        except Exception:
            return None, None
        if yfinance_profile is None or yfinance_profile.float_shares is None:
            return None, None
        return yfinance_profile.float_shares, (
            yfinance_profile.source
            or getattr(self.yfinance_provider, "source_name", None)
            or "yfinance"
        )

    def _fetch_fresh(self, ticker: str) -> AssetProfile | None:
        if self._fmp_available():
            try:
                profile = self.fmp_provider.get_profile(ticker)
            except Exception:
                profile = None
            if profile is not None:
                return profile
        try:
            return self.yfinance_provider.get_profile(ticker)
        except Exception:
            return None

    def _fmp_available(self) -> bool:
        can_call = getattr(self.fmp_provider, "can_call", None)
        if callable(can_call):
            try:
                return bool(can_call())
            except Exception:
                return False
        return True

    def _is_fresh(self, profile: AssetProfile) -> bool:
        updated = _parse_timestamp(profile.profile_updated_at)
        if updated is None:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        return updated >= cutoff

    def _load_cached(self, ticker: str) -> AssetProfile | None:
        if self.db_path is None:
            return None
        conn = self._conn()
        try:
            row = get_asset(conn, ticker)
        finally:
            conn.close()
        if row is None:
            return None
        return _profile_from_row(row)

    def _upsert(self, profile: AssetProfile) -> None:
        if self.db_path is None:
            return
        conn = self._conn()
        try:
            upsert_asset(conn, profile)
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self.db_path)


def _profile_from_row(row: dict[str, Any]) -> AssetProfile:
    field_names = {f for f in AssetProfile.__dataclass_fields__}
    return AssetProfile(**{k: v for k, v in row.items() if k in field_names})
