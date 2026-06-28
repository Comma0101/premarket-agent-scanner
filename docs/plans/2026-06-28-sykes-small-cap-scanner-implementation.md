# Sykes-Style Small-Cap Scanner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a source-backed small-cap discovery scanner that ranks Sykes-style watchlist candidates using current scanner data while explicitly surfacing unsupported fields as unknown.

**Architecture:** Add a generic small-cap scanner layer that composes the existing `ScannerService` instead of duplicating provider logic. Presets live in YAML, scoring lives in `services/small_cap_scanner_service.py`, and the agent/tool surface exposes a JSON-safe `scan_small_caps` wrapper.

**Tech Stack:** Python dataclasses, existing SQLite/provider services, YAML via existing `pyyaml` dependency, Typer CLI, pytest, Ruff.

---

## Prerequisite

Implement this on a branch that contains or can reference the Timothy Sykes
research dossier:

- `docs/research/timothy_sykes/source_inventory.md`
- `docs/research/timothy_sykes/evidence_matrix.md`
- `docs/research/timothy_sykes/distillation_notes.md`
- `docs/research/timothy_sykes/data_gap_report.md`

If those files are not present, do not block implementation, but keep every
Sykes-style threshold documented as pragmatic rather than source-explicit.

### Task 1: Preset Model And Loader

**Files:**
- Modify: `app/models.py`
- Create: `data/scanner_presets.yaml`
- Create: `services/scanner_preset_service.py`
- Test: `tests/test_small_cap_scanner.py`

**Step 1: Write failing tests for preset loading**

Add to `tests/test_small_cap_scanner.py`:

```python
from pathlib import Path

import pytest

from services.scanner_preset_service import PresetService


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
        "example:\\n"
        "  cap_tiers: [small]\\n"
        "  direction: up\\n"
        "  min_gap_abs: 5\\n",
        encoding="utf-8",
    )
    service = PresetService(path)

    with pytest.raises(KeyError) as exc:
        service.get_preset("missing")

    assert "example" in str(exc.value)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
```

Expected: fail because `services.scanner_preset_service` does not exist.

**Step 3: Add preset dataclass to `app/models.py`**

Add:

```python
@dataclass
class SmallCapScannerPreset:
    name: str
    cap_tiers: list[str]
    direction: Direction = "up"
    min_gap_abs: float = 5.0
    min_volume: float | None = None
    min_rel_volume: float | None = 2.0
    include_low_confidence: bool = False
    missing_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
```

**Step 4: Create `data/scanner_presets.yaml`**

```yaml
sykes_small_cap_v0:
  cap_tiers:
    - nano
    - micro
    - small
  direction: up
  min_gap_abs: 5.0
  min_volume: 500000
  min_rel_volume: 2.0
  include_low_confidence: false
  missing_fields:
    - float
    - catalyst
    - filings
    - former_runner
    - liquidity
    - short_interest
  notes:
    - "Listed small-cap discovery preset."
    - "Thresholds are pragmatic defaults, not source-explicit Timothy Sykes criteria."
    - "Unsupported fields must remain unknown, not inferred."
```

**Step 5: Create `services/scanner_preset_service.py`**

Implement:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config import BASE_DIR
from app.models import SmallCapScannerPreset


class PresetService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or BASE_DIR / "data" / "scanner_presets.yaml"

    def list_presets(self) -> list[str]:
        return sorted(self._load().keys())

    def get_preset(self, name: str) -> SmallCapScannerPreset:
        raw = self._load()
        key = name.strip()
        if key not in raw:
            valid = ", ".join(sorted(raw)) or "(none)"
            raise KeyError(f"Unknown scanner preset: {name}. Valid presets: {valid}.")
        data = raw[key] or {}
        return SmallCapScannerPreset(
            name=key,
            cap_tiers=[str(item) for item in data.get("cap_tiers", [])],
            direction=data.get("direction", "up"),
            min_gap_abs=float(data.get("min_gap_abs", 5.0)),
            min_volume=_optional_float(data.get("min_volume")),
            min_rel_volume=_optional_float(data.get("min_rel_volume", 2.0)),
            include_low_confidence=bool(data.get("include_low_confidence", False)),
            missing_fields=[str(item) for item in data.get("missing_fields", [])],
            notes=[str(item) for item in data.get("notes", [])],
        )

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{self.path} must contain a mapping of preset names.")
        return loaded


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
```

**Step 6: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
```

Expected: pass.

**Step 7: Commit**

