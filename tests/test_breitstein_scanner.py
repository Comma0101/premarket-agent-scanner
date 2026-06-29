from importlib.util import find_spec

from app.models import (
    BreitsteinCandidate,
    BreitsteinScanOutput,
    CatalystEvent,
    ScannerResult,
    ScanRunOutput,
    SmallCapEvidence,
)
from services.scanner_preset_service import PresetService


def test_breitstein_models_are_available() -> None:
    import app.models as models

    assert hasattr(models, "BreitsteinCandidate")
    assert hasattr(models, "BreitsteinScanOutput")


def test_load_breitstein_mean_reversion_preset() -> None:
    preset = PresetService().get_preset("breitstein_mean_reversion_v0")

    assert preset.name == "breitstein_mean_reversion_v0"
    assert preset.cap_tiers == ["small", "mid", "large", "mega"]
    assert preset.direction == "both"
    assert preset.min_gap_abs == 3.0
    assert preset.min_volume == 500_000
    assert preset.min_rel_volume == 3.0
    assert preset.include_low_confidence is False
    assert "intraday_bars" in preset.missing_fields
    assert "vwap" in preset.missing_fields


def test_breitstein_scanner_service_module_exists() -> None:
    assert find_spec("services.breitstein_scanner_service") is not None


def _result(
    *,
    ticker: str = "FLUSH",
    market_cap: float | None = 50_000_000_000,
    gap_pct: float | None = -6.0,
    gap_dollar: float | None = -3.0,
    volume: float | None = 5_000_000,
    rel_volume: float | None = 5.0,
    confidence: str = "OK",
    gap_basis: str | None = "premarket",
) -> ScannerResult:
    return ScannerResult(
        ticker=ticker,
        name=f"{ticker} Inc.",
        universe="WATCHLIST:HOT_ACTIVE",
        market_cap=market_cap,
        previous_close=50.0,
        premarket_price=47.0,
        latest_price=47.0,
        gap_pct=gap_pct,
        gap_dollar=gap_dollar,
        volume=volume,
        rel_volume=rel_volume,
        confidence=confidence,  # type: ignore[arg-type]
        gap_basis=gap_basis,
        notes=None,
        sources=["fake"],
        timestamp="2026-06-29T13:30:00Z",
    )


def test_grade_breitstein_candidate_allows_gap_down_a_watch_with_clean_premarket_data() -> None:
    from services.breitstein_scanner_service import grade_breitstein_candidate

    candidate = grade_breitstein_candidate(
        _result(),
        missing_fields=["intraday_bars", "vwap"],
        has_catalyst=True,
    )

    assert candidate.grade == "A_WATCH"
    assert candidate.score >= 75
    assert candidate.cap_tier == "large"
    assert candidate.abnormal_move is True
    assert candidate.has_catalyst is True
    assert "gap_down_flush" in candidate.matched_signals
    assert "premarket_gap_basis" in candidate.matched_signals
    assert candidate.gap_basis == "premarket"
    assert candidate.confidence == "OK"


def test_grade_breitstein_candidate_caps_last_trade_gap_basis_below_a_watch() -> None:
    from services.breitstein_scanner_service import grade_breitstein_candidate

    candidate = grade_breitstein_candidate(
        _result(gap_basis="last_trade"),
        missing_fields=["intraday_bars", "vwap"],
        has_catalyst=True,
    )

    assert candidate.grade in {"B_WATCH", "C_WATCH", "REJECT"}
    assert candidate.grade != "A_WATCH"
    assert "last_trade_gap_basis" in candidate.matched_signals
    assert any("last_trade" in note for note in candidate.risk_notes)


