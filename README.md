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

V1 data-layer functionality is implemented:

- Project structure and environment configuration.
- SQLite schema helpers and local API usage tracking.
- Data models and provider interfaces.
- Universe and watchlist YAML loader.
- yfinance, Alpaca Free, and FMP Free provider adapters.
- Asset/profile cache service with FMP-first and yfinance fallback behavior.
- Snapshot service with yfinance primary premarket pricing and Alpaca IEX validation.
- Gap calculation, filtering, session note, and confidence model.
- CLI commands for listing universes, refreshing profiles, and scanning gaps.
- Agent tool wrappers that return structured JSON.
- Unit tests for gap calculation, filters, confidence, and universe loading.

## Requirements

- Python 3.11 or newer.
- Optional API keys:
  - Alpaca Free API key and secret.
  - FMP Free API key.

The scanner should still run without Alpaca or FMP keys, but it will degrade to yfinance/cache-only behavior where possible.

## Setup

```bash
cd premarket-agent-scanner
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

## CLI Usage

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

## Agent Tools

The agent-callable functions live in `agent_tools/tools.py` and return dictionaries/lists rather than prose:

- `scan_premarket_gaps({...})`
- `explain_premarket_mover({...})`
- `compare_universe_gaps({...})`

Numeric values are passed through from provider/cache data. Missing values stay `null` in JSON-style outputs.

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
