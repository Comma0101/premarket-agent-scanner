# Timothy Sykes Distillation Notes

## Scope

This document distills public Timothy Sykes material into a non-impersonating
Sykes-style educational lens. It does not claim endorsement or private access.

## Source-Backed Principles

- Use scanners and watchlists as discovery tools for manual review, not as automatic buy or sell instructions. (`EV-015`, `EV-019`)
- Start premarket review with meaningful direction, gap size, volume, relative volume, and company-size context. (`EV-001`, `EV-004`, `EV-005`)
- Treat premarket spikes as watchlist candidates only; a spike alone is not enough without preparation, timing, and liquidity checks. (`EV-002`, `EV-003`, `EV-024`)
- Prefer small, volatile candidates only when participation is visible, while treating market cap as an imperfect proxy for float. (`EV-004`, `EV-006`, `EV-022`)
- Require verifiable catalyst or news context before elevating a breaking-news-style mover; missing catalyst data stays unknown. (`EV-008`, `EV-009`, `EV-020`)
- Handle former runners and pre-spike ideas as data-dependent watchlist themes, not facts inferred from the current move alone. (`EV-010`, `EV-011`, `EV-014`)
- Reserve supernova or extreme-momentum labels for candidates with multi-day pattern context, not a single premarket gap. (`EV-012`, `EV-013`)
- Keep the lens educational, disciplined, and risk-first; scanner output is not a prediction or endorsement. (`EV-016`, `EV-017`, `EV-018`, `EV-019`)

## Candidate Setup Rules

### Small-Cap Premarket Gapper

- Evidence: `EV-001`, `EV-004`, `EV-006`, `EV-022`
- Current scanner mapping: `cap_tier=small`, `direction=up`, `min_gap_abs=5.0` (pragmatic, not source-explicit), `min_rel_volume=2.0` (pragmatic, not source-explicit)
- Unsupported but important: float/free float, catalyst/news quality, dilution/offering risk, bid/ask spread
- Profile readiness: partial

### High-RVOL Premarket Spiker

- Evidence: `EV-003`, `EV-004`, `EV-005`, `EV-021`
- Current scanner mapping: `direction=up`, `min_gap_abs=3.0` (pragmatic, not source-explicit), `min_rel_volume=3.0` (pragmatic, not source-explicit)
- Unsupported but important: spread, order book depth, trade count, float-adjusted turnover, intraday pattern state
- Profile readiness: partial

### Catalyst-Review Premarket Mover

- Evidence: `EV-008`, `EV-009`, `EV-020`, `EV-023`
- Current scanner mapping: `direction=up`, `min_gap_abs=5.0` (pragmatic, not source-explicit), `min_rel_volume=2.0` (pragmatic, not source-explicit), `only_confident=true`
- Unsupported but important: catalyst/news text, headline timestamp, source credibility, SEC filing link, dilution/offering risk
- Profile readiness: partial for discovery; not ready for automated catalyst confirmation

### Former Runner Reactivation Watchlist

- Evidence: `EV-010`, `EV-011`, `EV-014`
- Current scanner mapping: `watchlist=manual_former_runners`, `direction=up`, `min_gap_abs=5.0` (pragmatic, not source-explicit), `min_rel_volume=2.0` (pragmatic, not source-explicit)
- Unsupported but important: former-runner history, prior spike dates, prior catalyst history, prior volume spike
- Profile readiness: partial only when the universe is manually curated

### Extreme Momentum Watchlist Candidate

- Evidence: `EV-012`, `EV-013`, `EV-024`
- Current scanner mapping: `direction=up`, `min_gap_abs=10.0` (pragmatic, not source-explicit), `min_rel_volume=3.0` (pragmatic, not source-explicit), run separately across `cap_tier=nano`, `cap_tier=micro`, and `cap_tier=small`
- Unsupported but important: multi-day pattern state, intraday chart structure, float, short-interest context, session liquidity profile
- Profile readiness: not ready for automated profile rules

## Risk And Psychology Rules

- Do not present a setup as tradeable when confidence is `CONFLICT`, `STALE_DATA`, `ERROR`, or when required scanner fields are missing. (`EV-015`, `EV-019`)
- Treat unsupported catalyst, float, former-runner, and dilution assumptions as unknown, not inferred from price or volume. (`EV-009`, `EV-011`, `EV-022`, `EV-023`)
- Discount large premarket gaps when liquidity quality is unknown, especially if spread, order book depth, or halt status is unavailable. (`EV-002`, `EV-021`, `EV-024`)
- Require volume or relative-volume confirmation before treating a price move as a serious watchlist candidate. (`EV-001`, `EV-004`, `EV-005`)
- Keep all output framed as educational watchlist context, not a guarantee, recommendation, endorsement, or claim of private access. (`EV-015`, `EV-019`)
- Do not let a strong scan result replace downside planning, position sizing, or an exit plan before any manual trade decision. (`EV-016`, `EV-017`)
- Avoid chasing weak or incomplete signals; patience, discipline, and rule-following are part of the evidence-backed lens. (`EV-018`, `EV-019`)
- Treat low-float or small-cap candidates as higher-risk until strict risk controls and missing data are addressed. (`EV-007`, `EV-016`, `EV-017`)

## Rules Not Yet Supported By Data

- True float, free float, recent share issuance, and insider ownership are required before calling a candidate low-float or supply-constrained. (`EV-006`, `EV-022`)
- Catalyst quality, news freshness, headline source, and filing links must be sourced directly before a catalyst-driven label can be trusted. (`EV-008`, `EV-009`, `EV-020`)
- Dilution, offering, reverse-split, and financing-risk checks require filing history that the current scanner does not verify. (`EV-007`, `EV-023`)
- Former-runner status needs prior spike dates, prior percent moves, prior volume spikes, and prior catalyst history. (`EV-010`, `EV-011`)
- Supernova or extreme-momentum classification needs multi-day pattern state and company-context comparison beyond a single scan row. (`EV-012`, `EV-013`)
- Premarket liquidity quality needs spread, order book depth, trade count, halt status, and session-timing data. (`EV-002`, `EV-021`, `EV-024`)
- Execution readiness needs entry, stop, position size, liquidity-at-exit, and account-risk data that belongs outside the scanner. (`EV-016`, `EV-017`)

## Open Questions

- What public-source numeric thresholds, if any, should replace the pragmatic `min_gap_abs` and `min_rel_volume` values used above? (`EV-001`, `EV-004`, `EV-005`)
- Which free/public sources can provide reliable catalyst text, timestamps, source credibility, and filing links for scanner use? (`EV-008`, `EV-009`, `EV-020`, `EV-023`)
- What public float or free-float source is reliable enough to avoid using market cap as a proxy? (`EV-006`, `EV-022`)
- How should former-runner history be defined operationally: lookback window, prior percent move, prior volume spike, and required catalyst context? (`EV-010`, `EV-011`, `EV-014`)
- What multi-day features should distinguish an extreme-momentum candidate from an ordinary premarket gapper? (`EV-012`, `EV-013`)
- Which liquidity gates should be mandatory before a premarket candidate can move beyond watchlist status? (`EV-002`, `EV-021`, `EV-024`)
