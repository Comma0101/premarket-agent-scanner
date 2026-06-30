from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.config import BASE_DIR
from app.models import utc_now_iso
from services.desk_explainer import DISCLAIMER
from services.session_time_service import (
    data_caveat_for,
    format_et,
    session_banner_for,
    session_mode_for,
)


WATCH_BUCKETS = [
    "primary_watch",
    "secondary_watch",
    "monitoring",
    "context_watch",
    "blocked_data_quality",
    "rejected",
]

GUARDRAILS = [
    DISCLAIMER,
    "Every market number is data-layer sourced; unknown fields remain unknown.",
    "Reference levels are scanner facts, not order instructions.",
]


class MorningBriefService:
    def __init__(
        self,
        *,
        desk_service: Any | None = None,
        journal_dir: Path | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.desk_service = desk_service
        self.journal_dir = journal_dir or BASE_DIR / "data" / "sessions"
        self.now_provider = now_provider
        self.ny_tz = ZoneInfo("America/New_York")

    def run(
        self,
        *,
        profile: str = "default",
        tickers: list[str] | None = None,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        all_universes: bool = False,
        market: str | None = None,
        market_limit: int | None = None,
        max_workers: int | None = None,
        scan_preset_name: str = "sykes_small_cap_v0",
        include_intraday: bool = False,
        include_daily: bool = False,
        refresh_catalysts: bool = False,
        save_journal: bool = True,
    ) -> dict[str, Any]:
        desk_output = self._desk_service().run(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
            scan_preset_name=scan_preset_name,
            trader_profiles=_trader_profiles_for(profile),
            include_intraday=include_intraday,
            include_daily=include_daily,
            refresh_catalysts=refresh_catalysts,
        )
        now_ny = self._now_ny()
        session_mode = _session_mode(now_ny)
        session_id = f"{now_ny.date().isoformat()}-{session_mode.lower().replace('_', '-')}"
        watchlist_packet = _empty_watchlist()
        data_caveats: list[str] = []

        candidates = [
            _brief_candidate(item, desk_output.get("selection") or {}, profile)
            for item in desk_output.get("tickers") or []
        ]
        for candidate in candidates:
            watchlist_packet[candidate["bucket"]].append(candidate)
            if candidate["data_caveat"]:
                data_caveats.append(f"{candidate['ticker']}: {candidate['data_caveat']}")

        for bucket in WATCH_BUCKETS:
            watchlist_packet[bucket].sort(
                key=lambda candidate: (
                    candidate["consensus_score"],
                    _grade_rank(candidate["grade"]),
                    candidate["rvol"] or 0,
                    abs(candidate["gap_pct"] or 0),
                ),
                reverse=True,
            )

        packet = {
            "agent_name": "premarket_desk",
            "strategy": profile,
            "status": "OK",
            "session_mode": session_mode,
            "session_banner": session_banner_for(now_ny),
            "market_opens_in_minutes": _market_opens_in_minutes(now_ny),
            "brief_summary": _brief_summary(watchlist_packet, data_caveats),
            "watchlist": watchlist_packet,
            "consensus_tickers": _consensus_tickers(candidates),
            "market_context": {
                "selection": desk_output.get("selection"),
                "session_mode": session_mode,
            },
            "data_caveats": data_caveats,
            "guardrails": list(GUARDRAILS),
            "warnings": _warnings(desk_output),
            "tool_calls": [
                {
                    "tool_name": "run_desk",
                    "status": "OK",
                    "notes": list(desk_output.get("notes") or []),
                }
            ],
            "handoff_prompt": (
                "Present buckets in order: primary_watch, secondary_watch, monitoring, "
                "then blocked_data_quality. Do not turn references into trade advice."
            ),
            "session_id": session_id,
            "scanned_count": desk_output.get("ticker_count", 0),
            "filtered_count": _filtered_count(desk_output),
            "analyzed_count": len(desk_output.get("tickers") or []),
            "generated_at": utc_now_iso(),
            "source_desk_run": desk_output,
            "disclaimer": DISCLAIMER,
        }

        if save_journal:
            self._write_journal(packet, now_ny)

        return packet

    def _desk_service(self) -> Any:
        if self.desk_service is not None:
            return self.desk_service
        from services.desk_run_service import DeskRunService

        self.desk_service = DeskRunService()
        return self.desk_service

    def _now_ny(self) -> datetime:
        now = self.now_provider() if self.now_provider else datetime.now(self.ny_tz)
        if now.tzinfo is None:
            return now.replace(tzinfo=self.ny_tz)
        return now.astimezone(self.ny_tz)

    def _write_journal(self, packet: dict[str, Any], now_ny: datetime) -> None:
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        journal_path = self.journal_dir / f"{now_ny.date().isoformat()}.json"
        journal = {
            "date": now_ny.date().isoformat(),
            "session_id": packet["session_id"],
            "session_mode": packet["session_mode"],
            "profile": packet["strategy"],
            "brief_generated_at": packet["generated_at"],
            "scanned": packet["scanned_count"],
            "filtered": packet["filtered_count"],
            "analyzed": packet["analyzed_count"],
            "primary_watch": _journal_candidates(packet["watchlist"]["primary_watch"]),
            "secondary_watch": _journal_candidates(packet["watchlist"]["secondary_watch"]),
            "monitoring": _journal_candidates(packet["watchlist"]["monitoring"]),
            "data_caveats": list(packet["data_caveats"]),
        }
        journal_path.write_text(
            json.dumps(journal, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _trader_profiles_for(profile: str) -> list[str]:
    if profile == "default":
        return ["timothy_sykes", "lance_breitstein", "alex_temiz", "tim_grittani"]
    return [profile]


def _brief_candidate(
    item: dict[str, Any],
    selection: dict[str, Any],
    profile: str,
) -> dict[str, Any]:
    ticker = str(item.get("ticker") or "").upper()
    view = _preferred_view(item, profile)
    data_card = view.get("data_card") or {}
    data_quality = item.get("data_quality") or {}
    selection_candidate = _selection_candidate(selection, ticker)
    grade = selection_candidate.get("grade") or _grade_from_view(view)
    confidence = data_quality.get("confidence") or data_card.get("confidence")
    gap_basis = data_quality.get("gap_basis") or data_card.get("gap_basis")
    bucket = _bucket(
        confidence=confidence,
        gap_basis=gap_basis,
        grade=grade,
        view=view,
        missing_fields=item.get("missing_fields") or [],
    )
    scanners_triggered = _sources_triggered(selection_candidate, view)
    consensus_score = len(scanners_triggered)
    as_of = data_quality.get("as_of") or data_card.get("as_of")
    data_caveat = data_caveat_for(
        as_of,
        gap_basis=gap_basis,
        confidence=confidence,
    )

    return {
        "ticker": ticker,
        "name": None,
        "bucket": bucket,
        "grade": grade,
        "gap_pct": data_card.get("gap_pct"),
        "gap_dollar": data_card.get("gap_dollar"),
        "gap_basis": gap_basis,
        "previous_close": data_card.get("previous_close"),
        "rvol": data_card.get("rel_volume"),
        "volume": data_card.get("volume"),
        "dollar_volume": _dollar_volume(data_card),
        "market_cap": data_card.get("market_cap"),
        "confidence": confidence,
        "as_of": as_of,
        "as_of_et": format_et(as_of),
        "as_of_utc": as_of,
        "session_mode": session_mode_for(as_of),
        "row_session_mode": session_mode_for(as_of),
        "data_caveat": data_caveat,
        "sources": list(data_quality.get("sources") or []),
        "consensus_score": consensus_score,
        "scanners_triggered": scanners_triggered,
        "setup_summaries": _setup_summaries(view),
        "run_up_pct": None,
        "consecutive_green_days": None,
        "entry_reference": None,
        "risk_reference": None,
        "reference_source": None,
        "nearest_resistance": None,
        "nearest_support": None,
        "evidence_summary": _evidence_summary(view),
        "why": _why(ticker, bucket, grade, gap_basis, confidence, view),
        "missing_fields": list(item.get("missing_fields") or []),
        "risk_notes": list(selection_candidate.get("risk_notes") or []),
    }


def _preferred_view(item: dict[str, Any], profile: str) -> dict[str, Any]:
    views = item.get("views") or {}
    if profile != "default" and profile in views:
        return dict(views[profile])
    if views:
        return dict(next(iter(views.values())))
    return {}


def _selection_candidate(selection: dict[str, Any], ticker: str) -> dict[str, Any]:
    for candidate in selection.get("candidates") or []:
        if str(candidate.get("ticker") or "").upper() == ticker:
            return dict(candidate)
    return {}


def _grade_from_view(view: dict[str, Any]) -> str:
    if view.get("moment_state") == "not_ready_data_quality":
        return "REJECT"
    pass_count = sum(
        1
        for check in view.get("setup_stack") or []
        if check.get("status") == "PASS" and check.get("label") != "Data quality"
    )
    if pass_count >= 3:
        return "B_WATCH"
    if pass_count >= 1:
        return "C_WATCH"
    return "REJECT"


def _bucket(
    *,
    confidence: str | None,
    gap_basis: str | None,
    grade: str,
    view: dict[str, Any],
    missing_fields: list[str],
) -> str:
    if confidence != "OK" or gap_basis != "premarket":
        return "blocked_data_quality"
    if grade == "A_WATCH":
        return "primary_watch"
    if grade == "B_WATCH":
        return "secondary_watch"
    if "intraday_bars" in missing_fields or _has_unknown_intraday(view):
        return "monitoring"
    if grade == "C_WATCH":
        return "context_watch"
    return "rejected"


def _has_unknown_intraday(view: dict[str, Any]) -> bool:
    for check in view.get("setup_stack") or []:
        if check.get("label") == "Intraday context" and check.get("status") == "UNKNOWN":
            return True
    return False


def _sources_triggered(
    selection_candidate: dict[str, Any],
    view: dict[str, Any],
) -> list[str]:
    triggered: list[str] = []
    if selection_candidate.get("grade") in {"A_WATCH", "B_WATCH", "C_WATCH"}:
        triggered.append("small_cap_scan")
    if view.get("moment_state") != "not_ready_data_quality":
        triggered.append(f"profile:{view.get('trader') or 'unknown'}")
    return triggered


def _setup_summaries(view: dict[str, Any]) -> list[str]:
    summaries = []
    for check in view.get("setup_stack") or []:
        if check.get("status") == "PASS":
            summaries.append(f"{check.get('label')}: PASS")
    return summaries


def _dollar_volume(data_card: dict[str, Any]) -> float | None:
    latest = data_card.get("premarket_price") or data_card.get("latest_price")
    volume = data_card.get("volume")
    if isinstance(latest, int | float) and isinstance(volume, int | float):
        return latest * volume
    return None


def _evidence_summary(view: dict[str, Any]) -> str:
    context = view.get("context") or {}
    evidence = context.get("evidence") or {}
    if not evidence:
        return "evidence=unknown"
    parts = []
    if evidence.get("float_shares") is not None:
        parts.append(f"float={evidence.get('float_shares')}")
    if evidence.get("float_rotation") is not None:
        parts.append(f"rotation={evidence.get('float_rotation')}")
    parts.append(f"catalysts={len(evidence.get('catalysts') or [])}")
    parts.append(f"filings={len(evidence.get('filings') or [])}")
    if evidence.get("former_runner"):
        parts.append("former_runner=yes")
    return "; ".join(parts)


def _why(
    ticker: str,
    bucket: str,
    grade: str,
    gap_basis: str | None,
    confidence: str | None,
    view: dict[str, Any],
) -> str:
    if bucket == "blocked_data_quality":
        return (
            f"{ticker} is blocked by data quality: gap_basis={gap_basis}, "
            f"confidence={confidence}."
        )
    pass_labels = [
        check.get("label")
        for check in view.get("setup_stack") or []
        if check.get("status") == "PASS" and check.get("label")
    ]
    if pass_labels:
        return (
            f"{ticker} is {grade} with gap_basis={gap_basis}, "
            f"confidence={confidence}; passing checks: {', '.join(pass_labels)}."
        )
    return f"{ticker} is {grade} with gap_basis={gap_basis}, confidence={confidence}."


def _empty_watchlist() -> dict[str, list[dict[str, Any]]]:
    return {bucket: [] for bucket in WATCH_BUCKETS}


def _session_mode(now_ny: datetime) -> str:
    current = now_ny.time()
    if time(4, 0) <= current < time(9, 30):
        return "PRE_MARKET"
    if time(9, 30) <= current < time(16, 0):
        return "MARKET_OPEN"
    if time(16, 0) <= current < time(20, 0):
        return "POST_MARKET"
    return "OFF_SESSION"


def _market_opens_in_minutes(now_ny: datetime) -> int | None:
    if _session_mode(now_ny) != "PRE_MARKET":
        return None
    market_open = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
    return int((market_open - now_ny).total_seconds() // 60)


def _brief_summary(
    watchlist_packet: dict[str, list[dict[str, Any]]],
    data_caveats: list[str],
) -> str:
    return (
        f"{len(watchlist_packet['primary_watch'])} primary, "
        f"{len(watchlist_packet['secondary_watch'])} secondary, "
        f"{len(watchlist_packet['monitoring'])} monitoring, "
        f"{len(data_caveats)} data caveat(s)."
    )


def _consensus_tickers(candidates: list[dict[str, Any]]) -> list[str]:
    return [
        candidate["ticker"]
        for candidate in candidates
        if candidate["consensus_score"] >= 2
    ]


def _warnings(desk_output: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for item in desk_output.get("tickers") or []:
        for error in item.get("errors") or []:
            warnings.append(f"{item.get('ticker')}: {error.get('error')}")
    return warnings


def _filtered_count(desk_output: dict[str, Any]) -> int:
    selection = desk_output.get("selection") or {}
    if selection.get("source") == "market_scan":
        return int(selection.get("candidate_count") or 0)
    return int(desk_output.get("ticker_count") or 0)


def _grade_rank(grade: str) -> int:
    return {"A_WATCH": 3, "B_WATCH": 2, "C_WATCH": 1}.get(grade, 0)


def _journal_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": candidate["ticker"],
            "grade": candidate["grade"],
            "consensus": candidate["consensus_score"],
            "scanners": list(candidate["scanners_triggered"]),
            "bucket": candidate["bucket"],
        }
        for candidate in candidates
    ]
