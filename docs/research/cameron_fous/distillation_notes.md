# Cameron Fous Distillation Notes

## Scope

This document distills public Cameron Fous material (Fous4 system) into a non-impersonating Fous-style educational lens. It does not claim endorsement or private access.

## Source-Backed Principles

- The Fous4 system is a momentum-based strategy focused on identifying specific technical breakout patterns before they fully materialize. (`EV-001`)
- Risk management is mechanical: target a minimum 2:1 risk-to-reward ratio for every setup, defining entries and stops before execution. (`EV-002`)
- Technical indicators confirm price action; the 13-day EMA, RSI, and MACD are primary tools for verifying momentum. (`EV-003`, `EV-006`)
- The strategy covers both long breakouts (Fous4) and short breakdowns (Fous4x2), adapting to different market regimes. (`EV-004`)
- Emotional discipline and strict adherence to predefined mechanical rules are essential for long-term profitability. (`EV-002`)

## Candidate Setup Rules

### Fous4 Breakout Candidate

- Evidence: `EV-001`, `EV-003`, `EV-005`, `EV-006`
- Current scanner mapping: `direction=up`, `min_gap_abs=3.0`, `min_rel_volume=2.0`
- Unsupported but important: 13-day EMA, RSI, MACD, multi-day pattern classification (Force, Revival, Survival, Gold)
- Profile readiness: not ready for automated pattern recognition

### Fous4x2 Breakdown Candidate (Short)

- Evidence: `EV-004`
- Current scanner mapping: `direction=down`, `min_gap_abs=3.0`, `min_rel_volume=2.0`
- Unsupported but important: 13-day EMA (price below EMA), borrow availability, short interest, borrow cost
- Profile readiness: not ready

## Risk And Psychology Rules

- Do not enter a trade without a pre-calculated 2:1 profit-to-loss target. (`EV-002`)
- Entries, exits, and stops must be mechanical and set before the trade; emotional trading is discouraged. (`EV-002`)
- Technical indicators (13 EMA) must align with the price action to confirm the setup's validity. (`EV-003`)

## Rules Not Yet Supported By Data

- Identification of the four core breakout patterns (Force, Revival, Survival, Gold) requires multi-day chart structure parsing. (`EV-001`, `EV-005`)
- Strategy requires calculation of the 13-day EMA, RSI, and MACD for confirmation. (`EV-003`, `EV-006`)
- Fous4x2 short setups require hard-to-borrow status, borrow availability, and borrow fees. (`EV-004`)
- Executing the 2:1 risk/reward rule mechanically requires setting hypothetical entry, stop, and target levels, which the scanner does not calculate. (`EV-002`)

## Open Questions

- Can the scanner integrate a technical indicator service to pull the 13-day EMA, RSI, and MACD?
- How can we mechanically define and detect the "Force," "Revival," "Survival," and "Gold" multi-day patterns using available data?
- What source should be used for reliable short borrow availability for the Fous4x2 setups?

## Profile Readiness

Status: partial

Rationale:
- The scanner can discover basic momentum gappers and elevated RVOL, but lacks the specific chart pattern recognition and technical indicators (13 EMA) fundamental to the Fous4 strategy.
- Until indicator data and multi-day pattern analysis are integrated, the profile can only serve as a generic momentum screener rather than a true Fous4 lens.
