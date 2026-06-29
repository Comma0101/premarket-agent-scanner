# Small-Cap Evidence Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enrich small-cap scanner candidates with source-backed float, filing, catalyst, and former-runner evidence while preserving unknowns when data is unavailable.

**Architecture:** Add evidence dataclasses and cache helpers, then introduce `SmallCapEvidenceService` as a narrow enrichment layer composed by `SmallCapScannerService`. Provider integrations stay behind interfaces/fakes in tests; v1 uses existing profile data plus SEC filing metadata and leaves unavailable news/short-interest data explicitly unknown.

**Tech Stack:** Python dataclasses, SQLite cache helpers, existing provider/service patterns, SEC JSON metadata via `requests`, Typer CLI, pytest, Ruff.

---

## Prerequisite

Implement from the branch that already contains the small-cap scanner:

- `services/small_cap_scanner_service.py`
- `services/scanner_preset_service.py`
- `data/scanner_presets.yaml`
- `cli/scan_small_caps.py`
- `agent_tools/tools.py`

Use TDD for each task. Do not create a trader profile or dedicated agent file in this plan.

### Task 1: Evidence Models And Cache Tables

**Files:**
- Modify: `app/models.py`
- Modify: `app/db.py`
- Test: `tests/test_small_cap_evidence.py`

**Step 1: Write failing database/model tests**

Create `tests/test_small_cap_evidence.py`:

```python
from app.db import (
    get_cached_filings,
    get_cached_news,
    get_runner_history,
    insert_filing_event,
    insert_news_event,
    insert_runner_event,
)
from app.models import CatalystEvent, FilingEvent, FormerRunnerEvent, SmallCapEvidence


def test_evidence_models_default_to_unknown_fields():
    evidence = SmallCapEvidence(ticker="HOT", missing_fields=["float", "catalyst"])

    assert evidence.ticker == "HOT"
    assert evidence.float_shares is None
    assert evidence.filings == []
    assert evidence.catalysts == []
    assert evidence.missing_fields == ["float", "catalyst"]


def test_evidence_cache_round_trips_filings_news_and_runner_history(tmp_path):
    db_path = tmp_path / "evidence.sqlite"

    insert_filing_event(
        db_path,
        FilingEvent(
            ticker="HOT",
            form_type="S-1",
            filed_at="2026-06-28",
            accession_number="0000000000-26-000001",
            description="Registration statement",
            source_url="https://www.sec.gov/Archives/example",
            risk_tags=["offering"],
        ),
    )
    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT announces contract",
            published_at="2026-06-28T12:00:00Z",
            source="fake-news",
            url="https://example.test/hot",
            summary="Contract headline",
            confidence="OK",
        ),
    )
    insert_runner_event(
        db_path,
        FormerRunnerEvent(
            ticker="HOT",
            event_date="2026-06-01",
            max_gap_pct=180.0,
            max_volume=12_000_000,
            source_run_id="run123",
            notes=["prior large gap"],
        ),
    )

    filings = get_cached_filings(db_path, "HOT")
    news = get_cached_news(db_path, "HOT")
    runners = get_runner_history(db_path, "HOT")

    assert filings[0].form_type == "S-1"
    assert filings[0].risk_tags == ["offering"]
    assert news[0].headline == "HOT announces contract"
    assert runners[0].max_gap_pct == 180.0
```

**Step 2: Run tests to verify they fail**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

Expected: import failures for missing evidence models and DB helpers.

**Step 3: Add evidence dataclasses**

In `app/models.py`, add:

```python
@dataclass
class FilingEvent:
    ticker: str
    form_type: str
    filed_at: str
    accession_number: str
    description: str | None = None
    source_url: str | None = None
    risk_tags: list[str] = field(default_factory=list)


@dataclass
class CatalystEvent:
    ticker: str
    headline: str
    published_at: str | None
    source: str
    url: str | None = None
    summary: str | None = None
    confidence: str = "UNKNOWN"


@dataclass
class FormerRunnerEvent:
    ticker: str
    event_date: str
    max_gap_pct: float | None = None
    max_volume: float | None = None
    source_run_id: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class SmallCapEvidence:
    ticker: str
    float_shares: float | None = None
    shares_outstanding: float | None = None
    float_source: str | None = None
    exchange: str | None = None
    is_low_float: bool | None = None
    filings: list[FilingEvent] = field(default_factory=list)
    catalysts: list[CatalystEvent] = field(default_factory=list)
    former_runner: FormerRunnerEvent | None = None
    missing_fields: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now_iso)
```

