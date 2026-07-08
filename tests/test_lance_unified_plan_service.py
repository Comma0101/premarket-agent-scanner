from services.lance_unified_plan_service import LanceUnifiedPlanService


def _swing_plan(
    ticker: str = "IBM",
    *,
    state: str = "active_watch",
    grade: str = "ACTIVE_DAILY_WATCH",
) -> dict:
    return {
        "ticker": ticker,
        "state": state,
        "lance_quality_grade": grade,
        "playbook": "relative_strength_continuation",
        "score": 90,
        "state_reason": "Daily trend and relative strength are aligned.",
        "waiting_for": ["daily close confirmation above prior-day high"],
        "invalidates_if": ["daily close loses prior-day low"],
        "data_quality": {"confidence": "OK", "gap_basis": "last_trade"},
        "daily_context": {"trend": "uptrend", "structure": "constructive_near_highs"},
        "relative_strength": {"classification": "strong"},
    }


def _intraday_plan(
    ticker: str = "IBM",
    *,
    state: str = "waiting_for_turn",
    grade: str = "B_WATCH",
) -> dict:
    return {
        "ticker": ticker,
        "state": state,
        "lance_quality_grade": grade,
        "setup_name": "mean_reversion_after_capitulation",
        "state_reason": "Directional pressure exists, but Lance is still waiting for the turn.",
        "waiting_for": ["prior 2-minute bar high break"],
        "invalidates_if": ["prior 2-minute low/high reference fails"],
        "data_quality": {"confidence": "OK", "gap_basis": "last_trade"},
        "trigger_reference": {"direction": "long", "price": 201.0},
        "risk_reference": {"price": 195.0},
    }


class FakeSwingService:
    def __init__(self, plans: dict[str, dict]) -> None:
        self.plans = plans
        self.calls: list[dict] = []

    def build_plan(
        self,
        ticker: str,
        *,
        lookback_days: int = 60,
        data_quality_override: dict | None = None,
    ) -> dict:
        self.calls.append({
            "ticker": ticker,
            "lookback_days": lookback_days,
            "data_quality_override": data_quality_override,
        })
        return self.plans[ticker]


class FakeIntradayService:
    def __init__(self, plans: dict[str, dict]) -> None:
        self.plans = plans
        self.calls: list[str] = []

    def build_plan(self, ticker: str) -> dict:
        self.calls.append(ticker)
        return self.plans[ticker]


class FakeMemoryService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def summarize(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "status": "OK",
            "outcome_count": 3,
            "by_action_mode": [
                {
                    "action_mode": "watch",
                    "total": 2,
                    "outcomes": {
                        "worked": 1,
                        "failed": 1,
                        "chop": 0,
                        "reversed": 0,
                        "unknown": 0,
                    },
                    "worked_rate": 0.5,
                }
            ],
            "by_alignment": [
                {
                    "alignment": "aligned",
                    "total": 2,
                    "outcomes": {
                        "worked": 1,
                        "failed": 1,
                        "chop": 0,
                        "reversed": 0,
                        "unknown": 0,
                    },
                    "worked_rate": 0.5,
                }
            ],
            "recent_outcomes": [{"ticker": "IBM", "outcome": "worked"}],
        }


def test_unified_plan_aligns_swing_active_with_intraday_waiting_for_turn():
    service = LanceUnifiedPlanService(
        swing_service=FakeSwingService({"IBM": _swing_plan()}),
        intraday_service=FakeIntradayService({"IBM": _intraday_plan()}),
    )

    output = service.build(tickers=["IBM"], lookback_days=45)

    plan = output["plans"][0]
    assert output["agent_name"] == "lance_unified"
    assert output["groups"]["watch"][0]["ticker"] == "IBM"
    assert plan["ticker"] == "IBM"
    assert plan["action_mode"] == "watch"
    assert plan["alignment"] == "aligned"
    assert plan["primary_timeframe"] == "daily_then_intraday"
    assert plan["swing"]["state"] == "active_watch"
    assert plan["intraday"]["state"] == "waiting_for_turn"
    assert "Daily idea is valid; intraday timing is still forming." in plan["thesis"]
    assert "daily close confirmation" in " ".join(plan["waiting_for"])
    assert "prior 2-minute bar high break" in " ".join(plan["waiting_for"])
    assert plan["disclaimer"].startswith("Unified Lance plans are not")


