# D3 Live Scan Performance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make live whole-market small-cap scans materially faster by adding bounded scanner concurrency and exposing it through CLI/agent surfaces.

**Architecture:** Add optional `max_workers` at the scanner-service boundary and keep provider/data-combination logic unchanged. The default core scanner remains serial; market-scan callers can opt into a modest worker count. All market facts still come from `SnapshotService` and downstream grading remains unchanged.

**Tech Stack:** Python `concurrent.futures.ThreadPoolExecutor`, dataclasses, Typer CLI, JSON-safe agent tools, pytest offline fakes, Ruff.

---

## Read First

1. Read `AGENTS.md`. Preserve the prime directive: never invent market numbers.
2. Use `.venv/bin/python`.
3. Tests must remain offline with injected fakes.
4. Commit after each task with `Co-Authored-By: Codex <codex@openai.com>`.
5. Do not push or merge D3 without explicit human approval.

---

### Task 1: Add bounded concurrency to ScannerService

**Files:**
- Modify: `services/scanner_service.py`
- Test: `tests/test_scanner.py`

**Step 1: Write the failing tests**

Add to `tests/test_scanner.py`:

```python
import time
```

Add a snapshot-service fake:

```python
class SlowSnapshotService:
    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay

    def build_snapshot(self, ticker: str):
        time.sleep(self.delay)
        return CombinedSnapshot(
            ticker=ticker,
            timestamp=utc_now_iso(),
            previous_close=10.0,
            premarket_price=11.0,
            latest_price=11.0,
            open_price=None,
            high=None,
            low=None,
            volume=2_000_000,
            source_primary="fake",
            source_secondary=None,
            confidence="OK",
            sources=["fake"],
            market_cap=500_000_000,
            average_volume=500_000,
            yfinance_data=ProviderPriceData(
                ticker=ticker,
                source="fake",
                previous_close=10.0,
                premarket_price=11.0,
                latest_price=11.0,
            ),
        )
```

Add:

```python
def test_scan_uses_bounded_concurrency_when_requested():
    tickers = ",".join(f"T{i}" for i in range(8))
    serial = ScannerService(
        universe_service=UniverseService(),
        snapshot_service=SlowSnapshotService(delay=0.03),
        persist=False,
    )
    concurrent = ScannerService(
        universe_service=UniverseService(),
        snapshot_service=SlowSnapshotService(delay=0.03),
        persist=False,
    )

    start = time.perf_counter()
    serial_out = serial.scan(tickers=tickers, filters=ScanFilters(), max_workers=1)
    serial_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    concurrent_out = concurrent.scan(tickers=tickers, filters=ScanFilters(), max_workers=4)
    concurrent_elapsed = time.perf_counter() - start

    assert len(serial_out.results) == 8
    assert len(concurrent_out.results) == 8
    assert concurrent_elapsed < serial_elapsed * 0.75
    assert "max_workers=4" in " ".join(concurrent_out.notes)
```

Add:

```python
def test_concurrent_scan_records_ticker_errors_as_notes():
    class RaisingSnapshotService(SlowSnapshotService):
        def build_snapshot(self, ticker: str):
            if ticker == "BAD":
                raise RuntimeError("provider timeout")
            return super().build_snapshot(ticker)

    out = ScannerService(
        universe_service=UniverseService(),
        snapshot_service=RaisingSnapshotService(delay=0),
        persist=False,
    ).scan(tickers="HOT,BAD,COOL", filters=ScanFilters(), max_workers=3)

    assert [result.ticker for result in out.results] == ["HOT", "COOL"]
    assert any("BAD: scan error: provider timeout" in note for note in out.notes)
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_scanner.py::test_scan_uses_bounded_concurrency_when_requested tests/test_scanner.py::test_concurrent_scan_records_ticker_errors_as_notes -q
```

Expected: `ScannerService.scan()` does not accept `max_workers`.

**Step 3: Implement minimal concurrency**

In `services/scanner_service.py`:

- import `as_completed` and `ThreadPoolExecutor` from `concurrent.futures`;
- add `max_workers: int = 1` to `ScannerService.scan()`;
- normalize with `worker_count = max(1, int(max_workers or 1))`;
- keep the existing serial loop when `worker_count == 1` or only one ticker exists;
- otherwise submit `_scan_ticker(...)` for each ticker and collect futures with `as_completed`;
- preserve the existing per-ticker exception note shape;
- add an operational note such as `Scanned 75 ticker(s) with max_workers=8.` when concurrency is used.

**Step 4: Verify**

Run:

```bash
.venv/bin/python -m pytest tests/test_scanner.py -q
```

**Step 5: Commit**

```bash
git add services/scanner_service.py tests/test_scanner.py
git commit -m "Add bounded scanner concurrency"
```

---

### Task 2: Thread max_workers through small-cap services and tools