def test_breitstein_scanner_defaults_to_hot_active_and_applies_evidence() -> None:
    from services.breitstein_scanner_service import BreitsteinScannerService

    class FakeScanner:
        def __init__(self) -> None:
            self.calls = []

        def scan(self, **kwargs):
            self.calls.append(kwargs)
            return ScanRunOutput(
                run_id="run-1",
                universe="WATCHLIST:HOT_ACTIVE",
                started_at="2026-06-29T13:30:00Z",
                completed_at="2026-06-29T13:31:00Z",
                status="OK",
                results=[_result()],
                notes=["raw-note"],
            )

    class FakeEvidenceService:
        def enrich_candidates(self, candidates):
            candidates[0].evidence = SmallCapEvidence(
                ticker="FLUSH",
                catalysts=[
                    CatalystEvent(
                        ticker="FLUSH",
                        headline="Flush announces temporary operational issue",
                        published_at="2026-06-29T13:00:00Z",
                        source="fake-wire",
                        catalyst_quality="hard",
                        recency_minutes=30.0,
                        confidence="OK",
                    )
                ],
                missing_fields=["intraday_bars", "vwap"],
                sources=["fake-wire"],
            )
            candidates[0].missing_fields = list(candidates[0].evidence.missing_fields)
            return candidates

    fake_scanner = FakeScanner()
    output = BreitsteinScannerService(
        scanner_service=fake_scanner,
        evidence_service=FakeEvidenceService(),
    ).scan()

    assert fake_scanner.calls[0]["watchlist"] == "HOT_ACTIVE"
    assert fake_scanner.calls[0]["filters"].min_market_cap == 300_000_000
    assert fake_scanner.calls[0]["filters"].max_market_cap is None
    assert fake_scanner.calls[0]["filters"].direction == "both"
    assert fake_scanner.calls[0]["filters"].min_gap_abs == 3.0
    assert fake_scanner.calls[0]["filters"].min_volume == 500_000
    assert fake_scanner.calls[0]["filters"].min_rel_volume == 3.0
    assert fake_scanner.calls[0]["filters"].include_low_confidence is False

    assert output.preset == "breitstein_mean_reversion_v0"
    assert output.run_ids == ["run-1"]
    assert output.phase == "1"
    assert output.candidate_count == 1
    assert output.candidates[0].ticker == "FLUSH"
    assert output.candidates[0].has_catalyst is True
    assert "fresh_catalyst_context" in output.candidates[0].matched_signals
    assert output.candidates[0].evidence is not None


def test_scan_breitstein_tool_returns_candidates() -> None:
    from agent_tools import tools

    class FakeBreitsteinService:
        def scan(self, **kwargs):
            assert kwargs["watchlist"] == "HOT_ACTIVE"
            assert kwargs["max_workers"] == 4
            return BreitsteinScanOutput(
                preset=kwargs["preset_name"],
                run_ids=["run-1"],
                candidate_count=1,
                candidates=[
                    BreitsteinCandidate(
                        ticker="FLUSH",
                        name="FLUSH Inc.",
                        market_cap=50_000_000_000,
                        gap_pct=-6.0,
                        gap_dollar=-3.0,
                        volume=5_000_000,
                        rel_volume=5.0,
                        confidence="OK",
                        gap_basis="premarket",
                        cap_tier="large",
                        abnormal_move=True,
                        consecutive_days_direction=None,
                        has_catalyst=True,
                        score=100,
                        grade="A_WATCH",
                        matched_signals=["gap_down_flush"],
                        missing_fields=["intraday_bars", "vwap"],
                        risk_notes=[],
                        sources=["fake"],
                        evidence=SmallCapEvidence(
                            ticker="FLUSH",
                            catalysts=[
                                CatalystEvent(
                                    ticker="FLUSH",
                                    headline="Temporary issue",
                                    published_at="2026-06-29T13:00:00Z",
                                    source="fake-wire",
                                    confidence="OK",
                                )
                            ],
                            missing_fields=["intraday_bars", "vwap"],
                        ),
                        timestamp="2026-06-29T13:30:00Z",
                    )
                ],
                notes=["phase 1 only"],
            )

    out = tools.scan_breitstein(
        watchlist="HOT_ACTIVE",
        max_workers=4,
        service=FakeBreitsteinService(),
    )

    assert out["candidate_count"] == 1
    assert out["phase"] == "1"
    assert out["candidates"][0]["ticker"] == "FLUSH"
    assert out["candidates"][0]["grade"] == "A_WATCH"
    assert out["candidates"][0]["gap_basis"] == "premarket"
    assert out["candidates"][0]["confidence"] == "OK"
    assert out["candidates"][0]["has_catalyst"] is True
    assert out["candidates"][0]["evidence"]["catalysts"][0]["source"] == "fake-wire"
