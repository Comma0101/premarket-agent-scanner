from app.models import CombinedSnapshot, IntradayBar, IntradayBarSeries
from services.lance_swing_plan_service import LanceSwingPlanService


def _snapshot(
    *,
    ticker: str = "TEST",
    confidence: str = "OK",
    latest_price: float | None = 120.0,
    previous_close: float | None = 118.0,
    volume: float | None = 5_000_000,
    average_volume: float | None = 2_000_000,
) -> CombinedSnapshot:
    return CombinedSnapshot(
        ticker=ticker,
        timestamp="2026-07-01T20:00:00Z",
        previous_close=previous_close,
        premarket_price=None,
        latest_price=latest_price,
        open_price=None,
        high=None,
        low=None,
        volume=volume,
        source_primary="fake_snapshot",
        source_secondary=None,
        confidence=confidence,  # type: ignore[arg-type]
        sources=["fake_snapshot"],
        market_cap=50_000_000_000,
        average_volume=average_volume,
    )


def _daily_series(
    ticker: str,
    closes: list[float],
    *,
    source: str = "fake_daily",
) -> IntradayBarSeries:
    bars = []
    for index, close in enumerate(closes, start=1):
        bars.append(
            IntradayBar(
                ticker=ticker,
                timestamp=f"2026-06-{index:02d}T20:00:00Z",
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000_000 + index,
                timeframe="1Day",
            )
        )
    return IntradayBarSeries(
        ticker=ticker,
        timeframe="1Day",
        bars=bars,
        source=source,
        fetched_at="2026-07-01T20:05:00Z",
    )


class FakeSnapshotService:
    def __init__(self, snapshots: dict[str, CombinedSnapshot]) -> None:
        self.snapshots = snapshots
        self.calls: list[str] = []

    def build_snapshot(self, ticker: str) -> CombinedSnapshot:
        self.calls.append(ticker)
        return self.snapshots[ticker]


class FakeBarProvider:
    source_name = "fake_daily"

    def __init__(self, series_by_ticker: dict[str, IntradayBarSeries]) -> None:
        self.series_by_ticker = series_by_ticker
        self.calls: list[tuple[str, str, int]] = []

    def get_bars(
        self,
        ticker: str,
        timeframe: str,
        start: str,
        end: str,
        limit: int = 100,
    ) -> IntradayBarSeries:
        self.calls.append((ticker, timeframe, limit))
        return self.series_by_ticker[ticker]


def test_lance_swing_plan_flags_relative_strength_continuation():
    ticker_series = _daily_series(
        "TEST",
        [
            100,
            101,
            102,
            103,
            104,
            105,
            106,
            107,
            108,
            109,
            110,
            111,
            112,
            113,
            114,
            115,
            116,
            117,
            118,
            120,
        ],
    )
    provider = FakeBarProvider({
        "TEST": ticker_series,
        "QQQ": _daily_series("QQQ", [100 + index * 0.2 for index in range(20)]),
        "SPY": _daily_series("SPY", [100 + index * 0.1 for index in range(20)]),
    })
    service = LanceSwingPlanService(
        snapshot_service=FakeSnapshotService({"TEST": _snapshot()}),
        daily_bar_provider=provider,
    )

    output = service.build(tickers=["TEST"])

    plan = output["plans"][0]
    assert output["agent_name"] == "lance_swing"
    assert output["groups"]["active_watch"][0]["ticker"] == "TEST"
    assert plan["state"] == "active_watch"
    assert plan["lance_quality_grade"] == "ACTIVE_DAILY_WATCH"
    assert plan["playbook"] == "relative_strength_continuation"
    assert plan["bias"] == "long_bias"
    assert "relative strength continuation" in plan["bias_reason"]
    assert plan["daily_context"]["trend"] == "uptrend"
    assert plan["relative_strength"]["classification"] == "strong"
    assert plan["data_quality"]["rel_volume_basis"] == "session_volume_vs_average_daily_volume"
    assert plan["daily_context"]["prior_day_levels"]["close"] == 120
    assert "daily close confirmation" in " ".join(plan["waiting_for"])
    assert "daily close loses" in " ".join(plan["invalidates_if"])
    assert plan["disclaimer"].startswith("Swing plans are not")
    assert provider.calls[0] == ("TEST", "1Day", 60)


def test_lance_swing_plan_blocks_when_daily_bars_missing():
    provider = FakeBarProvider({
        "TEST": _daily_series("TEST", []),
        "QQQ": _daily_series("QQQ", []),
        "SPY": _daily_series("SPY", []),
    })
    service = LanceSwingPlanService(
        snapshot_service=FakeSnapshotService({"TEST": _snapshot()}),
        daily_bar_provider=provider,
    )

    output = service.build(tickers=["TEST"])

    plan = output["plans"][0]
    assert plan["state"] == "blocked_data_quality"
    assert plan["lance_quality_grade"] == "REJECT"
    assert "daily_bars" in plan["missing_fields"]
    assert output["groups"]["blocked"][0]["ticker"] == "TEST"