Add `evidence: SmallCapEvidence | None = None` to `SmallCapCandidate`.

**Step 4: Add cache tables and helpers**

In `app/db.py`:

- Extend `SCHEMA_SQL` with `ticker_filings`, `ticker_news`, and `ticker_runner_history`.
- Add JSON helper functions for list fields.
- Add helpers:
  - `insert_filing_event(db_path, event)`
  - `get_cached_filings(db_path, ticker, limit=10)`
  - `insert_news_event(db_path, event)`
  - `get_cached_news(db_path, ticker, limit=10)`
  - `insert_runner_event(db_path, event)`
  - `get_runner_history(db_path, ticker, limit=5)`

Use `get_connection(db_path)` inside each helper, close connections, and make
upserts idempotent where possible.

**Step 5: Run tests**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
git add app/models.py app/db.py tests/test_small_cap_evidence.py
git commit -m "Add small-cap evidence models"
```

### Task 2: Profile Evidence Service

**Files:**
- Create: `services/small_cap_evidence_service.py`
- Modify: `tests/test_small_cap_evidence.py`

**Step 1: Write failing profile enrichment tests**

Append:

```python
from app.models import AssetProfile, SmallCapCandidate
from services.small_cap_evidence_service import SmallCapEvidenceService


class FakeProfileService:
    def get_profile(self, ticker: str):
        if ticker == "HOT":
            return AssetProfile(
                ticker="HOT",
                exchange="NASDAQ",
                shares_outstanding=20_000_000,
                float_shares=8_000_000,
                source="fake-profile",
            )
        return None


def _candidate(ticker="HOT"):
    return SmallCapCandidate(
        ticker=ticker,
        name=None,
        market_cap=100_000_000,
        gap_pct=12.0,
        gap_dollar=1.2,
        volume=2_000_000,
        rel_volume=5.0,
        confidence="OK",
        score=90,
        grade="A_WATCH",
        missing_fields=["float", "catalyst", "filings", "former_runner"],
    )


def test_evidence_service_populates_float_from_profile():
    service = SmallCapEvidenceService(profile_service=FakeProfileService())

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.float_shares == 8_000_000
    assert enriched.evidence.is_low_float is True
    assert "float" not in enriched.evidence.missing_fields
    assert "float_known" in enriched.matched_signals
    assert "fake-profile" in enriched.evidence.sources


def test_evidence_service_keeps_float_unknown_when_profile_missing():
    service = SmallCapEvidenceService(profile_service=FakeProfileService())

    enriched = service.enrich_candidates([_candidate("MISS")])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.float_shares is None
    assert "float" in enriched.evidence.missing_fields
    assert any("float is unknown" in note for note in enriched.evidence.risk_notes)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

Expected: import failure for missing service.

**Step 3: Implement `SmallCapEvidenceService` profile enrichment**

Create `services/small_cap_evidence_service.py` with:

- constructor accepting `profile_service`, `filing_provider`, `news_provider`, `db_path`, `low_float_threshold=10_000_000`
- `enrich_candidates(candidates: list[SmallCapCandidate]) -> list[SmallCapCandidate]`
- `_build_evidence(candidate)` that:
  - starts from `candidate.missing_fields`
  - loads profile through injected profile service
  - sets float/shares/exchange/source
  - marks `is_low_float`
  - removes `float` from evidence missing fields only when `float_shares` is known
  - appends `float_known` or `low_float_context` to candidate matched signals
  - appends risk notes for unknown float

Keep this task limited to profile evidence. Filing/news/former-runner fields can
stay unknown until later tasks.

**Step 4: Run tests**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add services/small_cap_evidence_service.py tests/test_small_cap_evidence.py
git commit -m "Add profile evidence enrichment"
```

### Task 3: SEC Filing Metadata Provider

**Files:**
- Create: `providers/sec_provider.py`
- Modify: `services/small_cap_evidence_service.py`
- Modify: `tests/test_small_cap_evidence.py`

**Step 1: Write failing SEC provider and service tests**

Append:

```python
from app.models import FilingEvent
from providers.sec_provider import classify_filing_risk