**Files:**
- Modify: `services/small_cap_scanner_service.py`
- Modify: `agent_tools/tools.py`
- Modify: `agent_tools/definitions.py`
- Modify: `agent_orchestrator/trading_agent.py`
- Test: `tests/test_small_cap_market_scan.py`
- Test: `tests/test_agent_tools.py`
- Test: `tests/test_agent_orchestrator.py`

**Step 1: Write failing tests**

In `tests/test_small_cap_market_scan.py`, update the market fake scanner to assert:

```python
assert kwargs["max_workers"] == 6
```

Call:

```python
).scan(market="us-listed", market_limit=2, max_workers=6, preset_name="sykes_small_cap_v0")
```

In `tests/test_agent_tools.py::test_scan_small_caps_tool_accepts_market_selection`, add:

```python
assert kwargs["max_workers"] == 6
```

and call `tools.scan_small_caps(..., max_workers=6, ...)`.

In `tests/test_agent_orchestrator.py::test_orchestrator_can_run_market_scan`, call:

```python
TradingAgentOrchestrator(...).run_sykes_small_cap_watchlist(
    market="us-listed",
    market_limit=100,
    max_workers=6,
)
```

and assert `tool_input` includes `"max_workers": 6`.

Add or update the tool schema test to assert `max_workers` is present.

**Step 2: Run the tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_market_scan.py tests/test_agent_tools.py tests/test_agent_orchestrator.py -q
```

Expected: unexpected keyword or missing schema/property assertions.

**Step 3: Implement pass-through**

- Add `max_workers: int | None = None` to `SmallCapScannerService.scan()`.
- Pass `max_workers=max_workers or 1` into `self.scanner_service.scan(...)`.
- Add `max_workers` to `agent_tools.tools.scan_small_caps()` and pass it through.
- Add `max_workers` integer schema to `agent_tools/definitions.py` for `scan_small_caps`.
- Add `max_workers` to `TradingAgentOrchestrator.run_sykes_small_cap_watchlist()` and include it in `tool_input` when provided.

**Step 4: Verify**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_market_scan.py tests/test_agent_tools.py tests/test_agent_orchestrator.py -q
```

**Step 5: Commit**

```bash
git add services/small_cap_scanner_service.py agent_tools/tools.py agent_tools/definitions.py agent_orchestrator/trading_agent.py tests/test_small_cap_market_scan.py tests/test_agent_tools.py tests/test_agent_orchestrator.py
git commit -m "Thread scanner concurrency through agent surfaces"
```

---

### Task 3: Expose CLI worker controls

**Files:**
- Modify: `cli/scan_small_caps.py`
- Modify: `cli/run_agent.py`
- Test: `tests/test_small_cap_scanner.py`
- Test: `tests/test_agent_orchestrator.py`

**Step 1: Write failing tests**

In `tests/test_small_cap_scanner.py`, add a CLI test that monkeypatches
`SmallCapScannerService` and invokes:

```bash
--market us-listed --market-limit 25 --max-workers 6
```

Assert the fake service received `max_workers == 6`.

In `tests/test_agent_orchestrator.py::test_run_agent_cli_json_output`, invoke:

```bash
--market us-listed --market-limit 25 --max-workers 6 --json
```

and assert the fake orchestrator received `max_workers == 6`.

**Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py::test_scan_small_caps_cli_passes_max_workers tests/test_agent_orchestrator.py::test_run_agent_cli_json_output -q
```

Expected: CLI does not accept `--max-workers` or fake orchestrator assertion fails.

**Step 3: Implement CLI options**

- Add `max_workers: int | None = typer.Option(None, "--max-workers", help="Bounded worker count for broad market scans.")` to `cli.scan_small_caps.main()`.
- Pass `max_workers=max_workers` to `SmallCapScannerService().scan(...)`.
- Add the same option to `cli.run_agent.main()`.
- Pass it to `TradingAgentOrchestrator().run_sykes_small_cap_watchlist(...)`.

**Step 4: Verify**

Run:

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py tests/test_agent_orchestrator.py -q
```

**Step 5: Commit**

```bash
git add cli/scan_small_caps.py cli/run_agent.py tests/test_small_cap_scanner.py tests/test_agent_orchestrator.py
git commit -m "Expose scan worker controls in CLIs"
```

---

### Task 4: Docs and verification

**Files:**
- Modify: `README.md`
- Optional Modify: `docs/plans/2026-06-29-d3-live-scan-performance-design.md`

**Step 1: Update docs**

- Document `--max-workers` under the small-cap market scan example.
- State that bounded concurrency improves live market scans but does not change
  data quality labels, gap basis, or scanner guardrails.

**Step 2: Full verification**

Run:

```bash
scripts/verify.sh
```

Expected:

- pytest passes;
- Ruff passes;
- `git diff --check` passes.

**Step 3: Commit**

```bash
git add README.md docs/plans/2026-06-29-d3-live-scan-performance-design.md
git commit -m "Document live scan worker controls"
```

---

### Task 5: Stop and report

Report:

- branch name and commits;
- verification result;
- live scan command to test;
- that no market numbers were invented;
- whether `main` was pushed before D3 branch work.
