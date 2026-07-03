# Ross Cameron Distillation Notes

## Scope

This document distills public Ross Cameron (Warrior Trading) material into a non-impersonating educational lens, focusing on mechanical rules for Gap and Go and Momentum Breakouts.

## Source-Backed Principles

- **Gap and Go**: Look for minimum 4% pre-market gap ups driven by a fundamental catalyst (news).
- **Momentum Breakout**: Focus on low float stocks with excessive volume (high RVOL) that are "in play".
- **Indicators**: VWAP is the primary "bread and butter" equilibrium point; 9 EMA and 20 EMA track intraday momentum.
- **Risk First**: Strict stop losses (e.g., low of the 1-minute candle), and simulator practice before real capital.

## Candidate Setup Rules

### Gap and Go Scanner Setup

- Evidence: `EV-101`, `EV-102`
- Current scanner mapping: `direction=up`, `min_gap_abs=4.0`, high volume.
- Unsupported but important: Catalyst confirmation, holding premarket highs, 1-min opening range breakout.
- Profile readiness: partial

### Momentum Breakout Setup

- Evidence: `EV-103`, `EV-104`
- Current scanner mapping: `cap_tier=micro` or `cap_tier=nano`, high `min_rel_volume`.
- Unsupported but important: True low float verification, Level 2 order book depth, flat top/bull flag intraday pattern recognition.
- Profile readiness: partial

### VWAP/EMA Confirmation

- Evidence: `EV-105`, `EV-106`
- Current scanner mapping: None currently.
- Unsupported but important: Intraday VWAP, 9 EMA, 20 EMA.
- Profile readiness: not ready

## Risk And Psychology Rules

- Do not chase if the stock is below VWAP or heavily selling off pre-market.
- Stop losses are often defined by immediate candle lows (e.g., 1-min ORB low).
- Emphasize strict risk management and cutting losses quickly.

## Rules Not Yet Supported By Data

- VWAP and EMA (9, 20) are strictly required but intraday indicator data isn't in the scanner yet.
- Level 2 depth for anticipating momentum shifts.
- Intraday pattern recognition (Bull flag, Flat top).
- True float values (market cap is only a proxy).

## Open Questions

- How to efficiently integrate intraday VWAP and EMAs into the pre-market/early session scan?
- Can we reliably proxy Level 2 depth with existing volume/spread metrics?
- What public sources can provide real-time true float and catalyst news verification?

## Profile Readiness

Status: partial

Rationale: Core filters (gap >= 4%, RVOL, direction=up) map well to existing scanner inputs. However, Ross Cameron's heavy reliance on intraday indicators (VWAP, 9/20 EMA) and Level 2 depth means the current scanner can only identify candidates, not confirm the actual entry setup.