```bash
git add app/models.py data/scanner_presets.yaml services/scanner_preset_service.py tests/test_small_cap_scanner.py
git commit -m "Add small-cap scanner presets"
```

### Task 2: Candidate Models And Scoring

**Files:**
- Modify: `app/models.py`
- Create: `services/small_cap_scanner_service.py`
- Test: `tests/test_small_cap_scanner.py`

**Step 1: Write failing scoring tests**

Append:

```python
from app.models import ScannerResult
from services.small_cap_scanner_service import grade_small_cap_candidate


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


def test_conflict_candidate_is_rejected():
    candidate = grade_small_cap_candidate(
        _result(confidence="CONFLICT"),
        missing_fields=[],
    )

    assert candidate.grade == "REJECT"
    assert "unusable_confidence" in candidate.matched_signals
```

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
```

Expected: fail because `services.small_cap_scanner_service` does not exist.

**Step 3: Add candidate models to `app/models.py`**

Add:

```python
SmallCapGrade = Literal["A_WATCH", "B_WATCH", "C_WATCH", "REJECT"]


@dataclass
class SmallCapCandidate:
    ticker: str
    name: str | None
    market_cap: float | None
    gap_pct: float | None
    gap_dollar: float | None
    volume: float | None
    rel_volume: float | None
    confidence: Confidence
    score: int
    grade: SmallCapGrade
    matched_signals: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    timestamp: str | None = None
```

**Step 4: Create `services/small_cap_scanner_service.py`**

Implement `grade_small_cap_candidate(result, missing_fields)`:

```python
from __future__ import annotations

from app.models import ScannerResult, SmallCapCandidate

UNUSABLE_CONFIDENCE = {"ERROR", "CONFLICT", "STALE_DATA", "MISSING_PREVIOUS_CLOSE", "MISSING_PREMARKET_PRICE"}


def grade_small_cap_candidate(
    result: ScannerResult,
    *,
    missing_fields: list[str],
) -> SmallCapCandidate:
    score = 0
    matched: list[str] = []
    risk_notes: list[str] = []

    if result.confidence in UNUSABLE_CONFIDENCE:
        matched.append("unusable_confidence")
        risk_notes.append(f"Rejected because confidence is {result.confidence}.")
        return _candidate(result, 0, "REJECT", matched, missing_fields, risk_notes)

    if result.gap_pct is None or result.gap_pct <= 0:
        matched.append("no_positive_gap")
        return _candidate(result, 0, "REJECT", matched, missing_fields, ["No positive gap."])

    if result.market_cap is None:
        matched.append("missing_market_cap")
        risk_notes.append("Market cap is unknown, so small-cap fit cannot be confirmed.")
    elif result.market_cap <= 2_000_000_000:
        score += 20
        matched.append("small_cap_fit")
    else:
        matched.append("too_large")
        return _candidate(result, 0, "REJECT", matched, missing_fields, ["Market cap is outside small-cap scope."])

    if result.gap_pct >= 10:
        score += 25
        matched.append("strong_gap")
    elif result.gap_pct >= 5:
        score += 15
        matched.append("gap_up")

    if result.rel_volume is not None and result.rel_volume >= 3:
        score += 25
        matched.append("high_rvol")
    elif result.rel_volume is not None and result.rel_volume >= 2:
        score += 15
        matched.append("rvol_confirmed")
    else:
        risk_notes.append("Relative volume is weak or unknown.")

    if result.volume is not None and result.volume >= 1_000_000:
        score += 20
        matched.append("liquid_volume")
    elif result.volume is not None and result.volume >= 500_000:
        score += 10
        matched.append("minimum_volume")
    else:
        risk_notes.append("Volume is below the preferred small-cap scanner floor or unknown.")

    if result.confidence == "OK":
        score += 10
        matched.append("clean_confidence")
    else:
        risk_notes.append(f"Data confidence is {result.confidence}.")

    for field in missing_fields:
        risk_notes.append(f"{field} is unknown; do not infer it from price or volume.")

    grade = _grade(score, missing_fields)
    return _candidate(result, score, grade, matched, missing_fields, risk_notes)


def _grade(score: int, missing_fields: list[str]) -> str:
    if score >= 80 and len(missing_fields) <= 6:
        return "A_WATCH"
    if score >= 60:
        return "B_WATCH"
    if score >= 35:
        return "C_WATCH"
    return "REJECT"


