from app.models import CombinedSnapshot, HaltStatus
from services.lance_intraday_plan_service import LanceIntradayPlanService
from tests.test_intraday_analysis import _make_series


def _snapshot(
    *,
    ticker: str = "TEST",
    confidence: str = "OK",
    latest_price: float | None = 109,
    previous_close: float | None = 100,
    volume: float | None = 4_000_000,
    average_volume: float | None = 1_000_000,
    halt_status: HaltStatus | None = None,
) -> CombinedSnapshot:
    return CombinedSnapshot(
        ticker=ticker,
        timestamp="2026-07-01T15:30:00Z",
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
        halt_status=halt_status,
    )


class FakeSnapshotService:
    def __init__(self, snapshot: CombinedSnapshot) -> None:
        self.snapshot = snapshot

    def build_snapshot(self, ticker: str) -> CombinedSnapshot:
        assert ticker == self.snapshot.ticker
        return self.snapshot


class FakeIntradayService:
    def __init__(self, series) -> None:
        from services.intraday_analysis_service import IntradayAnalysisService

        self.series = series
        self.real = IntradayAnalysisService()

    def fetch_bars(self, ticker: str, timeframe: str = "2Min", start: str = "", end: str = "", limit: int = 100):
        assert ticker == self.series.ticker
        return self.series

    def compute_vwap(self, series):
        return self.real.compute_vwap(series)

    def detect_entry_signal(self, series, vwap):
        return self.real.detect_entry_signal(series, vwap)

    def compute_prior_bar_levels(self, series):
        return self.real.compute_prior_bar_levels(series)

    def check_volume_2x(self, series):
        return self.real.check_volume_2x(series)

    def compute_consecutive_bars(self, series):
        return self.real.compute_consecutive_bars(series)

    def compute_rate_of_change(self, series):
        return self.real.compute_rate_of_change(series)

    def compute_bollinger_width(self, series):
        return self.real.compute_bollinger_width(series)

    def compute_20_period_ma(self, series):
        return self.real.compute_20_period_ma(series)

    def detect_chop(self, series):
        return self.real.detect_chop(series)


def test_lance_plan_returns_triggered_reference_for_confirmed_long_signal():
    series = _make_series(
        "TEST",
        [
            (110, 111, 109, 110, 1000),
            (109, 110, 108, 109, 1000),
            (108, 109, 107, 108, 1000),
            (107, 108, 106, 107, 1000),
            (108, 110, 107, 109, 2000),
        ],
    )
    service = LanceIntradayPlanService(
        snapshot_service=FakeSnapshotService(_snapshot()),
        intraday_service=FakeIntradayService(series),
    )

    plan = service.build_plan("TEST")

    assert plan["state"] == "triggered_reference"
    assert plan["setup_name"] == "mean_reversion_after_capitulation"
    assert plan["trigger_reference"] == {
        "direction": "long",
        "price": 109,
        "source": "prior_2min_bar_high_break",
        "timestamp": "2026-06-29T14:04:00Z",
    }
    assert plan["risk_reference"] == {
        "price": 106,
        "source": "prior_2min_bar_low",
    }
    assert plan["conditions"]["data_quality"]["status"] == "PASS"
    assert plan["conditions"]["participation"]["status"] == "PASS"
    assert plan["conditions"]["prior_bar_break"]["status"] == "PASS"
    assert plan["data_quality"]["confidence"] == "OK"
    assert plan["data_quality"]["gap_basis"] == "last_trade"
    assert plan["data_quality"]["rel_volume_basis"] == "session_volume_vs_average_daily_volume"
    assert plan["front_side_status"] == "right_side_confirmed"
    assert plan["lance_quality_grade"] == "A_WATCH"
    assert plan["state_reason"] == "Right-side prior 2-minute bar break is confirmed."
    assert plan["waiting_for"] == []
    assert "prior 2-minute low/high reference fails" in plan["invalidates_if"]
    assert plan["decision_sequence"][0]["step"] == "data_gate"
    assert plan["decision_sequence"][0]["status"] == "PASS"
    assert plan["decision_sequence"][-1]["step"] == "right_side_gate"
    assert plan["decision_sequence"][-1]["status"] == "PASS"
    assert "Did the prior-bar reference produce follow-through" in plan["manual_review_questions"][0]
    assert plan["disclaimer"].startswith("Reference levels are not")


