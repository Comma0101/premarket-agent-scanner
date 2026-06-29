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
- Gap scanner service with market-cap, gap, direction, volume, and
  relative-volume (RVOL) filters, plus named cap tiers (nano/micro/small/mid/
  large/mega) for small-cap vs large-cap gapper scans.
- CLI: `list_universes`, `scan_premarket`, and `refresh_profiles`.
- Agent-callable JSON tool layer (`agent_tools`): `scan_premarket`,
  `list_universes`, and `get_ticker_snapshot`, with standard tool-use schemas
  and a dispatcher that can log to `agent_queries`.
- MCP server (`mcp_server`) exposing those tools over the Model Context Protocol
  for Claude Code / opencode / codex, plus a `premarket-desk` analyst persona and
  pluggable `trader_profiles/`.
- Test suite covering gap math, filtering, sorting, confidence labelling, the
  JSON tools, and the MCP transport (all offline).
- Default AI-related universes and personal watchlist example.

Pending:

- Wire FMP market caps into the scan by default.
- Snapshot history / staleness reporting commands.
- Paper watchlist + journaling tools for the desk agent (track flagged names
  through the session).
- Catalyst/news, float, and intraday-level data tools to deepen setup judgment.

## Agent Layer (MCP)

The scanner exposes its tools over the Model Context Protocol so any MCP-capable
agent — Claude Code, opencode, codex — can call them. There is no built-in LLM
loop and no API key is needed to serve the tools; the driving agent supplies the
model.

```bash
uv pip install -e ".[agent]"   # adds the `mcp` dependency
python -m mcp_server            # stdio MCP server exposing the scanner tools
```

`.mcp.json` registers the server for Claude Code automatically (it launches
`python -m mcp_server` on demand). For opencode/codex, point their MCP config at
the same command. The tools are:

- `scan_premarket` — gap scan over a universe/watchlist/tickers with filters.
- `list_universes` — list defined universes and watchlists.
- `get_ticker_snapshot` — full snapshot + computed gap for one ticker.

The agent never invents numbers — every price, gap, market cap, volume, and
confidence label comes from this tool layer, a thin wrapper over the scanner.
The tools are tested offline (`tests/test_agent_tools.py`,
`tests/test_mcp_server.py`).

### Desk persona and trader profiles

`.claude/agents/premarket-desk.md` is a ready-to-use trading-desk analyst persona
that drives these tools: it scans, ranks gappers into A/B/C setups, gates on the
data-confidence labels, and writes a morning brief — never inventing a number.
Its *style* is pluggable: it loads a trader profile from `trader_profiles/`
(`default.md` out of the box; copy `TEMPLATE.md` to distill a specific trader's
playbook into concrete scan filters and a grading rubric).

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

Gapper presets — small-cap and large-cap, with a relative-volume filter:

```bash
# Small-cap gappers up 5%+ on at least 2x average volume
python -m cli.scan_premarket --all --cap-tier small \
  --min-gap-abs 5 --direction up --min-rvol 2

# Large-cap gappers up 2%+
python -m cli.scan_premarket --all --cap-tier large \
  --min-gap-abs 2 --direction up
```

Cap tiers: `nano` (<$50M), `micro` ($50M-$300M), `small` ($300M-$2B),
`mid` ($2B-$10B), `large` ($10B-$200B), `mega` (>$200B). `--min-rvol` is
relative volume (current volume ÷ average daily volume) — a key gapper-quality
signal, especially for small caps. Small-cap scanning needs small-cap tickers in
a universe or watchlist; add them in `data/universes.yaml`.

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
