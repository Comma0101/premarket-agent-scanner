from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import re
import time
from typing import Callable
from xml.etree import ElementTree

from app.models import HaltStatus, utc_now_iso


TRADE_HALTS_RSS_URL = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
NDAQ_NS = "{http://www.nasdaqtrader.com/}"


class NasdaqHaltProvider:
    source_name = "nasdaq_trader_halts"

    def __init__(
        self,
        *,
        feed_url: str = TRADE_HALTS_RSS_URL,
        cache_ttl_seconds: int = 60,
        fetcher: Callable[[], str] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.feed_url = feed_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self.fetcher = fetcher or self._fetch
        self.now_provider = now_provider
        self._cache_loaded_at: float | None = None
        self._cache_statuses: dict[str, HaltStatus] = {}
        self._cache_fetched_at: str | None = None
        self._cache_error: str | None = None

    def get_halt_status(self, ticker: str) -> HaltStatus:
        normalized = ticker.upper()
        statuses, fetched_at, error = self._load_statuses()
        if error:
            return HaltStatus(
                ticker=normalized,
                status="UNKNOWN",
                is_active=False,
                source=self.source_name,
                fetched_at=fetched_at,
                error=error,
            )
        return statuses.get(
            normalized,
            HaltStatus(
                ticker=normalized,
                status="UNKNOWN",
                is_active=False,
                source=self.source_name,
                fetched_at=fetched_at,
            ),
        )

    def _load_statuses(self) -> tuple[dict[str, HaltStatus], str, str | None]:
        now_monotonic = time.monotonic()
        if (
            self._cache_loaded_at is not None
            and now_monotonic - self._cache_loaded_at < self.cache_ttl_seconds
        ):
            return self._cache_statuses, self._cache_fetched_at or utc_now_iso(), self._cache_error

        fetched_at = _to_utc_iso(self._now())
        try:
            feed_text = self.fetcher()
            statuses = self._parse(feed_text, fetched_at=fetched_at)
            error = None
        except Exception as exc:
            statuses = {}
            error = str(exc)

        self._cache_loaded_at = now_monotonic
        self._cache_statuses = statuses
        self._cache_fetched_at = fetched_at
        self._cache_error = error
        return statuses, fetched_at, error

    def _fetch(self) -> str:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("requests package is not installed.") from exc

        response = requests.get(self.feed_url, timeout=15)
        response.raise_for_status()
        return response.content.decode("utf-8-sig", errors="replace")

    def _parse(self, feed_text: str, *, fetched_at: str) -> dict[str, HaltStatus]:
        root = ElementTree.fromstring(feed_text.lstrip("\ufeffï»¿\r\n\t "))
        statuses: dict[str, HaltStatus] = {}
        for item in root.findall(".//item"):
            title = _node_text(item, "title")
            labels = _labels_from_description(_node_text(item, "description"))
            ticker = (
                _node_text(item, f"{NDAQ_NS}IssueSymbol")
                or labels.get("issue symbol")
                or labels.get("symbol")
                or _ticker_from_title(title)
            )
            if not ticker:
                continue

            normalized = ticker.upper()
            reason_code = _node_text(item, f"{NDAQ_NS}ReasonCode") or labels.get("reason code")
            halt_time = _et_datetime_to_utc_iso(
                _node_text(item, f"{NDAQ_NS}HaltDate") or labels.get("halt date"),
                _node_text(item, f"{NDAQ_NS}HaltTime") or labels.get("halt time"),
            )
            resume_time = _et_datetime_to_utc_iso(
                _node_text(item, f"{NDAQ_NS}ResumptionDate") or labels.get("resume date"),
                (
                    _node_text(item, f"{NDAQ_NS}ResumptionTradeTime")
                    or _node_text(item, f"{NDAQ_NS}ResumptionQuoteTime")
                    or labels.get("resume time")
                ),
            )
            is_active = _is_active(resume_time, self._now())
            statuses[normalized] = HaltStatus(
                ticker=normalized,
                status=_status_for(reason_code, is_active=is_active),
                is_active=is_active,
                reason_code=reason_code,
                reason=labels.get("reason"),
                halt_time=halt_time,
                resume_time=resume_time,
                source=self.source_name,
                fetched_at=fetched_at,
            )
        return statuses

    def _now(self) -> datetime:
        now = self.now_provider() if self.now_provider else datetime.now(timezone.utc)
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)


def _node_text(item: ElementTree.Element, tag: str) -> str:
    child = item.find(tag)
    return "" if child is None or child.text is None else child.text.strip()


def _labels_from_description(description: str) -> dict[str, str]:
    text = re.sub(r"<br\s*/?>", "\n", description, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    labels: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        labels[key.strip().lower()] = value.strip()
    return labels


def _ticker_from_title(title: str) -> str | None:
    match = re.search(r"\b([A-Z][A-Z0-9.\-]{0,9})\b\s*$", title.strip())
    return match.group(1) if match else None


def _et_datetime_to_utc_iso(date_text: str | None, time_text: str | None) -> str | None:
    if not date_text or not time_text:
        return None
    try:
        time_clean = time_text.strip().split(".", 1)[0]
        parsed = datetime.strptime(
            f"{date_text.strip()} {time_clean}",
            "%m/%d/%Y %H:%M:%S",
        )
    except ValueError:
        return None

    from zoneinfo import ZoneInfo

    return _to_utc_iso(parsed.replace(tzinfo=ZoneInfo("America/New_York")))


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _is_active(resume_time: str | None, now: datetime) -> bool:
    if resume_time is None:
        return True
    try:
        resume = datetime.fromisoformat(resume_time)
    except ValueError:
        return True
    return resume > now.astimezone(timezone.utc)


def _status_for(reason_code: str | None, *, is_active: bool) -> str:
    if not is_active:
        return "RESUMED"
    code = (reason_code or "").upper()
    if code.startswith("LUD") or code in {"T5", "M", "M1", "M2"}:
        return "HALTED_LULD"
    if code.startswith("T") or code.startswith("H"):
        return "HALTED_REGULATORY"
    return "HALTED"