def test_lance_plan_marks_low_rvol_name_not_in_play():
    series = _make_series(
        "TEST",
        [
            (100, 101, 99, 100, 1000),
            (100, 101, 99, 100, 1000),
            (100, 101, 99, 100, 1000),
            (100, 101, 99, 100, 1000),
        ],
    )
    service = LanceIntradayPlanService(
        snapshot_service=FakeSnapshotService(
            _snapshot(latest_price=101, previous_close=100, volume=100_000, average_volume=1_000_000)
        ),
        intraday_service=FakeIntradayService(series),
    )

    plan = service.build_plan("TEST")

    assert plan["state"] == "not_in_play"
    assert plan["front_side_status"] == "not_in_play"
    assert plan["lance_quality_grade"] == "C_CONTEXT"
    assert "RVOL participation is below Lance's floor." in plan["waiting_for"]
    assert plan["conditions"]["participation"]["status"] == "FAIL"
    assert "rel_volume" not in plan["missing_fields"]
    assert plan["next_step"] == "No Lance intraday plan until abnormal move and RVOL participation improve."


def test_lance_plan_marks_setup_forming_before_prior_bar_break():
    series = _make_series(
        "TEST",
        [
            (110, 111, 109, 110, 1000),
            (109, 110, 108, 109, 1000),
            (108, 109, 107, 108, 1000),
            (107, 108, 106, 107, 1000),
            (107, 107.5, 106.5, 107.2, 2100),
        ],
    )
    service = LanceIntradayPlanService(
        snapshot_service=FakeSnapshotService(_snapshot()),
        intraday_service=FakeIntradayService(series),
    )

    plan = service.build_plan("TEST")

    assert plan["state"] == "waiting_for_turn"
    assert plan["front_side_status"] == "front_side_active"
    assert plan["lance_quality_grade"] == "B_WATCH"
    assert plan["state_reason"] == "Directional pressure exists, but Lance is still waiting for the turn."
    assert "prior 2-minute bar high break" in plan["waiting_for"]
    assert plan["trigger_reference"] == {
        "direction": "long",
        "price": 108,
        "source": "waiting_for_prior_2min_bar_high_break",
        "timestamp": "2026-06-29T14:04:00Z",
    }
    assert plan["conditions"]["prior_bar_break"]["status"] == "WAITING"
    assert plan["conditions"]["volume_2x"]["status"] == "PASS"


def test_lance_plan_blocks_low_confidence_snapshot():
    service = LanceIntradayPlanService(
        snapshot_service=FakeSnapshotService(_snapshot(confidence="LOW_CONFIDENCE")),
        intraday_service=FakeIntradayService(_make_series("TEST", [])),
    )

    plan = service.build_plan("TEST")

    assert plan["state"] == "blocked_data_quality"
    assert plan["lance_quality_grade"] == "REJECT"
    assert plan["front_side_status"] == "blocked"
    assert "Data quality must return to OK with clear gap basis." in plan["waiting_for"]
    assert plan["conditions"]["data_quality"]["status"] == "BLOCKED"
    assert plan["missing_fields"] == ["intraday_bars"]


def test_lance_plan_blocks_halted_snapshot():
    service = LanceIntradayPlanService(
        snapshot_service=FakeSnapshotService(
            _snapshot(
                ticker="ABCD",
                halt_status=HaltStatus(
                    ticker="ABCD",
                    status="HALTED",
                    reason_code="LUDP",
                    halt_time="07/01/2026 09:35:12",
                ),
            )
        ),
        intraday_service=FakeIntradayService(_make_series("ABCD", [])),
    )

    plan = service.build_plan("ABCD")

    assert plan["state"] == "blocked_data_quality"
    assert plan["lance_quality_grade"] == "REJECT"
    assert plan["front_side_status"] == "blocked"
    assert plan["data_quality"]["halt_status"]["status"] == "HALTED"
    assert plan["conditions"]["data_quality"]["detail"] == "halt_status=HALTED."
    assert "Active halt must resolve." in plan["waiting_for"]
