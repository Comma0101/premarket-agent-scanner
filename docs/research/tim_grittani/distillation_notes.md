# Tim Grittani Distillation Notes

## Scope

This document distills public Tim Grittani material into a non-impersonating
Grittani-style educational lens. It does not claim endorsement or private access.
The focus is on his data-driven, setup-specific mechanical trading rules as 
gathered from public interviews, courses, and educational material.

## Source-Backed Principles

- Base setups on data tracking. Treat trading as a statistical exercise managed via spreadsheet tracking, not emotional guessing. (`EV-001`)
- Master specific patterns (e.g., Gap and Crap, Morning Panic Dip Buy, Breakouts) rather than trading everything. (`EV-001`, `EV-007`)
- Use VWAP extensively for gauging trend, momentum exhaustion, and establishing support/resistance levels. (`EV-005`)
- Disregard company fundamentals ("Trade the Ticker"). Rely on price action, chart patterns, and technical execution. (`EV-007`)
- Require strict risk/reward ratios. Cut losses immediately when the thesis is invalidated (the "Golden Rule"). (`EV-006`)
- Never catch a falling knife. Wait for confirmation of a bounce or momentum shift before entry. (`EV-009`)

## Candidate Setup Rules

### Gap and Crap (Overextended Short)

- Evidence: `EV-002`, `EV-005`
- Current scanner mapping: `direction=up`, `gap_basis=premarket`, `min_gap_abs=10.0` (pragmatic)
- Unsupported but important: Multi-day chart extension, momentum exhaustion, distance from VWAP, intraday resistance.
- Profile readiness: partial for discovery; scanner identifies the gap, but not the multi-day extension or the exhaustion.

### Morning Panic Dip Buy

- Evidence: `EV-003`, `EV-009`
- Current scanner mapping: `direction=down`, `min_gap_abs=10.0` (pragmatic)
- Unsupported but important: Prior multi-day 50%+ run-up, panic velocity, real-time bounce confirmation, level 2 data.
- Profile readiness: not ready for automated confirmation, as the core requirement (prior run-up) is missing from current scanner logic.

### OTC Breakout

- Evidence: `EV-004`, `EV-010`
- Current scanner mapping: `direction=up`, `min_gap_abs=10.0` (pragmatic)
- Unsupported but important: Dollar volume > $1M+, OTC-specific liquidity filtering, multi-day resistance breakout level.
- Profile readiness: partial; requires a robust dollar-volume filter and confirmation of OTC data provider reliability.

## Risk And Psychology Rules

- The "Golden Rule" is paramount: cut losses quickly and unconditionally if the trade moves against the setup. (`EV-006`)
- Do not anticipate the bounce or the top; wait for confirmation from price action. (`EV-009`)
- Keep output framed as educational discovery. The scanner highlights a setup, but the trader must manage the execution and sizing. (`EV-006`)
- Do not let a scan result replace a pre-planned exit strategy and defined risk/reward ratio. (`EV-006`)

## Rules Not Yet Supported By Data

- The Morning Panic Dip Buy strictly requires a multi-day run-up prior to the panic. The scanner cannot currently detect the historical 50%+ move. (`EV-003`)
- Gap and Crap requires momentum exhaustion and multi-day overextension, which cannot be derived from a single day's gap and volume. (`EV-002`)
- VWAP relationships (distance from VWAP, VWAP trend) are needed for his specific entries and exits. (`EV-005`)
- Reliable OTC data (including accurate dollar volume) is required for the OTC Breakout setup. (`EV-004`, `EV-010`)
- Real-time confirmation of a bounce or momentum shift requires level 2 and tick-by-tick action. (`EV-009`)

## Open Questions

- What specific dollar-volume threshold should be hardcoded for Grittani-style OTC breakouts? (`EV-004`)
- How can the scanner be enhanced to query a 3-to-5 day lookback to validate the "multi-day run" requirement for the Morning Panic setup? (`EV-003`)
- How should VWAP exhaustion be quantified mechanically? (e.g., standard deviations from VWAP, specific reversal candlestick patterns). (`EV-005`)

## Profile Readiness

Status: partial

Rationale:

- The scanner can identify the initial conditions (large gaps, high volume), but Grittani's setups are highly dependent on multi-day context (prior runs, overextension) and intraday exhaustion signals. (`EV-002`, `EV-003`)
- Critical technical parameters like distance from VWAP and multi-day run percentages are missing. (`EV-005`)
- The dossier can serve as a discovery tool for Grittani-style setups, but cannot automatically confirm them without the missing data. (`EV-009`)
