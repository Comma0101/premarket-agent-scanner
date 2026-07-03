# Nate Michaud Distillation Notes

## Scope

This document distills public Nate Michaud (Investors Underground) material into a non-impersonating Michaud-style educational lens. It does not claim endorsement or private access.

## Source-Backed Principles

- "Trade the ticker, not the company": prioritize price action, volume, and volatility over fundamental narratives. (`EV-003`)
- Strictly define risk based on technical chart levels before entering any trade. (`EV-005`)
- Use VWAP as a primary gauge for market sentiment and support/resistance ("VWAP Boulevard"). (`EV-004`)
- Focus on specific, high-probability patterns rather than trading random noise. (`EV-001`, `EV-002`)
- Monitor short interest and squeeze potential as key momentum drivers. (`EV-006`)

## Candidate Setup Rules

### ABCD Pattern Breakout

- Evidence: `EV-001`, `EV-005`
- Current scanner mapping: `direction=up`, `volume` thresholds
- Unsupported but important: Intraday pattern state (identifying Point A high, Point B low, Point C higher low), live intraday breakout alerts.
- Profile readiness: partial for identifying initial spikers, but unable to mechanically confirm the C-to-D breakout phase without intraday sequence data.

### Red-to-Green Momentum Shift

- Evidence: `EV-002`, `EV-005`
- Current scanner mapping: `previous_close`, `latest_price`, `direction=up`
- Unsupported but important: Intraday momentum tracking to alert *as* the stock approaches the previous close, rather than just snapshotting after it crosses.
- Profile readiness: high for basic crossing detection, partial for anticipating the move.

### VWAP Support/Squeeze

- Evidence: `EV-004`, `EV-006`
- Current scanner mapping: `basic VWAP`, `latest_price`
- Unsupported but important: Short interest data, borrow rates, and intraday consolidation detection along the VWAP line.
- Profile readiness: partial (can filter for price > VWAP, but lacks the short-squeeze context).
