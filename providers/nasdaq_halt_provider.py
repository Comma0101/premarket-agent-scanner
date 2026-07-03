from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from typing import Callable

from app.models import HaltStatus


HALTS_RSS_URL = "https://www.nasdaqtrader.com/RSS.aspx?Feed=tradehalts"


class NasdaqHaltProvider:
    """Read the official NASDAQ Trader halt RSS feed."""

    source_name = "nasdaq_trader_halts"

    def __init__(
        self,
        *,
        fetcher: Callable[[], str] | None = None,
        url: str = HALTS_RSS_URL,
    ) -> None:
        self.fetcher = fetcher
        self.url = url
        self._cached_feed: str | None = None

    def get_halt_status(self, ticker: str) -> HaltStatus:
        normalized = ticker.strip().upper()
        if not normalized:
            return HaltStatus(
                ticker=normalized,
                status="UNKNOWN",
                error="ticker is required",
                notes=["NASDAQ halt feed lookup requires a ticker."],
            )
        try:
            feed = self._feed()
        except Exception as exc:
            return HaltStatus(
                ticker=normalized,
                status="UNKNOWN",
                error=str(exc),
                notes=["NASDAQ halt feed unavailable"],
            )
        try:
            return _status_from_feed(feed, normalized)
        except (ET.ParseError, ValueError) as exc:
            return HaltStatus(
                ticker=normalized,
                status="UNKNOWN",
                source=self.source_name,
                error=str(exc),
                notes=["NASDAQ halt feed parse failed"],
            )

    def _feed(self) -> str:
        if self._cached_feed is None:
            self._cached_feed = self.fetcher() if self.fetcher is not None else self._fetch_url()
        return self._cached_feed

    def _fetch_url(self) -> str:
        request = urllib.request.Request(
            self.url,
            headers={"User-Agent": "premarket-agent-scanner contact@example.com"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - official HTTPS feed
            return response.read().decode("utf-8", errors="replace")


def _status_from_feed(feed: str, ticker: str) -> HaltStatus:
    items = _items(feed)
    for item in items:
        raw_text = "\n".join(
            part for part in [item.get("title"), item.get("description")] if part
        )
        fields = _fields(raw_text)
        symbol = (
            fields.get("symbol")
            or item.get("issuesymbol", "").upper()
            or _symbol_from_title(item.get("title") or "")
        )
        if symbol != ticker:
            continue
        resume_time = (
            fields.get("resumption trade time")
            or item.get("resumptiontradetime")
            or fields.get("resumption quote time")
            or item.get("resumptionquotetime")
        )
        return HaltStatus(
            ticker=ticker,
            status="RESUMED" if resume_time else "HALTED",
            reason_code=fields.get("reason code") or item.get("reasoncode"),
            reason=fields.get("reason"),
            halt_time=_join_date_time(
                fields.get("halt date") or item.get("haltdate"),
                fields.get("halt time") or item.get("halttime"),
            ),
            resume_time=_join_date_time(
                fields.get("resumption date") or item.get("resumptiondate"),
                resume_time,
            ),
            source=NasdaqHaltProvider.source_name,
            raw=item,
        )
    return HaltStatus(
        ticker=ticker,
        status="NOT_HALTED",
        source=NasdaqHaltProvider.source_name,
    )


def _items(feed: str) -> list[dict[str, str]]:
    root = ET.fromstring(feed)
    if _strip_namespace(root.tag).lower() != "rss":
        raise ValueError("NASDAQ halt feed did not return RSS XML.")
    rows = []
    for item in root.findall(".//item"):
        row = {}
        for child in item:
            tag = _strip_namespace(child.tag).lower()
            if child.text:
                row[tag] = _clean(child.text)
        rows.append(row)
    return rows


def _fields(text: str) -> dict[str, str]:
    normalized = _clean(text)
    labels = [
        "Symbol",
        "Name",
        "Market",
        "Reason Code",
        "Reason",
        "Halt Date",
        "Halt Time",
        "Resumption Date",
        "Resumption Quote Time",
        "Resumption Trade Time",
    ]
    pattern = "|".join(re.escape(label) for label in labels)
    matches = list(re.finditer(rf"({pattern})\s*:\s*", normalized, flags=re.IGNORECASE))
    output: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        output[match.group(1).lower()] = normalized[start:end].strip()
    if "symbol" in output:
        output["symbol"] = output["symbol"].upper()
    return output


def _symbol_from_title(title: str) -> str | None:
    match = re.search(r"\b([A-Z]{1,6})\b\s*$", title.strip().upper())
    return match.group(1) if match else None


def _join_date_time(date_value: str | None, time_value: str | None) -> str | None:
    if not time_value:
        return None
    if date_value:
        return f"{date_value} {time_value}"
    return time_value


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