def test_unified_plan_uses_intraday_plan_override_without_calling_intraday_service():
    intraday = FakeIntradayService({})
    service = LanceUnifiedPlanService(
        swing_service=FakeSwingService({"IBM": _swing_plan()}),
        intraday_service=intraday,
    )

    output = service.build(
        tickers=["IBM"],
        intraday_plans={"IBM": _intraday_plan(state="setup_forming", grade="B_WATCH")},
    )

    plan = output["plans"][0]
    assert intraday.calls == []
    assert plan["intraday"]["state"] == "setup_forming"
    assert plan["action_mode"] == "watch"


def test_unified_plan_passes_intraday_data_quality_to_swing_layer():
    intraday_plan = _intraday_plan(state="setup_forming", grade="B_WATCH")
    swing = FakeSwingService({"IBM": _swing_plan()})
    service = LanceUnifiedPlanService(
        swing_service=swing,
        intraday_service=FakeIntradayService({}),
    )

    service.build(tickers=["IBM"], intraday_plans={"IBM": intraday_plan})

    assert swing.calls == [{
        "ticker": "IBM",
        "lookback_days": 60,
        "data_quality_override": intraday_plan["data_quality"],
    }]


def test_unified_plan_attaches_matching_outcome_memory_when_available():
    memory = FakeMemoryService()
    service = LanceUnifiedPlanService(
        swing_service=FakeSwingService({"IBM": _swing_plan()}),
        intraday_service=FakeIntradayService({"IBM": _intraday_plan()}),
        memory_service=memory,
    )

    output = service.build(tickers=["IBM"])

    plan = output["plans"][0]
    assert memory.calls == [{"ticker": "IBM", "limit": 100}]
    assert plan["outcome_memory"]["status"] == "OK"
    assert plan["outcome_memory"]["outcome_count"] == 3
    assert plan["outcome_memory"]["matching_action_mode"]["action_mode"] == "watch"
    assert plan["outcome_memory"]["matching_alignment"]["alignment"] == "aligned"
    assert plan["outcome_memory"]["recent_outcomes"][0]["outcome"] == "worked"
    assert "Journaled outcomes only" in plan["outcome_memory"]["note"]


def test_unified_plan_reviews_conflict_between_active_swing_and_invalidated_intraday():
    service = LanceUnifiedPlanService(
        swing_service=FakeSwingService({"IBM": _swing_plan()}),
        intraday_service=FakeIntradayService({
            "IBM": _intraday_plan(state="invalidated", grade="REJECT")
        }),
    )

    output = service.build(tickers="IBM")

    plan = output["plans"][0]
    assert plan["action_mode"] == "review"
    assert plan["alignment"] == "conflict"
    assert "intraday_invalidated_daily_active" in plan["conflict_flags"]
    assert output["groups"]["review"][0]["ticker"] == "IBM"


def test_unified_plan_blocks_when_either_layer_blocks_data_quality():
    service = LanceUnifiedPlanService(
        swing_service=FakeSwingService({
            "IBM": _swing_plan(state="blocked_data_quality", grade="REJECT")
        }),
        intraday_service=FakeIntradayService({"IBM": _intraday_plan()}),
    )

    output = service.build(tickers=["IBM"])

    plan = output["plans"][0]
    assert plan["action_mode"] == "blocked"
    assert plan["alignment"] == "blocked"
    assert "data quality" in plan["thesis"].lower()
    assert output["groups"]["blocked"][0]["ticker"] == "IBM"


def test_unified_plan_ignores_invalid_daily_without_intraday_trigger():
    service = LanceUnifiedPlanService(
        swing_service=FakeSwingService({"IBM": _swing_plan(state="invalidated", grade="REJECT")}),
        intraday_service=FakeIntradayService({
            "IBM": _intraday_plan(state="not_in_play", grade="C_CONTEXT")
        }),
    )

    output = service.build(tickers=["IBM"])

    plan = output["plans"][0]
    assert plan["action_mode"] == "ignore"
    assert plan["alignment"] == "not_aligned"
    assert output["groups"]["ignore"][0]["ticker"] == "IBM"
