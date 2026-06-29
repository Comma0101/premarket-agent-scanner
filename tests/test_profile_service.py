from __future__ import annotations

from app.models import AssetProfile
from services.profile_service import ProfileService


class FMPProfileWithoutFloat:
    def can_call(self):
        return True

    def get_profile(self, ticker: str):
        return AssetProfile(
            ticker=ticker.upper(),
            name=f"{ticker.upper()} Corp.",
            exchange="NASDAQ",
            market_cap=100_000_000,
            float_shares=None,
            source="fmp",
        )


class YFinanceProfileWithFloat:
    def get_profile(self, ticker: str):
        return AssetProfile(
            ticker=ticker.upper(),
            float_shares=8_000_000,
            source="yfinance",
        )


def test_profile_service_resolve_float_backfills_missing_primary_float():
    service = ProfileService(
        fmp_provider=FMPProfileWithoutFloat(),
        yfinance_provider=YFinanceProfileWithFloat(),
        db_path=None,
    )

    profile = service.get_profile("HOT")
    float_shares, source = service.resolve_float("HOT")

    assert profile is not None
    assert profile.source == "fmp"
    assert profile.float_shares is None
    assert float_shares == 8_000_000
    assert source == "yfinance"
