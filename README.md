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
- CLI, agent-callable JSON tool layer, and deterministic agent orchestrator.

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
- CLI: `list_universes`, `scan_premarket`, `refresh_profiles`, `scan_small_caps`,
  and `run_agent`.
- Agent-callable JSON tool layer (`agent_tools`): `scan_premarket`,
  `scan_small_caps`, `list_universes`, and `get_ticker_snapshot`, with standard
  tool-use schemas and a dispatcher that can log to `agent_queries`.
- MCP server (`mcp_server`) exposing those tools over the Model Context Protocol
  for Claude Code / opencode / codex, plus a `premarket-desk` analyst persona and
  pluggable `trader_profiles/`.
- Agent orchestrator (`agent_orchestrator`) that turns scanner output into a
  grounded Sykes-style small-cap watchlist packet for Codex, Claude, opencode,
  or another external driver.
- Test suite covering gap math, filtering, sorting, confidence labelling, the
  JSON tools, dispatcher behavior, and the MCP transport (all offline).
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
- `scan_small_caps` — Sykes-style small-cap watchlist scanner with evidence.
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

## Agent Orchestrator

The repo exposes JSON-safe tools in `agent_tools` for an external agent
(Codex, Claude, opencode, or another driver) to call directly. It also includes
a deterministic orchestrator in `agent_orchestrator` that calls those tools and
builds an agent handoff packet. The packet contains the tool call, watchlist
buckets, evidence summaries, missing-data warnings, safety guardrails, and a
handoff prompt. There is still no built-in LLM API client; the external agent
uses the packet.

Every price, gap, market cap, volume, and confidence label comes from the tool
layer, which is a thin wrapper over the scanner. The JSON tools work and are
tested without any LLM API key.

Run the Sykes-style small-cap watchlist orchestrator:

```bash
python -m cli.run_agent --tickers IONQ,SOUN --json
```

Run the same workflow against a filtered US-listed market universe:

```bash
python -m cli.run_agent --market us-listed --json
```

For a quick live smoke test, limit the number of market symbols:

```bash
python -m cli.run_agent --market us-listed --market-limit 25 --json
```

The default workflow is `sykes_small_cap_watchlist`. It does not impersonate
Timothy Sykes, does not place orders, and does not produce buy/sell advice. It
packages scanner evidence so the driving agent can communicate grounded
watchlist context.

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

## Small-Cap Discovery Scanner

`python -m cli.scan_small_caps` runs a listed small-cap discovery scan using
named presets such as `sykes_small_cap_v0`. The scanner ranks watchlist
candidates by gap, volume, RVOL, cap fit, and data confidence, while enriching
the output with evidence when available.

Evidence currently includes float and shares outstanding from profile
providers, exchange/listing context, recent SEC filing metadata, cached
catalyst/news records, and local former-runner history. Missing evidence is
still shown as unknown rather than inferred. Short-interest and borrow-cost
context remain unsupported in v1.

Example:

```bash
python -m cli.scan_small_caps --all --preset sykes_small_cap_v0
```

Whole-market mode:

```bash
python -m cli.scan_small_caps --market us-listed --preset sykes_small_cap_v0
```

Smoke-test mode:

```bash
python -m cli.scan_small_caps --market us-listed --market-limit 25
```

`--market us-listed` uses Alpaca's active US equity assets when Alpaca keys are
configured. Without Alpaca keys, it falls back to public Nasdaq Trader symbol
files and filters out ETFs, test issues, warrants, units, rights, preferreds,
funds, trusts, notes, and other non-common-stock-like symbols before applying
the small-cap scanner filters. Class-share and preferred-style symbols with
structural markers such as `.` or `$` are also filtered out because the current
quote path does not normalize them. Yahoo/yfinance remains the quote/profile
source; it is not used as the official market symbol master.

The output is watchlist context only, not buy/sell advice.

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

V1 supports selected universes/watchlists and the filtered `--market us-listed`
common-stock universe.

## Safety

This project does not provide buy/sell recommendations. Scanner output should be read as "matches your filter", not "you should buy".