def _candidate(
    result: ScannerResult,
    score: int,
    grade: str,
    matched: list[str],
    missing_fields: list[str],
    risk_notes: list[str],
) -> SmallCapCandidate:
    return SmallCapCandidate(
        ticker=result.ticker,
        name=result.name,
        market_cap=result.market_cap,
        gap_pct=result.gap_pct,
        gap_dollar=result.gap_dollar,
        volume=result.volume,
        rel_volume=result.rel_volume,
        confidence=result.confidence,
        score=score,
        grade=grade,  # type: ignore[arg-type]
        matched_signals=matched,
        missing_fields=missing_fields,
        risk_notes=risk_notes,
        sources=result.sources,
        timestamp=result.timestamp,
    )
```

**Step 5: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
git add app/models.py services/small_cap_scanner_service.py tests/test_small_cap_scanner.py
git commit -m "Add small-cap candidate scoring"
```

### Task 3: Small-Cap Scanner Service

**Files:**
- Modify: `app/models.py`
- Modify: `services/small_cap_scanner_service.py`
- Test: `tests/test_small_cap_scanner.py`

**Step 1: Write failing service tests**

Append:

```python
from app.models import ScanRunOutput
from services.small_cap_scanner_service import SmallCapScannerService


class FakeScanner:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def scan(self, **kwargs):
        self.calls.append(kwargs)
        return self.output


def test_small_cap_scanner_runs_each_cap_tier_and_ranks_candidates():
    output = ScanRunOutput(
        run_id="abc123",
        universe=None,
        started_at="2026-06-28T12:00:00Z",
        completed_at="2026-06-28T12:01:00Z",
        status="OK",
        results=[_result(ticker="HOT"), _result(ticker="OKAY", gap_pct=6.0, rel_volume=2.1)],
    )
    fake = FakeScanner(output)
    scanner = SmallCapScannerService(scanner_service=fake)

    out = scanner.scan(tickers="HOT,OKAY", preset_name="sykes_small_cap_v0")

    assert out["preset"] == "sykes_small_cap_v0"
    assert out["candidate_count"] == 2
    assert out["candidates"][0].ticker == "HOT"
    assert {call["filters"].max_market_cap for call in fake.calls}
```

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
```

Expected: fail because `SmallCapScannerService` does not exist or lacks `scan`.

**Step 3: Add run-output model to `app/models.py`**

Add:

```python
@dataclass
class SmallCapScanOutput:
    preset: str
    run_ids: list[str]
    candidate_count: int
    candidates: list[SmallCapCandidate]
    notes: list[str] = field(default_factory=list)
```

**Step 4: Implement `SmallCapScannerService.scan`**

In `services/small_cap_scanner_service.py`, add:

```python
from app.models import SmallCapScanOutput, make_scan_filters
from services.scanner_service import ScannerService
from services.scanner_preset_service import PresetService


class SmallCapScannerService:
    def __init__(
        self,
        *,
        scanner_service: ScannerService | None = None,
        preset_service: PresetService | None = None,
    ) -> None:
        self.scanner_service = scanner_service or ScannerService()
        self.preset_service = preset_service or PresetService()

    def scan(
        self,
        *,
        preset_name: str = "sykes_small_cap_v0",
        universe: str | None = None,
        watchlist: str | None = None,
        tickers: str | None = None,
        all_universes: bool = False,
    ) -> SmallCapScanOutput:
        preset = self.preset_service.get_preset(preset_name)
        candidates: list[SmallCapCandidate] = []
        run_ids: list[str] = []
        notes: list[str] = list(preset.notes)

        for tier in preset.cap_tiers:
            filters = make_scan_filters(
                cap_tier=tier,
                min_gap_abs=preset.min_gap_abs,
                min_volume=preset.min_volume,
                min_rel_volume=preset.min_rel_volume,
                direction=preset.direction,
                include_low_confidence=preset.include_low_confidence,
            )
            output = self.scanner_service.scan(
                universe=universe,
                watchlist=watchlist,
                tickers=tickers,
                all_universes=all_universes,
                filters=filters,
            )
            run_ids.append(output.run_id)
            notes.extend(output.notes)
            for result in output.results:
                candidate = grade_small_cap_candidate(
                    result,
                    missing_fields=list(preset.missing_fields),
                )
                if candidate.grade != "REJECT":
                    candidates.append(candidate)

        candidates = _dedupe_and_sort(candidates)
        return SmallCapScanOutput(
            preset=preset.name,
            run_ids=run_ids,
            candidate_count=len(candidates),
            candidates=candidates,
            notes=notes,
        )