class FakeFilingProvider:
    def get_recent_filings(self, ticker: str):
        return [
            FilingEvent(
                ticker=ticker,
                form_type="S-1",
                filed_at="2026-06-27",
                accession_number="0000000000-26-000002",
                description="Securities registration statement",
                source_url="https://www.sec.gov/Archives/example",
                risk_tags=["offering"],
            )
        ]


def test_classify_filing_risk_tags_offering_forms():
    assert classify_filing_risk("S-1", "Registration statement") == ["offering"]
    assert classify_filing_risk("8-K", "Entry into a Material Definitive Agreement") == []


def test_evidence_service_attaches_recent_filings_and_removes_missing_field():
    service = SmallCapEvidenceService(
        profile_service=FakeProfileService(),
        filing_provider=FakeFilingProvider(),
    )

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.filings[0].form_type == "S-1"
    assert "filings" not in enriched.evidence.missing_fields
    assert any("offering" in note.lower() for note in enriched.evidence.risk_notes)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

Expected: import failure for missing `providers.sec_provider`.

**Step 3: Add SEC provider**

Create `providers/sec_provider.py`.

Implement:

- `SECProvider.get_recent_filings(ticker: str, limit: int = 10) -> list[FilingEvent]`
- `classify_filing_risk(form_type: str, description: str | None) -> list[str]`

Provider behavior:

- Use SEC company ticker mapping to resolve CIK.
- Use SEC submissions endpoint for recent filings.
- Set a browser-like `User-Agent` from config/env if available, otherwise a
  conservative project identifier.
- Catch network/provider errors and return `[]`.
- Do not claim "no filing risk" when the provider fails.

Risk tag rules for v1:

- `offering`: forms `S-1`, `S-3`, `424B`, `424B3`, `424B5`, descriptions with
  "offering", "registration", or "prospectus"
- `dilution_context`: descriptions with "warrant", "convertible", "purchase agreement"
- `reverse_split`: descriptions with "reverse split"

**Step 4: Update evidence service**

In `services/small_cap_evidence_service.py`:

- call `filing_provider.get_recent_filings(ticker)` when a provider is injected
- attach filing events
- remove `filings` from evidence missing fields when at least one filing was returned
- add risk notes for filing risk tags
- catch provider errors and keep `filings` unknown

**Step 5: Run tests**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
git add providers/sec_provider.py services/small_cap_evidence_service.py tests/test_small_cap_evidence.py
git commit -m "Add SEC filing evidence"
```

### Task 4: Attach Evidence To Small-Cap Scanner

**Files:**
- Modify: `services/small_cap_scanner_service.py`
- Modify: `tests/test_small_cap_scanner.py`

**Step 1: Write failing scanner integration test**

Append to `tests/test_small_cap_scanner.py`:

```python
from app.models import SmallCapEvidence


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

    assert output.candidates[0].evidence is not None
    assert output.candidates[0].evidence.float_shares == 8_000_000
```

**Step 2: Run test to verify it fails**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_scanner.py::test_small_cap_scanner_attaches_evidence_to_candidates -q
```

Expected: constructor does not accept `evidence_service`.

**Step 3: Update scanner service**

In `SmallCapScannerService.__init__`, accept `evidence_service=None`.

After dedupe/sort, run:

```python
if self.evidence_service is not None:
    candidates = self.evidence_service.enrich_candidates(candidates)
```

Default to `SmallCapEvidenceService()` so normal scans are enriched. Keep tests
fast by allowing injected fakes.

**Step 4: Run tests**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_scanner.py tests/test_small_cap_evidence.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add services/small_cap_scanner_service.py tests/test_small_cap_scanner.py
git commit -m "Attach evidence to small-cap scans"
```

### Task 5: JSON Tool Evidence Output

**Files:**
- Modify: `agent_tools/tools.py`
- Modify: `tests/test_agent_tools.py`

**Step 1: Write failing tool serialization test**

Modify `test_scan_small_caps_tool_returns_candidates` to include evidence:

```python
from app.models import SmallCapEvidence

# inside the fake candidate:
evidence=SmallCapEvidence(
    ticker="HOT",
    float_shares=8_000_000,
    is_low_float=True,
    missing_fields=["catalyst"],
    risk_notes=["filings are unknown"],
)

