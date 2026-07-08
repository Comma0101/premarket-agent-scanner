from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import get_lance_watchlist_events
from services.lance_market_scan_service import DISCLAIMER


class LanceSessionTimelineService:
    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def timeline(
        self,
        *,
        session_id: str,
        ticker: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        events = get_lance_watchlist_events(
            self.db_path,
            session_id=session_id,
            ticker=ticker,
            limit=limit,
        )
        if not events:
            return {
                "agent_name": "lance_intraday",
                "session_id": session_id,
                "status": "EMPTY",
                "event_count": 0,
                "tickers": [],
                "notes": ["No Lance watchlist events found for the requested session."],
                "disclaimer": DISCLAIMER,
            }

        grouped: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            grouped.setdefault(str(event["ticker"]), []).append(event)

        tickers = [_ticker_timeline(ticker, ticker_events) for ticker, ticker_events in grouped.items()]
        tickers.sort(
            key=lambda row: (
                len(row["events"]),
                abs(row["score_delta"] or 0),
                row["latest_score"],
            ),
            reverse=True,
        )
        return {
            "agent_name": "lance_intraday",
            "session_id": session_id,
            "status": "OK",
            "event_count": len(events),
            "tickers": tickers,
            "notes": [],
            "disclaimer": DISCLAIMER,
        }


def _ticker_timeline(ticker: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    first = events[0]
    latest = events[-1]
    first_score = float(first.get("score") or 0)
    latest_score = float(latest.get("score") or 0)
    first_quality = first.get("data_quality") or {}
    latest_quality = latest.get("data_quality") or {}
    return {
        "ticker": ticker,
        "first_state": first.get("state"),
        "latest_state": latest.get("state"),
        "first_score": first_score,
        "latest_score": latest_score,
        "score_delta": round(latest_score - first_score, 2),
        "gap_pct_delta": _delta(latest_quality.get("gap_pct"), first_quality.get("gap_pct")),
        "rel_volume_delta": _delta(
            latest_quality.get("rel_volume"),
            first_quality.get("rel_volume"),
        ),
        "events": events,
    }


def _delta(current: Any, previous: Any) -> float | None:
    if isinstance(current, int | float) and isinstance(previous, int | float):
        return round(float(current) - float(previous), 2)
    return None
