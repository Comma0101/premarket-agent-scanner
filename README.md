# Premarket Agent Scanner

Personal-use premarket gap scanner and market data layer for selected stock universes.

This project is designed to answer questions like:

- Show premarket gap ups over 5% with market cap above $10B.
- Which AI infrastructure names are gapping down this morning?
- Among my watchlist, which large caps are moving premarket?
- Which names have low-confidence data?

The scanner is a data/query layer first. It is not an auto-trading system and does not place broker orders.

## V1 Scope

- Local SQLite database.
- Static YAML universes and watchlists.
- Free data-source adapters for yfinance, Alpaca Free, and FMP Free.
- Market-cap and company-profile caching.
- Premarket gap calculation.
- Data-confidence labels for missing, stale, low-confidence, and conflicting data.
- CLI and agent-callable JSON tool layer.

## Current Status

A working end-to-end premarket scan is in place (yfinance-only path, no API
keys required). `python -m cli.scan_premarket` resolves a selection, builds a
snapshot per ticker, computes the gap, applies filters, persists the run, and
renders a table.

Implemented:

- Project structure and packaging (installable with `pip install -e ".[dev]"`).
- Environment configuration.
- SQLite schema helpers.
- Data models and provider interfaces.
- Universe and watchlist YAML loader.
- yfinance, Alpaca, and FMP provider adapters.
- Snapshot service combining providers into a single snapshot, with optional
  Alpaca cross-validation that flags CONFLICT when sources disagree (auto-enabled
  when Alpaca keys are present; yfinance-only otherwise).
- Confidence model (OK, LOW_CONFIDENCE, CONFLICT, STALE_DATA, MISSING_*, ERROR).
- Gap scanner service with market-cap / gap / direction filters and persistence.
- CLI: `list_universes`, `scan_premarket`, and `ask` (natural-language).
- Agent-callable JSON tool layer (`agent_tools`): `scan_premarket`,
  `list_universes`, and `get_ticker_snapshot`, with Anthropic tool-use schemas,
  a dispatcher that logs to `agent_queries`, and a Claude agent loop.
- Test suite covering gap math, filtering, sorting, confidence labelling, the
  JSON tools, and the agent tool-use loop (all offline).
- Default AI-related universes and personal watchlist example.

Pending:

- Wire FMP market caps into the scan by default.
- `refresh_profiles` CLI for proactive profile/market-cap caching.
- Snapshot history / staleness reporting commands.

## Agent Layer

Ask the scanner in plain English (requires the Anthropic SDK and an API key):

```bash
pip install -e ".[agent]"
export ANTHROPIC_API_KEY=...   # add when ready
python -m cli.ask "Which MAG7 names are gapping up over 1% premarket?"
```

The agent never invents numbers — every price, gap, market cap, and confidence
label comes from the tool layer, which is a thin wrapper over the scanner. The
JSON tools work and are tested without any API key; only the conversational
`ask` command needs one.

Note: Yahoo Finance must be reachable for the yfinance path. Some sandboxed or
policy-restricted networks block it; run locally for live premarket data.

## Requirements

- Python 3.11 or newer.
- Optional API keys:
  - Alpaca Free API key and secret.
  - FMP Free API key.

The scanner should still run without Alpaca or FMP keys, but it will degrade to yfinance/cache-only behavior where possible.

## Setup

```bash
cd /Users/kuma./Workspace/premarket-agent-scanner
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Then add API keys to `.env` if available:

```bash
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
FMP_API_KEY=
DATABASE_URL=sqlite:///data/market_data.sqlite
DEFAULT_TIMEZONE=America/New_York
```

## Planned CLI Usage

Refresh company profiles:

```bash
python -m cli.refresh_profiles --universe AI_WAVE_3_EQUIPMENT
```

Run scanner:

```bash
python -m cli.scan_premarket \
  --universe AI_WAVE_3_EQUIPMENT \
  --min-market-cap 10000000000 \
  --min-gap-abs 3 \
  --direction both
```

List universes:

```bash
python -m cli.list_universes
```

## Data Sources

This project uses free sources with clear limitations:

- yfinance: personal/research-grade quote and profile fallback.
- Alpaca Free: IEX-only structured validation, not full-market SIP data.
- FMP Free: company profile and market cap, with daily request limits.

The agent layer must not invent numbers. Prices, market caps, gaps, volume, and confidence labels must come from the data layer.

## Database

Default SQLite path:

```text
data/market_data.sqlite
```

The database is ignored by git so local market data stays local.

## Universes

Default universe definitions live in:

```text
data/universes.yaml
```

User watchlists live in:

```text
data/watchlists.yaml
```

V1 intentionally scans selected universes only. It does not attempt a full-market scan.

## Safety

This project does not provide buy/sell recommendations. Scanner output should be read as "matches your filter", not "you should buy".
