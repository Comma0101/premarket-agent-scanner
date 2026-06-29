# D3 Live Scan Performance Design

## Goal

Make live whole-market small-cap scans operationally usable without changing the
scanner's data contract, grading rules, or market-data guardrails.

## Current Problem

`ScannerService.scan()` resolves a ticker list, then calls
`snapshot_service.build_snapshot()` one ticker at a time. A 75-symbol live scan
completed, but a 250-symbol live scan was too slow for desk use and had to be
stopped. The provider path itself works: `--market us-listed` resolved 5,212
common-stock-like symbols from Alpaca assets.

## Selected Approach

Add bounded concurrency at the scanner-service layer.

- Keep `SnapshotService` unchanged. It remains the only layer that combines
  provider data and assigns confidence.
- Add `max_workers` to `ScannerService.scan()`. The default is `1`, preserving
  existing serial behavior unless a caller opts in.
- Use `ThreadPoolExecutor` only when `max_workers > 1` and more than one ticker
  is selected.
- Keep result semantics unchanged: one bad ticker becomes a run note, successful
  results are sorted by absolute gap, and persistence remains best-effort.
- Thread safety is handled by the existing per-call SQLite connections in
  `_safe_insert_snapshot()`, `_learn_market_cap()`, and `_persist_run()`.

## Public Surface

- `SmallCapScannerService.scan(max_workers=...)`
- `agent_tools.scan_small_caps(max_workers=...)`
- `cli.scan_small_caps --max-workers`
- `cli.run_agent --max-workers`
- Orchestrator packets include `max_workers` in the tool input when provided.

The default CLI/orchestrator behavior should choose a modest live default for
market scans, while explicit ticker/watchlist scans can remain serial unless
the user opts in.

## Rejected Approaches

- Provider-specific batching: likely faster long term, but it would require
  changing yfinance/Alpaca provider contracts and carries more precision risk.
- Async rewrite: unnecessary for this repo right now and would touch too many
  layers.
- Full-market prefilter before quotes: useful later, but the scanner still needs
  a faster quote loop for any broad market run.

## Testing

Tests stay offline.

- Add a fake slow snapshot service and verify concurrent scans finish materially
  faster than serial scans.
- Verify per-ticker exceptions still become run notes and do not fail the scan.
- Verify `max_workers` flows through the small-cap tool, CLI, and orchestrator.
- Run `scripts/verify.sh` before merge/push.
