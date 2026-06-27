from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import get_config
from app.db import get_api_usage_count, get_connection, increment_api_usage
from app.models import AssetProfile, utc_now_iso
from providers.yfinance_provider import _num


class FMPProvider:
    source_name = "fmp"
    daily_limit = 250

    def __init__(self, api_key: str | None = None, db_path: str | Path | None = None) -> None:
        config = get_config()
        self.api_key = api_key if api_key is not None else config.fmp_api_key
        self.db_path = db_path

    def get_daily_count(self) -> int:
        with get_connection(self.db_path) as conn:
            return get_api_usage_count(conn, self.source_name)

    def can_call(self) -> bool:
        if not self.api_key:
            return False
        return self.get_daily_count() < self.daily_limit

    def get_profile(self, ticker: str) -> AssetProfile | None:
        normalized = ticker.upper()
        if not self.api_key:
            return None
        if not self.can_call():
            return None

        try:
            import requests
        except ImportError:
            return None

        url = f"https://financialmodelingprep.com/api/v3/profile/{normalized}"
        params = {"apikey": self.api_key}

        with get_connection(self.db_path) as conn:
            increment_api_usage(conn, self.source_name)

        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code in {401, 402, 403, 429}:
                return None
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None

        record = _first_record(payload)
        if not record:
            return None

        profile = AssetProfile(
            ticker=normalized,
            name=record.get("companyName") or record.get("companyNameTTM"),
            exchange=record.get("exchangeShortName") or record.get("exchange"),
            sector=record.get("sector"),
            industry=record.get("industry"),
            country=record.get("country"),
            market_cap=_num(record.get("mktCap") or record.get("marketCap")),
            shares_outstanding=_num(record.get("sharesOutstanding")),
            float_shares=_num(record.get("floatShares")),
            source=self.source_name,
            profile_updated_at=utc_now_iso(),
        )
        if not any([profile.name, profile.market_cap, profile.exchange]):
            return None
        return profile


def _first_record(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        return payload
    return None