def _dedupe_and_sort(candidates: list[SmallCapCandidate]) -> list[SmallCapCandidate]:
    best: dict[str, SmallCapCandidate] = {}
    for candidate in candidates:
        current = best.get(candidate.ticker)
        if current is None or candidate.score > current.score:
            best[candidate.ticker] = candidate
    return sorted(best.values(), key=lambda item: item.score, reverse=True)
```

**Step 5: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
git add app/models.py services/small_cap_scanner_service.py tests/test_small_cap_scanner.py
git commit -m "Add small-cap scanner service"
```

### Task 4: JSON Tool Surface

**Files:**
- Modify: `agent_tools/tools.py`
- Modify: `agent_tools/definitions.py`
- Test: `tests/test_agent_tools.py`

**Step 1: Write failing tool tests**

Add to `tests/test_agent_tools.py`:

```python
def test_scan_small_caps_tool_returns_candidates(monkeypatch):
    from app.models import SmallCapCandidate, SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            return SmallCapScanOutput(
                preset=kwargs["preset_name"],
                run_ids=["run1"],
                candidate_count=1,
                candidates=[
                    SmallCapCandidate(
                        ticker="HOT",
                        name=None,
                        market_cap=100_000_000,
                        gap_pct=12.0,
                        gap_dollar=1.2,
                        volume=2_000_000,
                        rel_volume=5.0,
                        confidence="OK",
                        score=90,
                        grade="A_WATCH",
                        matched_signals=["strong_gap"],
                        missing_fields=["float"],
                        risk_notes=["float is unknown"],
                    )
                ],
                notes=["note"],
            )

    out = tools.scan_small_caps(
        tickers="HOT",
        preset_name="sykes_small_cap_v0",
        service=FakeSmallCapService(),
    )

    assert out["candidate_count"] == 1
    assert out["candidates"][0]["ticker"] == "HOT"
    assert out["candidates"][0]["grade"] == "A_WATCH"
    assert "float" in out["candidates"][0]["missing_fields"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_tools.py::test_scan_small_caps_tool_returns_candidates -q
```

Expected: fail because `scan_small_caps` does not exist.

**Step 3: Add `scan_small_caps` to `agent_tools/tools.py`**

Implement JSON conversion:

```python
def _small_cap_candidate_to_dict(candidate) -> dict[str, Any]:
    return {
        "ticker": candidate.ticker,
        "name": candidate.name,
        "market_cap": candidate.market_cap,
        "gap_pct": candidate.gap_pct,
        "gap_dollar": candidate.gap_dollar,
        "volume": candidate.volume,
        "rel_volume": candidate.rel_volume,
        "confidence": candidate.confidence,
        "score": candidate.score,
        "grade": candidate.grade,
        "matched_signals": candidate.matched_signals,
        "missing_fields": candidate.missing_fields,
        "risk_notes": candidate.risk_notes,
        "sources": candidate.sources,
        "timestamp": candidate.timestamp,
    }


def scan_small_caps(
    *,
    preset_name: str = "sykes_small_cap_v0",
    universe: str | None = None,
    watchlist: str | None = None,
    tickers: str | None = None,
    all_universes: bool = False,
    service: Any | None = None,
) -> dict[str, Any]:
    if not any([universe, watchlist, tickers, all_universes]):
        return {"error": "Provide at least one of: universe, watchlist, tickers, or all_universes."}

    from services.small_cap_scanner_service import SmallCapScannerService

    scanner = service or SmallCapScannerService()
    try:
        output = scanner.scan(
            preset_name=preset_name,
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            all_universes=all_universes,
        )
    except KeyError as exc:
        return {"error": str(exc)}

    return {
        "preset": output.preset,
        "run_ids": output.run_ids,
        "candidate_count": output.candidate_count,
        "candidates": [_small_cap_candidate_to_dict(item) for item in output.candidates],
        "notes": output.notes,
    }
```

**Step 4: Add schema and dispatch entry**

In `agent_tools/definitions.py`, add a tool definition for `scan_small_caps` and add:

```python
"scan_small_caps": tools.scan_small_caps,
```

The schema should expose:

- `preset_name`
- `universe`
- `watchlist`
- `tickers`
- `all_universes`

Description must say it is a small-cap watchlist scanner, not a trade
recommendation engine.

