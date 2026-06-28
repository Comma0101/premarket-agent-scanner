# Sykes-Style Small-Cap Scanner Design

## Objective

Build a small-cap scanner that is faithful to the public Timothy Sykes
distillation while staying honest about unsupported data. The scanner should
rank listed small-cap watchlist candidates using current market data, then
surface missing fields such as float, catalyst, filings, former-runner history,
and liquidity instead of inventing them.

This is not an auto-trader, not a buy/sell recommendation engine, and not an
impersonation or endorsement claim. It is a source-backed Sykes-style discovery
scanner for manual review.

## Evidence Basis

The scanner follows the existing research dossier and public official material:

- `docs/research/timothy_sykes/evidence_matrix.md`
- `docs/research/timothy_sykes/distillation_notes.md`
- `docs/research/timothy_sykes/data_gap_report.md`
- https://www.timothysykes.com/blog/how-to-use-stock-scanners/
- https://www.timothysykes.com/blog/low-float-stocks/
- https://www.timothysykes.com/blog/relative-volume/
- https://www.timothysykes.com/blog/stock-catalysts/
- https://www.timothysykes.com/blog/how-to-trade-in-premarket/

Key source-backed ideas:

- Scanners and watchlists are discovery tools, not trade instructions.
- Small and low-float names need extra risk handling.
- Volume and relative volume are participation signals.
- Catalyst/news context matters and must not be inferred from price alone.
- Former-runner and supernova labels need history/pattern context, not one
  snapshot.
- Premarket liquidity risk must be surfaced.

## Scope

V0 targets listed small-cap equities first. OTC/pink-sheet handling remains out
of scope until the data layer can identify and treat OTC liquidity/risk
separately.

Supported in V0:

- selected universe/watchlist/ticker input
- market-cap tier filtering for nano, micro, and small
- gap %, gap $, direction, volume, RVOL
- data-confidence gating
- candidate scoring and watchlist grade
- explicit missing-data flags for Sykes-relevant unknowns

Not supported in V0:

- true low-float confirmation
- catalyst/news quality verification
- SEC filing, dilution, offering, reverse split, or financing checks
- former-runner history
- supernova or multi-day pattern confirmation
- bid/ask spread, order book depth, halt status, or short/borrow context

## Architecture

Keep core scanner logic generic and add Sykes behavior through presets and
labels rather than hardcoding a trader name into business services.

Proposed files:

- `app/models.py`: add dataclasses for small-cap scanner configuration,
  candidate details, score breakdown, missing-field flags, and run output.
- `data/scanner_presets.yaml`: define `sykes_small_cap_v0` and any future
  scanner presets.
- `services/scanner_preset_service.py`: load and validate preset YAML.
- `services/small_cap_scanner_service.py`: orchestrate scans, apply scoring, and
  generate candidate grades.
- `agent_tools/tools.py`: expose `scan_small_caps`.
- `agent_tools/definitions.py`: add the `scan_small_caps` tool schema.
- `cli/scan_small_caps.py`: optional CLI entry point for local/manual use.
- `tests/test_small_cap_scanner.py`: offline tests for scoring, missing-data
  flags, confidence gates, and preset resolution.

The existing `ScannerService` remains the raw market-data scan layer. The new
small-cap scanner composes it rather than duplicating provider logic.

## Data Flow

1. User or agent calls `scan_small_caps` with a preset or explicit filters.
2. Preset service resolves `sykes_small_cap_v0` into raw scan filters.
3. `ScannerService` returns raw scan results using existing provider/data logic.
4. Small-cap scanner grades each result:
   - positive gap direction
   - cap tier/market-cap fit
   - volume and RVOL strength
   - data confidence
   - missing Sykes-relevant fields
5. Output returns ranked candidates with score breakdown, grade, risk notes, and
   explicit unknowns.

## Candidate Output

Each candidate should include:

- `ticker`
- `name`
- `market_cap`
- `gap_pct`
- `gap_dollar`
- `volume`
- `rel_volume`
- `confidence`
- `score`
- `grade`: `A_WATCH`, `B_WATCH`, `C_WATCH`, or `REJECT`
- `matched_signals`
- `missing_fields`: e.g. `float`, `catalyst`, `filings`, `former_runner`,
  `liquidity`, `short_interest`
- `risk_notes`
- `sources`
- `timestamp`

Grades are watchlist grades only. They must not imply a trade recommendation.

## V0 Preset

`sykes_small_cap_v0` should be conservative and transparent:

- cap tiers: nano, micro, small
- direction: up
- minimum gap: pragmatic default, likely 5%
- minimum RVOL: pragmatic default, likely 2x
- minimum volume: pragmatic default, likely 500k or 1M
- include low confidence: false by default
- require listed universe input or explicit tickers

Thresholds are pragmatic defaults, not claimed as Timothy Sykes's exact private
criteria.

## Scoring

Suggested scoring model:

- Gap strength: higher score for larger positive gap.
- RVOL strength: higher score for unusual participation.
- Volume floor: penalize thin names.
- Cap fit: prefer nano/micro/small and reject larger caps unless explicitly
  requested.
- Confidence: reject `ERROR`, `CONFLICT`, `STALE_DATA`, and missing price rows;
  heavily penalize `MISSING_MARKET_CAP`.
- Missing fields: do not reject solely for missing Sykes-style fields in V0, but
  surface them and cap the grade when critical fields are unknown.

Example grade logic:

- `A_WATCH`: strong gap, high RVOL, enough volume, clean confidence, small-cap fit.
- `B_WATCH`: good move but one weakness or important unknown.
- `C_WATCH`: marginal move or multiple caveats.
- `REJECT`: unusable confidence, wrong direction, too thin, no cap fit, or no
  computable gap.

## Error Handling

- Unknown preset returns a JSON error with valid preset names.
- Empty selection returns a structured empty result with notes.
- Provider failures remain row-level confidence/errors through `ScannerService`.
- Missing float/news/filing/history fields appear as unknowns, not fabricated
  values.
- If no candidates pass, output should say no matches and list active filters.

## Testing

Offline tests should cover:

- preset loading and validation
- cap-tier expansion across nano/micro/small
- candidate scoring and grade assignment
- confidence-gate rejection
- missing-field flags
- `scan_small_caps` JSON shape
- no unsupported fields are invented

The full existing scanner tests should remain unchanged and passing.

## Clean Repo Structure

Research stays in `docs/research/timothy_sykes/`.

Generic reusable scanner logic lives in `services/` and `app/models.py`.

Preset definitions live in `data/scanner_presets.yaml`.

Agent/tool exposure lives in `agent_tools/`.

Trader profile and Claude agent files should come after the scanner is stable:

- `trader_profiles/timothy_sykes.md`
- `.claude/agents/sykes-style-desk.md`

This sequencing prevents the repo from becoming persona-heavy before the data
surface is strong enough.
