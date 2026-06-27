from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db import get_asset, get_connection, upsert_asset
from app.models import AssetProfile
from providers.fmp_provider import FMPProvider
from providers.yfinance_provider import YFinanceProvider


def profile_is_stale(profile: dict | None, max_age_days: int = 7) -> bool:
    if not profile or not profile.get("profile_updated_at"):
        return True
    try:
        updated = datetime.fromisoformat(str(profile["profile_updated_at"]).replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - updated > timedelta(days=max_age_days)


class AssetService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        self.fmp = FMPProvider(db_path=db_path)
        self.yfinance = YFinanceProvider()

    def get_or_refresh_profile(self, ticker: str, force: bool = False) -> AssetProfile | None:
        normalized = ticker.upper()
        with get_connection(self.db_path) as conn:
            cached = get_asset(conn, normalized)
            if cached and not force and not profile_is_stale(cached):
                return AssetProfile(**{k: cached[k] for k in AssetProfile.__dataclass_fields__ if k in cached})
        profile = self.fmp.get_profile(normalized) or self.yfinance.get_profile(normalized)
        if profile:
            with get_connection(self.db_path) as conn:
                upsert_asset(conn, profile)
            return profile
        if cached:
            return AssetProfile(**{k: cached[k] for k in AssetProfile.__dataclass_fields__ if k in cached})
        return None

    def refresh_profiles(self, tickers: list[str], force: bool = False) -> list[AssetProfile]:
        output = []
        for ticker in tickers:
            profile = self.get_or_refresh_profile(ticker, force=force)
            if profile:
                output.append(profile)
        return output