# assertions:
assert out["candidates"][0]["evidence"]["float_shares"] == 8_000_000
assert out["candidates"][0]["evidence"]["is_low_float"] is True
assert "catalyst" in out["candidates"][0]["evidence"]["missing_fields"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_agent_tools.py::test_scan_small_caps_tool_returns_candidates -q
```

Expected: missing `evidence` key in candidate JSON.

**Step 3: Add evidence serializers**

In `agent_tools/tools.py`, add serializers for:

- `FilingEvent`
- `CatalystEvent`
- `FormerRunnerEvent`
- `SmallCapEvidence`

Then include:

```python
"evidence": _small_cap_evidence_to_dict(candidate.evidence),
```

Return `None` when evidence is `None`.

**Step 4: Run tests**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_agent_tools.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add agent_tools/tools.py tests/test_agent_tools.py
git commit -m "Expose small-cap evidence in tool output"
```

### Task 6: CLI Evidence Rendering

**Files:**
- Modify: `cli/scan_small_caps.py`
- Modify: `tests/test_small_cap_scanner.py`

**Step 1: Write failing render unit test**

Add a small pure render helper test if needed. Prefer testing helper functions
instead of invoking live providers:

```python
from app.models import SmallCapEvidence
from cli.scan_small_caps import _format_evidence_float


def test_scan_small_caps_cli_formats_evidence_float():
    evidence = SmallCapEvidence(ticker="HOT", float_shares=8_000_000, is_low_float=True)

    assert _format_evidence_float(evidence) == "8.0M low"
    assert _format_evidence_float(None) == "-"
```

**Step 2: Run test to verify it fails**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_scanner.py::test_scan_small_caps_cli_formats_evidence_float -q
```

Expected: missing helper.

**Step 3: Update CLI table**

In `cli/scan_small_caps.py`:

- add columns:
  - `Float`
  - `Catalyst`
  - `Filing Risk`
  - `Former`
- add helpers:
  - `_format_evidence_float(evidence)`
  - `_format_catalyst(evidence)`
  - `_format_filing_risk(evidence)`
  - `_format_former_runner(evidence)`

Keep values compact and use `-` for unknowns.

**Step 4: Run tests**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add cli/scan_small_caps.py tests/test_small_cap_scanner.py
git commit -m "Render small-cap evidence in CLI"
```

### Task 7: Documentation And Final Verification

**Files:**
- Modify: `README.md`

**Step 1: Update README**

Add to the Small-Cap Discovery Scanner section:

```markdown
The scanner can enrich candidates with evidence when data is available:
float/shares outstanding from profile providers, recent SEC filing metadata,
cached catalyst/news records, and local former-runner history. Missing evidence
is still shown as unknown rather than inferred.
```

Mention that short-interest/borrow data remains unsupported in v1.

**Step 2: Run targeted tests**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_small_cap_evidence.py tests/test_small_cap_scanner.py tests/test_agent_tools.py -q
```

Expected: pass.

**Step 3: Run full verification**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest -q
/home/comma/Documents/premarket-agent-scanner/.venv/bin/ruff check .
git diff --check
```

Expected: all pass.

**Step 4: Commit**

```bash
git add README.md
git commit -m "Document small-cap evidence enrichment"
```

### Task 8: Stop Before Agent/Profile Work

**Files:**
- Read: `docs/plans/2026-06-28-small-cap-evidence-enrichment-design.md`
- Read: `docs/plans/2026-06-28-small-cap-evidence-enrichment-implementation.md`
- Read: `agent_tools/tools.py`
- Read: `cli/scan_small_caps.py`

**Step 1: Final review checklist**

Verify:

- evidence is attached to scanner candidates
- tool JSON includes evidence blocks
- CLI displays compact evidence context
- unavailable fields remain unknown
- no broker execution exists
- no buy/sell recommendation text exists
- no `trader_profiles/timothy_sykes.md` created
- no `.claude/agents/sykes-style-desk.md` created

**Step 2: Final verification**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest -q
/home/comma/Documents/premarket-agent-scanner/.venv/bin/ruff check .
git diff --check
git status --short
```

**Step 3: Report and stop**

Report:

- branch name
- commits
- tests run
- evidence fields supported in v1
- fields still unknown or unsupported

Stop before building the trader profile or dedicated agent surface.
