# Jack Kellogg Distillation Notes

## Scope

This document distills public Jack Kellogg material into a non-impersonating Kellogg-style educational lens. It outlines his core strategy rules, setups, and required indicators based on public information.

## Source-Backed Principles

- Emphasize the "Keep It Simple, Stupid" (KISS) principle, focusing on basic technical elements rather than complex indicators. (`EV-001`)
- VWAP is a primary sentiment and entry guide. Avoid chasing long positions above VWAP and short positions below VWAP. (`EV-002`, `EV-003`)
- Volume must surge to confirm momentum; high volume is a key requirement for valid breakouts or trends. (`EV-004`)
- Focus on low-float stocks and OTC breakouts for sharp price spikes driven by demand entering a constrained supply. (`EV-005`)
- Hot sectors and significant news catalysts are preferred to ensure the presence of momentum and liquidity. (`EV-006`)
- Price action is king. If price action invalidates the setup or thesis, exit immediately regardless of indicator readings. (`EV-007`)

## Candidate Setup Rules

### Low Float Momentum Breakout

- Evidence: `EV-004`, `EV-005`, `EV-006`
- Current scanner mapping: `cap_tier=small` (as a proxy), `direction=up`, `min_rel_volume=3.0`, surging volume.
- Unsupported but important: true float, OTC market classification, hot sector tagging, catalyst verification.
- Profile readiness: partial

### VWAP Mean Reversion / Pullback

- Evidence: `EV-002`, `EV-003`, `EV-004`
- Current scanner mapping: `direction=up`, `min_rel_volume=2.0`.
- Unsupported but important: exact VWAP value, percentage distance from VWAP, intraday support/resistance levels, linear regression lines.
- Profile readiness: not ready for automated profile rules (requires intraday data and VWAP distance calculation).

### OTC Breakout

- Evidence: `EV-005`
- Current scanner mapping: Not supported (current scanner assumes listed equities).
- Unsupported but important: OTC vs listed classification, historical resistance levels.
- Profile readiness: unsupported

## Risk And Psychology Rules

- Cut losses quickly and immediately when price action contradicts the initial thesis. (`EV-007`)
- Avoid "death by a thousand paper cuts" by not taking low-conviction trades and avoid holding losers too long. (`EV-007`)
- Do not chase extended stocks; entering above VWAP for a long or below VWAP for a short skews the risk/reward unfavorably. (`EV-002`, `EV-003`)
- Trade size should only increase with conviction and experience in a specific setup.

## Rules Not Yet Supported By Data

- The scanner needs to calculate the real-time distance between the current price and the VWAP to filter out overextended candidates. (`EV-002`, `EV-003`)
- True float and OTC classification are required to properly identify his preferred low-float OTC runners. (`EV-005`)
- Support/Resistance lines and Linear Regression, which are core to his strategy, require historical and intraday pattern state analysis not currently present in the premarket snapshot. (`EV-001`)
- Tagging stocks by "hot sector" requires industry grouping and momentum aggregation across the sector. (`EV-006`)

## Open Questions

- What specific percentage distance from VWAP constitutes "too extended" to chase a breakout?
- How should the scanner define "surging volume" operationally? (e.g., a specific RVOL threshold or a volume run-rate comparison).
- Can the scanner reliably integrate OTC market data, or should the lens be adapted purely for listed equities?
- What lookback period is appropriate for generating the Linear Regression channels?

## Profile Readiness

Status: partial

Rationale:
- The current scanner can filter for basic volume and gap criteria, which aligns with his momentum requirements. (`EV-004`)
- However, core mechanical rules regarding VWAP distance, Linear Regression, Support/Resistance, and OTC market classification are unsupported. (`EV-001`, `EV-002`, `EV-005`)
- The profile can be used for discovery (finding high volume small caps) but cannot automatically grade a Kellogg-style setup without VWAP distance and float data.
