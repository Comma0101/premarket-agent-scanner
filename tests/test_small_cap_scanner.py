from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.models import (
    CatalystEvent,
    FilingEvent,
    FormerRunnerEvent,
    ScannerResult,
    ScanRunOutput,
    SmallCapCandidate,
    SmallCapEvidence,
)
from cli.scan_small_caps import _format_evidence_float
from services.scanner_preset_service import PresetService
from services.small_cap_scanner_service import (
    SmallCapScannerService,
    grade_small_cap_candidate,
)


def test_scan_small_caps_cli_imports():
    import cli.scan_small_caps as module

    assert module.app is not None


def test_scan_small_caps_cli_formats_evidence_float():
    evidence = SmallCapEvidence(
        ticker="HOT",
        float_shares=8_000_000,
        is_low_float=True,
    )

    assert _format_evidence_float(evidence) == "8.0M low"
    assert _format_evidence_float(None) == "-"


def test_scan_small_caps_cli_uses_evidence_missing_fields_when_available():
    import cli.scan_small_caps as module

    candidate = SmallCapCandidate(
        ticker="HOT",
        name=None,
        market_cap=25_000_000,
        gap_pct=12.0,
        gap_dollar=1.2,
        volume=2_000_000,
        rel_volume=5.0,
        confidence="OK",
        score=90,
        grade="A_WATCH",
        missing_fields=["float", "catalyst"],
        evidence=SmallCapEvidence(ticker="HOT", missing_fields=["catalyst"]),
    )

    assert module._format_candidate_missing_fields(candidate) == "catalyst"

    candidate.evidence = None

    assert module._format_candidate_missing_fields(candidate) == "float, catalyst"


def test_scan_small_caps_cli_formats_compact_evidence_summary():
    import cli.scan_small_caps as module

    evidence = SmallCapEvidence(
        ticker="HOT",
        float_shares=8_000_000,
        is_low_float=True,
        catalysts=[
            CatalystEvent(
                ticker="HOT",
                headline="Deal",
                published_at="2026-06-28T12:00:00Z",
                source="PR",
            )
        ],
        filings=[
            FilingEvent(
                ticker="HOT",
                form_type="S-1",
                filed_at="2026-06-28",
                accession_number="0000000000-26-000001",
                risk_tags=["offering"],
            )
        ],
        former_runner=FormerRunnerEvent(ticker="HOT", event_date="2026-06-01"),
    )

    summary = module._format_evidence_summary(evidence)

    assert len(summary) <= 32
    assert "8.0M" in summary
    assert "cat" in summary
    assert "offering" in summary
    assert "former" in summary or "prev" in summary
    assert module._format_evidence_summary(SmallCapEvidence(ticker="COLD")) == "-"
    assert module._format_evidence_summary(None) == "-"


