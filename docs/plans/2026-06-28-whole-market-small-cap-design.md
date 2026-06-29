# Whole-Market Small-Cap Scanner Design

## Goal

Let the Sykes-style small-cap scanner start from a real US-listed market
universe instead of the repo's AI/large-cap universes.

## Source Choice

Use Alpaca's assets endpoint first when credentials are configured. Alpaca is
the cleanest built-in source for an active US equity asset master. If Alpaca is
not configured or fails, fall back to Nasdaq Trader's public symbol files:
`nasdaqlisted.txt` and `otherlisted.txt`.

Yahoo/yfinance remains useful for quotes and profiles after symbols are known,
but it is not treated as an official whole-market symbol master.

## Filter-Out Rules

Before the scanner fetches prices, the market universe removes symbols that are
not common-stock-like candidates:

- ETFs and exchange-traded products
- test issues
- warrants, rights, units, preferreds, depositary shares, notes, bonds
- funds, trusts, closed-end funds, indexes
- non-US equity asset classes
- inactive or explicitly non-tradable Alpaca assets
- unsupported exchange codes and obvious structural symbol suffixes
- class/preferred-style symbols containing structural markers such as `.` or `$`

The remaining symbols are passed into the existing `sykes_small_cap_v0` filters:
small-cap tiers, gap up, RVOL, volume, confidence, and evidence enrichment.

## CLI/API

Use `--market us-listed`:

```bash
python -m cli.scan_small_caps --market us-listed
python -m cli.run_agent --market us-listed --json
```

For live smoke tests, use `--market-limit N` to scan only the first `N` filtered
symbols. Omitting the limit scans the full filtered universe.

This is still a watchlist scanner, not an execution engine.
