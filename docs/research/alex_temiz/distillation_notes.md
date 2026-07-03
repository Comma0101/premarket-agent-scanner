# Alex Temiz (MIC) Distillation Notes

## Scope

This document distills public Alex Temiz material into a non-impersonating educational lens. It does not claim endorsement, private access, or access to paid course content (My Investing Club / MIC).

## Source-Backed Principles

- **Process-Driven Execution.** Temiz emphasizes using a written "Perfect Trade Checklist." A trade must meet a set number of criteria (e.g., 8 out of 12) before entry to ensure high-probability setups. (`EV-AT-009`)
- **Strict Guardrails.** Treats risk management as the "holy grail." Advocates for mechanical "broker-level guardrails" and hard daily loss limits to prevent ego-driven trading and revenge trading. (`EV-AT-008`)
- **Scale Into Winners, Never Losers.** Start with a small position. Only scale up (add to the position) when the trade is working in your favor. Never average down a losing position. (`EV-AT-008`)
- **Equities day trader, not options.** Specializes in US small-cap equities. The current equity scanner is the right tool — no options data layer needed. (`EV-AT-006`)
- **VWAP is the primary indicator.** Uses VWAP (Volume Weighted Average Price) as the central chart reference for gauging market strength, institutional interest, and "money flow." Monitors if a stock bounces or fails at VWAP. (`EV-AT-007`)
- **Market Adaptability.** While best known for short-selling (First Red Day), he emphasizes pivoting to long-biased strategies when market conditions dictate (e.g., hot bull markets). (`EV-AT-010`)

## Candidate Setup Rules

### First Red Day (Primary Short Setup)

- Evidence: `EV-AT-002`, `EV-AT-003`, `EV-AT-004`, `EV-AT-005`
- **Scanner filters (underlying identification):**
  - Small-cap US equities.
  - Multi-day parabolic run-up (No fixed "magic number" of green days, but must be an extended, parabolic move).
  - Momentum exhaustion (stock is finally red on the day).
- **Entry triggers:**
  - Break down below the **previous day's close** or **previous day's low**. This move traps late-to-the-party buyers, forcing them to sell.
- **Stop / invalidation:**
  - Hard stop-loss set *before* entering the position. Position sizing is dictated entirely by the distance to the stop.
  - Stops are based on market structure (e.g., the day's high or a recent resistance level).
  - Thesis invalidation: If the stock reclaims the previous day's price level and shows strength, the setup is dead and the trade is exited.
- **Target / profit-taking:**
  - Scales out of the position ("covers into the panic") to lock in a realized P&L cushion.
  - No fixed target percentage; execution depends on the speed of the breakdown and momentum exhaustion.
- **Condition stacking:**
  - Multi-day parabolic run + trapped late buyers + break of prior close + failure at VWAP.
- **Current scanner mapping:**
  - Partially supported. We can scan for small-caps and current red days (price < prior close). We lack a multi-day run detector out of the box.
- Profile readiness: **underlying-watchlist with partial entry logic** (requires daily bar history for multi-day run detection).

## Rules Not Yet Supported By Data

- **Multi-day Run Detection** — The scanner needs to look back multiple days to identify the parabolic run-up required for a true "First Red Day."
- **VWAP** — Required for his primary indicator framework and assessing if the stock is failing at key intraday levels.
- **Intraday Highs/Lows** — Required for setting structured stop losses above the day's high or recent resistance.

## Red Flags

1. **Course Selling**: Primary current activity involves running a paid room (My Investing Club).
2. **Performance Verification**: While claims of $16M+ exist, they are primarily self-reported or verified via marketing materials/broker screenshots rather than comprehensive independent public audits like Darwinex.
3. **Verification Disputes**: Reddit and community discussions debate the value and legitimacy of the paid room, though the underlying strategies (like First Red Day) are standard prop-firm mechanics.

**Critical distinction**: These red flags concern claim verification and community drama, not method quality. The method content is grounded, highly risk-averse, relies on hard stops, and contains specific, scannable rules (break of prior close).

## Open Questions

- What specific VWAP bounce setups does he prioritize on the long side? Most public material heavily weights his short-selling, making it difficult to build a purely long-biased scanner profile.
- Are there specific RVOL requirements for his multi-day run-ups before they qualify for a First Red Day?

## Profile Readiness

Status: **underlying-watchlist with partial entry logic**

Rationale:
- The "First Red Day" strategy provides a concrete entry trigger (break below previous close or low) which is scannable with current data.
- However, the core setup requires a preceding multi-day parabolic run, which the current scanner cannot reliably detect without building a daily bar history component.
- Once daily bar history and VWAP are integrated, this profile becomes highly actionable and **agent-ready**.

## Comparison with Other Traders in This Project

| Dimension | Brando Le | Timothy Sykes | Lance Breitstein | Alex Temiz |
| --- | --- | --- | --- | --- |
| Mechanical rules in public sources | Zero | Multiple | Most | **Multiple** |
| Entry triggers | None stated | OTC breakout | Prior 2-min bar break | **Break of prior day close/low** |
| Stop loss | Rejected | Stated but vague | Hard rule: prior bar low/high | **Hard stop pre-entry (day's high)** |
| Target | None stated | Multi-day swing | 20-period MA | **Scales out on panic drops** |
| Instrument | Options | Small-cap equity | Equity shares | **Small-cap equity** |
| Data layer needed | Options chain | Current scanner | 2-min bars + VWAP | **Daily bar history + VWAP** |
| Profile readiness | profile-only | scanner-ready | agent-ready after bar data | **underlying-watchlist** |