def test_scan_small_caps_cli_reports_invalid_preset_cleanly():
    import cli.scan_small_caps as module

    result = CliRunner().invoke(
        module.app,
        ["--tickers", "HOT", "--preset", "does_not_exist"],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "does_not_exist" in result.output
    assert "Unknown scanner preset" in result.output


def test_scan_small_caps_cli_reports_unknown_universe_cleanly():
    import cli.scan_small_caps as module

    result = CliRunner().invoke(module.app, ["--universe", "DOES_NOT_EXIST"])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "DOES_NOT_EXIST" in result.output
    assert "Unknown universe" in result.output


def _result(
    *,
    ticker="HOT",
    market_cap=100_000_000,
    gap_pct=12.0,
    gap_dollar=1.2,
    volume=2_000_000,
    rel_volume=5.0,
    confidence="OK",
):
    return ScannerResult(
        ticker=ticker,
        name=None,
        universe=None,
        market_cap=market_cap,
        previous_close=10.0,
        premarket_price=11.2,
        latest_price=11.2,
        gap_pct=gap_pct,
        gap_dollar=gap_dollar,
        volume=volume,
        rel_volume=rel_volume,
        confidence=confidence,
        notes=None,
        sources=["fake"],
        timestamp="2026-06-28T12:00:00Z",
    )


def test_load_sykes_small_cap_preset():
    service = PresetService()
    preset = service.get_preset("sykes_small_cap_v0")

    assert preset.name == "sykes_small_cap_v0"
    assert preset.cap_tiers == ["nano", "micro", "small"]
    assert preset.direction == "up"
    assert preset.min_gap_abs == 5.0
    assert preset.min_rel_volume == 2.0
    assert preset.include_low_confidence is False
    assert "float" in preset.missing_fields
    assert "catalyst" in preset.missing_fields


def test_unknown_preset_lists_valid_names(tmp_path: Path):
    path = tmp_path / "scanner_presets.yaml"
    path.write_text(
        "example:\n"
        "  cap_tiers: [small]\n"
        "  direction: up\n"
        "  min_gap_abs: 5\n",
        encoding="utf-8",
    )
    service = PresetService(path)

    with pytest.raises(KeyError) as exc:
        service.get_preset("missing")

    assert "example" in str(exc.value)


def test_preset_body_must_be_mapping(tmp_path: Path):
    path = tmp_path / "scanner_presets.yaml"
    path.write_text("bad: 1\n", encoding="utf-8")
    service = PresetService(path)

    with pytest.raises(ValueError, match="Preset 'bad'.*mapping"):
        service.get_preset("bad")


def test_cap_tiers_must_be_list(tmp_path: Path):
    path = tmp_path / "scanner_presets.yaml"
    path.write_text(
        "bad:\n"
        "  cap_tiers: small\n",
        encoding="utf-8",
    )
    service = PresetService(path)

    with pytest.raises(ValueError, match="Preset 'bad' field 'cap_tiers'.*list"):
        service.get_preset("bad")


@pytest.mark.parametrize("field", ["missing_fields", "notes"])
def test_string_list_fields_must_be_lists(tmp_path: Path, field: str):
    path = tmp_path / "scanner_presets.yaml"
    path.write_text(
        "bad:\n"
        "  cap_tiers: [small]\n"
        f"  {field}: scalar\n",
        encoding="utf-8",
    )
    service = PresetService(path)

    with pytest.raises(ValueError, match=f"Preset 'bad' field '{field}'.*list"):
        service.get_preset("bad")


def test_small_cap_scanner_attaches_evidence_to_candidates():
    class FakeScanner:
        def scan(self, **kwargs):
            return ScanRunOutput(
                run_id="run-1",
                universe="fake",
                started_at="2026-06-28T12:00:00Z",
                completed_at="2026-06-28T12:01:00Z",
                status="OK",
                results=[_result(ticker="HOT")],
                notes=[],
            )

    class FakeEvidenceService:
        def enrich_candidates(self, candidates):
            candidates[0].evidence = SmallCapEvidence(
                ticker="HOT",
                float_shares=8_000_000,
                missing_fields=["catalyst", "filings"],
            )
            return candidates

    output = SmallCapScannerService(
        scanner_service=FakeScanner(),
        evidence_service=FakeEvidenceService(),
    ).scan(tickers="HOT", preset_name="sykes_small_cap_v0")

    candidate = output.candidates[0]
    assert candidate.evidence is not None
    assert candidate.evidence.float_shares == 8_000_000


def test_grade_strong_small_cap_candidate_is_a_watch():
    candidate = grade_small_cap_candidate(
        _result(),
        missing_fields=["float", "catalyst", "filings"],
    )

    assert candidate.grade == "A_WATCH"
    assert candidate.score >= 80
    assert "strong_gap" in candidate.matched_signals
    assert "high_rvol" in candidate.matched_signals
    assert "float" in candidate.missing_fields
    assert any("unknown" in note.lower() for note in candidate.risk_notes)


def test_strong_high_rvol_candidate_with_thin_volume_is_not_a_watch():
    candidate = grade_small_cap_candidate(
        _result(volume=1_000, rel_volume=8.0),
        missing_fields=["float", "catalyst", "filings"],
    )

    assert candidate.grade in {"B_WATCH", "C_WATCH", "REJECT"}
    assert candidate.grade != "A_WATCH"
    assert "strong_gap" in candidate.matched_signals
    assert "high_rvol" in candidate.matched_signals
    assert "liquid_volume" not in candidate.matched_signals
    assert "minimum_volume" not in candidate.matched_signals
    assert any("volume" in note.lower() for note in candidate.risk_notes)


def test_conflict_candidate_is_rejected():
    candidate = grade_small_cap_candidate(
        _result(confidence="CONFLICT"),
        missing_fields=[],
    )

    assert candidate.grade == "REJECT"
    assert "unusable_confidence" in candidate.matched_signals


def test_small_cap_scanner_runs_each_cap_tier_and_ranks_candidates():
    class FakeScanner:
        def __init__(self):
            self.calls = []

        def scan(self, **kwargs):
            self.calls.append(kwargs)
            run_number = len(self.calls)
            results_by_run = {
                1: [
                    _result(
                        ticker="HOT",
                        market_cap=25_000_000,
                        gap_pct=12.0,
                        volume=2_000_000,
                        rel_volume=5.0,
                    )
                ],
                2: [
                    _result(
                        ticker="OKAY",
                        market_cap=125_000_000,
                        gap_pct=6.0,
                        volume=600_000,
                        rel_volume=2.1,
                    )
                ],
                3: [
                    _result(
                        ticker="HOT",
                        market_cap=500_000_000,
                        gap_pct=5.5,
                        volume=550_000,
                        rel_volume=2.0,
                    )
                ],
            }
            return ScanRunOutput(
                run_id=f"run-{run_number}",
                universe="fake",
                started_at="2026-06-28T12:00:00Z",
                completed_at="2026-06-28T12:01:00Z",
                status="OK",
                results=results_by_run[run_number],
                notes=[f"raw-note-{run_number}"],
            )

    fake = FakeScanner()

    class NoopEvidenceService:
        def enrich_candidates(self, candidates):
            return candidates

    output = SmallCapScannerService(
        scanner_service=fake,
        evidence_service=NoopEvidenceService(),
    ).scan(
        tickers="HOT,OKAY",
        preset_name="sykes_small_cap_v0",
    )

    assert len(fake.calls) == 3
    assert [
        (
            call["filters"].min_market_cap,
            call["filters"].max_market_cap,
        )
        for call in fake.calls
    ] == [
        (0, 50_000_000),
        (50_000_000, 300_000_000),
        (300_000_000, 2_000_000_000),
    ]
    assert [call["tickers"] for call in fake.calls] == ["HOT,OKAY"] * 3

    assert output.preset == "sykes_small_cap_v0"
    assert output.candidate_count == 2
    assert output.run_ids == ["run-1", "run-2", "run-3"]
    assert [candidate.ticker for candidate in output.candidates] == ["HOT", "OKAY"]
    assert output.candidates[0].score > output.candidates[1].score
