# Steven Dux Distillation Notes

## Scope

This document distills public Steven Dux material into a non-impersonating
Dux-style educational lens. It does not claim endorsement or private access.

## Source-Backed Principles

- Build strategies on extensive historical data, tracking pattern win rates and risk/reward ratios before committing capital. (`EV-001`)
- Focus exclusively on small-cap stocks (under $300M-$500M) with high liquidity (e.g., >10M volume) to ensure capacity for short-selling. (`EV-005`, `EV-006`)
- Never anticipate or guess the top of a runner; always wait for price confirmation (e.g., failing at VWAP or breaking below the previous day's close). (`EV-009`)
- Observe volume near key resistance levels to identify distribution by large players. (`EV-007`)
- Strict risk management is the highest priority: limit risk to 1-2% of account per trade and cut losses instantly if the thesis is invalidated. (`EV-008`)

## Candidate Setup Rules

### Gap Up Short

- Evidence: `EV-002`, `EV-005`, `EV-006`
- Current scanner mapping: `cap_tier=small` (or micro), `direction=up`, `min_gap_abs=10.0` (pragmatic), `min_volume=10000000` (pragmatic/ideal)
- Unsupported but important: intraday price action confirming early failure, VWAP relationship, short borrow availability.
- Profile readiness: partial

### Bounce Short

- Evidence: `EV-003`, `EV-005`, `EV-006`, `EV-007`
- Current scanner mapping: `cap_tier=small`, `direction=down` (or faded from highs), high volume
- Unsupported but important: intraday bounce magnitude, exact VWAP level, failure confirmation at resistance.
- Profile readiness: not ready for automated execution, discovery only.

### First Red Day

- Evidence: `EV-004`, `EV-005`, `EV-006`
- Current scanner mapping: `direction=down` (for current session), high volume
- Unsupported but important: multi-day parabolic chart structure (e.g., 3+ consecutive green days prior), previous day close reference.
- Profile readiness: not ready for automated profile rules without multi-day historical data.

## Risk And Psychology Rules

- Limit max risk per trade to 1-2% of account equity. (`EV-008`)
- Avoid crowded or "trapped" trades by confirming liquidity and reading Level 2 data. (`EV-006`, `EV-009`)
- Suppress emotion and avoid looking at PnL during the trade; execute the plan based strictly on the chart. (`EV-008`)
- Do not trade if the exact criteria for a historical high-probability setup are not met. (`EV-001`)

## Rules Not Yet Supported By Data

- Multi-day chart structure and parabolic run context are required for First Red Day setups. (`EV-004`)
- Intraday VWAP, support/resistance levels, and Level 2 depth are necessary for Bounce Short and Gap Up Short confirmation. (`EV-002`, `EV-003`, `EV-007`, `EV-009`)
- Historical pattern statistical tracking (win rate, average profit/risk) is fundamentally missing from a real-time scanner. (`EV-001`)
- Short locate/borrow availability and cost, which are crucial for executing these setups. (Implied for short strategies)

## Open Questions

- How can we reliably define and scan for a "multi-day parabolic run" using daily historical data to trigger First Red Day alerts? (`EV-004`)
- What is the best way to incorporate real-time VWAP and key support/resistance levels into the scanner to validate Gap Up Shorts and Bounce Shorts? (`EV-002`, `EV-003`)
- Can we build a statistical tracking module that records setup occurrences and outcomes to replicate Dux's data-driven edge? (`EV-001`)

## Profile Readiness

Status: partial

Rationale:

- The scanner can discover small-cap, highly liquid, gap-up or gap-down candidates, which satisfies the initial filtering criteria for Dux-style setups. (`EV-002`, `EV-005`, `EV-006`)
- However, the core of the strategy relies on precise intraday execution (VWAP, resistance, confirmation) and multi-day context (parabolic runs), which the current snapshot scanner does not support natively. (`EV-003`, `EV-004`, `EV-007`, `EV-009`)
- Additionally, short selling requires locate and borrow data, which is currently absent.
