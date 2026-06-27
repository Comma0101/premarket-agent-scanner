from __future__ import annotations

import json
from pathlib import Path

from app.db import get_cached_previous_close, get_connection, insert_snapshot
from app.models import CombinedSnapshot, ProviderPriceData, utc_now_iso
from providers.alpaca_provider import AlpacaProvider
from providers.yfinance_provider import YFinanceProvider


class SnapshotService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        self.yfinance = YFinanceProvider()
        self.alpaca = AlpacaProvider(db_path=db_path)

    def get_snapshot(self, ticker: str) -> CombinedSnapshot:
        normalized = ticker.upper()
        yf = self.yfinance.get_snapshot(normalized)
        alpaca = self.alpaca.get_snapshot(normalized)
        with get_connection(self.db_path) as conn:
            cached_prev = get_cached_previous_close(conn, normalized)

        previous_close = alpaca.previous_close or yf.previous_close or cached_prev
        premarket_price = yf.premarket_price or alpaca.premarket_price or alpaca.latest_price or yf.latest_price
        latest_price = yf.latest_price or alpaca.latest_price or premarket_price
        timestamp = yf.timestamp or alpaca.timestamp or utc_now_iso()
        sources = [s.source for s in [yf, alpaca] if s and not s.error]
        notes = [*yf.notes, *alpaca.notes]
        snap = CombinedSnapshot(
            ticker=normalized,
            timestamp=timestamp,
            previous_close=previous_close,
            premarket_price=premarket_price,
            latest_price=latest_price,
            open_price=yf.open_price or alpaca.open_price,
            high=yf.high or alpaca.high,
            low=yf.low or alpaca.low,
            volume=yf.volume or alpaca.volume,
            source_primary=sources[0] if sources else None,
            source_secondary=sources[1] if len(sources) > 1 else None,
            confidence="LOW_CONFIDENCE",
            sources=sources,
            notes=notes,
            raw_yfinance_json=json.dumps(yf.raw, sort_keys=True) if yf.raw else None,
            raw_alpaca_json=json.dumps(alpaca.raw, sort_keys=True) if alpaca.raw else None,
            yfinance_data=yf,
            alpaca_data=alpaca,
        )
        return snap

    def save_snapshot(self, snapshot: CombinedSnapshot) -> None:
        with get_connection(self.db_path) as conn:
            insert_snapshot(conn, snapshot)