def test_lance_swing_plan_groups_invalidated_weak_name():
    provider = FakeBarProvider({
        "TEST": _daily_series(
            "TEST",
            [
                120,
                119,
                118,
                117,
                116,
                115,
                114,
                113,
                112,
                111,
                110,
                109,
                108,
                107,
                106,
                105,
                104,
                103,
                102,
                100,
            ],
        ),
        "QQQ": _daily_series("QQQ", [100 + index * 0.3 for index in range(20)]),
        "SPY": _daily_series("SPY", [100 + index * 0.2 for index in range(20)]),
    })
    service = LanceSwingPlanService(
        snapshot_service=FakeSnapshotService({"TEST": _snapshot(latest_price=100, previous_close=102)}),
        daily_bar_provider=provider,
    )

    output = service.build(tickers=["TEST"])

    plan = output["plans"][0]
    assert plan["state"] == "invalidated"
    assert plan["bias"] == "neutral"
    assert "No valid Lance swing setup" in plan["bias_reason"]
    assert plan["daily_context"]["trend"] == "downtrend"
    assert plan["relative_strength"]["classification"] == "weak"
    assert output["groups"]["invalidated"][0]["ticker"] == "TEST"


def test_lance_swing_plan_flags_large_pullback_as_mean_reversion_watch():
    provider = FakeBarProvider({
        "TEST": _daily_series(
            "TEST",
            [
                99,
                101,
                103,
                106,
                109,
                112,
                115,
                118,
                121,
                124,
                127,
                130,
                133,
                136,
                139,
                142,
                145,
                148,
                151,
                154,
            ],
        ),
        "QQQ": _daily_series("QQQ", [100 + index * 0.4 for index in range(20)]),
        "SPY": _daily_series("SPY", [100 + index * 0.3 for index in range(20)]),
    })
    service = LanceSwingPlanService(
        snapshot_service=FakeSnapshotService({
            "TEST": _snapshot(latest_price=142.0, previous_close=154.0, volume=5_000_000),
        }),
        daily_bar_provider=provider,
    )

    output = service.build(tickers=["TEST"])

    plan = output["plans"][0]
    assert plan["state"] == "mean_reversion_watch"
    assert plan["lance_quality_grade"] == "REVERSION_WATCH"
    assert plan["playbook"] == "swing_mean_reversion_reclaim"
    assert plan["bias"] == "long_bias"
    assert "reclaim" in plan["bias_reason"]
    assert plan["conditions"]["swing_mean_reversion"]["status"] == "PASS"
    assert "prior-day low reclaim" in " ".join(plan["waiting_for"])
    assert output["groups"]["mean_reversion_watch"][0]["ticker"] == "TEST"


def test_lance_swing_plan_reuses_benchmark_bars_across_tickers():
    provider = FakeBarProvider({
        "TEST": _daily_series("TEST", [100 + index for index in range(20)]),
        "NEXT": _daily_series("NEXT", [105 + index for index in range(20)]),
        "QQQ": _daily_series("QQQ", [100 + index * 0.2 for index in range(20)]),
        "SPY": _daily_series("SPY", [100 + index * 0.1 for index in range(20)]),
    })
    service = LanceSwingPlanService(
        snapshot_service=FakeSnapshotService({
            "TEST": _snapshot(ticker="TEST"),
            "NEXT": _snapshot(ticker="NEXT"),
        }),
        daily_bar_provider=provider,
    )

    output = service.build(tickers=["TEST", "NEXT"])

    assert output["plan_count"] == 2
    assert provider.calls.count(("QQQ", "1Day", 60)) == 1
    assert provider.calls.count(("SPY", "1Day", 60)) == 1


def test_lance_swing_plan_uses_data_quality_override_without_refetching_snapshot():
    provider = FakeBarProvider({
        "TEST": _daily_series("TEST", [100 + index for index in range(20)]),
        "QQQ": _daily_series("QQQ", [100 + index * 0.2 for index in range(20)]),
        "SPY": _daily_series("SPY", [100 + index * 0.1 for index in range(20)]),
    })
    snapshot_service = FakeSnapshotService({"TEST": _snapshot()})
    override = {
        "confidence": "OK",
        "data_status": "live",
        "provider_failures": {},
        "halt_status": None,
        "gap_basis": "last_trade",
        "as_of": "2026-07-01T14:00:00Z",
        "as_of_et": "Jul 1 10:00 AM ET",
        "session_mode": "MARKET_OPEN",
        "data_caveat": "MARKET_OPEN: last_trade regular-session quote.",
        "latest_price": 121.0,
        "previous_close": 118.0,
        "gap_pct": 2.54,
        "gap_dollar": 3.0,
        "volume": 7_000_000,
        "rel_volume": 3.5,
        "market_cap": 50_000_000_000,
        "sources": ["scan_snapshot"],
    }
    service = LanceSwingPlanService(
        snapshot_service=snapshot_service,
        daily_bar_provider=provider,
    )

    plan = service.build_plan("TEST", data_quality_override=override)

    assert snapshot_service.calls == []
    assert plan["data_quality"] == override
