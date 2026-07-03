"""Combine provider data into a single CombinedSnapshot with a confidence label.

The snapshot service is the one place that decides "what is the truth" for a
ticker right now. yfinance is the always-available primary source; Alpaca, when
configured, acts as a structured cross-check that can confirm or flag a price.

No number is invented here. Every field traces back to a provider response.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.models import CombinedSnapshot, HaltStatus, ProviderPriceData, utc_now_iso
from providers.yfinance_provider import YFinanceProvider

# If yfinance and Alpaca disagree on price by more than this fraction, the
# snapshot is flagged CONFLICT rather than silently trusting one source.
CONFLICT_THRESHOLD = 0.03

# A premarket/last price older than this many minutes is treated as STALE.
STALE_AFTER_MINUTES = 30


class SnapshotService:
    def __init__(
        self,
        yf_provider: YFinanceProvider | None = None,
        alpaca_provider: Any | None = None,
        halt_provider: Any | None = None,
    ) -> None:
        self.yf_provider = yf_provider or YFinanceProvider()
        # Alpaca is optional; passing None keeps the scanner yfinance-only.
        self.alpaca_provider = alpaca_provider
        self.halt_provider = halt_provider

    @classmethod
    def with_configured_providers(cls, db_path: str | None = None) -> "SnapshotService":
        """Build a snapshot service that cross-validates with Alpaca when keys exist.

        Without Alpaca credentials this is identical to the default yfinance-only
        service, so behavior is unchanged until an API key is provided.
        """
        from providers.alpaca_provider import AlpacaProvider
        from providers.nasdaq_halt_provider import NasdaqHaltProvider

        alpaca = AlpacaProvider(db_path=db_path)
        return cls(
            yf_provider=YFinanceProvider(),
            alpaca_provider=alpaca if alpaca.is_configured else None,
            halt_provider=NasdaqHaltProvider(),
        )

    def build_snapshot(self, ticker: str) -> CombinedSnapshot:
        normalized = ticker.upper()

        yf_data = self.yf_provider.get_snapshot(normalized)
        alpaca_data: ProviderPriceData | None = None
        if self.alpaca_provider is not None:
            try:
                alpaca_data = self.alpaca_provider.get_snapshot(normalized)
            except Exception as exc:  # provider should not crash a scan
                alpaca_data = ProviderPriceData(
                    ticker=normalized,
                    source=getattr(self.alpaca_provider, "source_name", "alpaca"),
                    notes=[f"Alpaca snapshot raised: {exc}"],
                    error=str(exc),
                )

        halt_status = self._get_halt_status(normalized)
        return self._combine(normalized, yf_data, alpaca_data, halt_status)

    def _get_halt_status(self, ticker: str) -> HaltStatus | None:
        if self.halt_provider is None:
            return None
        try:
            return self.halt_provider.get_halt_status(ticker)
        except Exception as exc:
            return HaltStatus(
                ticker=ticker,
                status="UNKNOWN",
                error=str(exc),
                notes=["NASDAQ halt feed lookup raised an exception."],
            )

    def _combine(
        self,
        ticker: str,
        yf_data: ProviderPriceData,
        alpaca_data: ProviderPriceData | None,
        halt_status: HaltStatus | None = None,
    ) -> CombinedSnapshot:
        sources: list[str] = []
        notes: list[str] = []
        provider_failures: dict[str, str] = {}

        # yfinance is primary for previous close, premarket, and last price.
        previous_close = yf_data.previous_close
        premarket_price = yf_data.premarket_price
        latest_price = yf_data.latest_price
        open_price = yf_data.open_price
        high = yf_data.high
        low = yf_data.low
        volume = yf_data.volume
        timestamp = yf_data.timestamp
        market_cap = _num(yf_data.raw.get("marketCap")) if yf_data.raw else None
        average_volume = _num(yf_data.raw.get("averageVolume")) if yf_data.raw else None

        if yf_data.error:
            notes.append(f"yfinance: {yf_data.error}")
            if yf_data.error != "missing_credentials":
                provider_failures[yf_data.source] = yf_data.error
        else:
            sources.append(yf_data.source)
        notes.extend(yf_data.notes)

        alpaca_usable = alpaca_data is not None and not alpaca_data.error
        if alpaca_usable:
            sources.append(alpaca_data.source)
            notes.extend(alpaca_data.notes)
            # Backfill any gaps yfinance left, without overwriting good data.
            previous_close = previous_close if previous_close is not None else alpaca_data.previous_close
            premarket_price = premarket_price if premarket_price is not None else alpaca_data.premarket_price
            latest_price = latest_price if latest_price is not None else alpaca_data.latest_price
            volume = volume if volume is not None else alpaca_data.volume
            timestamp = timestamp or alpaca_data.timestamp
        elif alpaca_data is not None and alpaca_data.error not in {None, "missing_credentials"}:
            notes.append(f"alpaca: {alpaca_data.error}")
            provider_failures[alpaca_data.source] = alpaca_data.error

        confidence = self._assign_confidence(
            previous_close=previous_close,
            premarket_price=premarket_price,
            latest_price=latest_price,
            timestamp=timestamp,
            yf_data=yf_data,
            alpaca_data=alpaca_data if alpaca_usable else None,
            notes=notes,
        )

        snapshot = CombinedSnapshot(
            ticker=ticker,
            timestamp=timestamp or utc_now_iso(),
            previous_close=previous_close,
            premarket_price=premarket_price,
            latest_price=latest_price,
            open_price=open_price,
            high=high,
            low=low,
            volume=volume,
            source_primary=sources[0] if sources else None,
            source_secondary=sources[1] if len(sources) > 1 else None,
            confidence=confidence,
            data_status=_assign_data_status(
                confidence=confidence,
                sources=sources,
                provider_failures=provider_failures,
            ),
            provider_failures=provider_failures,
            halt_status=halt_status,
            sources=sources,
            notes=notes,
            raw_yfinance_json=json.dumps(yf_data.raw) if yf_data.raw else None,
            raw_alpaca_json=json.dumps(alpaca_data.raw) if alpaca_usable and alpaca_data.raw else None,
            yfinance_data=yf_data,
            alpaca_data=alpaca_data,
        )
        snapshot.market_cap = market_cap
        snapshot.average_volume = average_volume
        return snapshot

    def _assign_confidence(
        self,
        *,
        previous_close: float | None,
        premarket_price: float | None,
        latest_price: float | None,
        timestamp: str | None,
        yf_data: ProviderPriceData,
        alpaca_data: ProviderPriceData | None,
        notes: list[str],
    ) -> str:
        # Hard failure: every source errored and we have nothing to show.
        if yf_data.error and (alpaca_data is None or alpaca_data.error):
            if previous_close is None and premarket_price is None and latest_price is None:
                return "ERROR"

        effective_price = premarket_price if premarket_price is not None else latest_price

        if previous_close is None:
            return "MISSING_PREVIOUS_CLOSE"
        if effective_price is None:
            return "MISSING_PREMARKET_PRICE"

        # Cross-source disagreement beats every softer label.
        if alpaca_data is not None and not alpaca_data.error:
            alpaca_price = (
                alpaca_data.premarket_price
                if alpaca_data.premarket_price is not None
                else alpaca_data.latest_price
            )
            if alpaca_price is not None and effective_price > 0:
                divergence = abs(alpaca_price - effective_price) / effective_price
                if divergence > CONFLICT_THRESHOLD:
                    notes.append(
                        f"yfinance {effective_price:.2f} vs alpaca {alpaca_price:.2f} "
                        f"({divergence * 100:.1f}% apart)."
                    )
                    return "CONFLICT"

        if _is_stale(timestamp):
            return "STALE_DATA"

        # Only one source and it's the unstructured yfinance fallback while
        # premarket price is absent -> treat as soft/low confidence.
        if alpaca_data is None and premarket_price is None:
            return "LOW_CONFIDENCE"

        return "OK"


def _is_stale(timestamp: str | None) -> bool:
    if not timestamp:
        return False
    parsed = _parse_iso(timestamp)
    if parsed is None:
        return False
    age = datetime.now(timezone.utc) - parsed
    return age.total_seconds() > STALE_AFTER_MINUTES * 60


def _parse_iso(value: str) -> datetime | None:
    try:
        text = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _assign_data_status(
    *,
    confidence: str,
    sources: list[str],
    provider_failures: dict[str, str],
) -> str:
    if provider_failures:
        return "provider_failure"
    if not sources:
        return "no_providers"
    if confidence == "STALE_DATA":
        return "stale"
    if confidence == "OK":
        return "live"
    return "partial"