**Step 5: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_tools.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
git add agent_tools/tools.py agent_tools/definitions.py tests/test_agent_tools.py
git commit -m "Expose small-cap scanner tool"
```

### Task 5: CLI Entry Point

**Files:**
- Create: `cli/scan_small_caps.py`
- Modify: `pyproject.toml` only if package list needs no change; otherwise leave it untouched.
- Test: `tests/test_small_cap_scanner.py`

**Step 1: Write a lightweight CLI render test**

If the project has no CLI test pattern, keep this task simple and test only that
the module imports:

```python
def test_scan_small_caps_cli_imports():
    import cli.scan_small_caps as module

    assert module.app is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py::test_scan_small_caps_cli_imports -q
```

Expected: fail because `cli.scan_small_caps` does not exist.

**Step 3: Create `cli/scan_small_caps.py`**

Implement Typer CLI:

```python
from __future__ import annotations

import typer

from cli._render import format_gap, format_market_cap, format_price, format_rvol
from services.small_cap_scanner_service import SmallCapScannerService

app = typer.Typer(add_completion=False, help="Small-cap discovery scanner.")


@app.command()
def main(
    preset_name: str = typer.Option("sykes_small_cap_v0", "--preset"),
    universe: str = typer.Option(None, "--universe", "-u"),
    watchlist: str = typer.Option(None, "--watchlist", "-w"),
    tickers: str = typer.Option(None, "--tickers", "-t"),
    all_universes: bool = typer.Option(False, "--all"),
) -> None:
    if not any([universe, watchlist, tickers, all_universes]):
        raise typer.BadParameter("Pick a selection: --universe, --watchlist, --tickers, or --all.")

    output = SmallCapScannerService().scan(
        preset_name=preset_name,
        universe=universe,
        watchlist=watchlist,
        tickers=tickers,
        all_universes=all_universes,
    )
    _render(output)


def _render(output) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _render_plain(output)
        return

    table = Table(title=f"Small-cap scan [{output.preset}]", header_style="bold")
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Grade")
    table.add_column("Score", justify="right")
    table.add_column("Gap", justify="right")
    table.add_column("RVol", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Mkt Cap", justify="right")
    table.add_column("Missing")
    for item in output.candidates:
        table.add_row(
            item.ticker,
            item.grade,
            str(item.score),
            format_gap(item.gap_pct),
            format_rvol(item.rel_volume),
            format_price(item.volume),
            format_market_cap(item.market_cap),
            ", ".join(item.missing_fields) or "-",
        )
    console = Console()
    console.print(table)
    for note in output.notes:
        console.print(f"[dim]note: {note}[/dim]")


def _render_plain(output) -> None:
    print(f"Small-cap scan [{output.preset}]")
    for item in output.candidates:
        print(f"{item.ticker:<6} {item.grade:<8} score={item.score:>3} gap={format_gap(item.gap_pct):>8}")


if __name__ == "__main__":
    app()
```

**Step 4: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add cli/scan_small_caps.py tests/test_small_cap_scanner.py
git commit -m "Add small-cap scanner CLI"
```

### Task 6: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Test: all relevant tests

**Step 1: Update README**

Add a short section:

```markdown
## Small-Cap Discovery Scanner

`python -m cli.scan_small_caps` runs a listed small-cap discovery scan using
named presets such as `sykes_small_cap_v0`. The scanner ranks watchlist
candidates by gap, volume, RVOL, cap fit, and data confidence, while surfacing
unsupported fields like float, catalyst, filings, former-runner history,
liquidity, and short-interest context as unknown.

Example:

```bash
python -m cli.scan_small_caps --all --preset sykes_small_cap_v0
```

The output is watchlist context only, not buy/sell advice.
```

**Step 2: Run targeted tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py tests/test_agent_tools.py -q
```

Expected: pass.

**Step 3: Run full verification**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
git diff --check
```

Expected: all pass.

**Step 4: Commit**

```bash
git add README.md
git commit -m "Document small-cap discovery scanner"
```

### Task 7: Stop Before Agent/Profile Work

**Files:**
- Read: `docs/plans/2026-06-28-sykes-small-cap-scanner-design.md`
- Read: `data/scanner_presets.yaml`
- Read: `agent_tools/definitions.py`

**Step 1: Summarize implementation**

Report:

- preset names
- new tool name
- CLI command
- tests run
- unsupported fields still surfaced as unknown

**Step 2: Stop**

Do not create:

- `trader_profiles/timothy_sykes.md`
- `.claude/agents/sykes-style-desk.md`

Ask whether to proceed next with:

1. data-layer enrichment for float/news/filings/former-runners,
2. trader profile on top of the scanner,
3. dedicated agent surface.
