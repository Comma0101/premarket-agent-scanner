# Elite Options Trader Distillation Notes

## Scope

This document distills public EliteOptionsTrader / Elite Options Trader / Brando Le
material into a non-impersonating educational lens. It does not claim endorsement,
private access, or access to paid Discord alerts.

## Source-Backed Principles

- Treat this as an options/day-trading lens, not a small-cap equity lens. Whop,
  X, podcast, and video clips all point toward options, trade alerts, market
  commentary, and Discord community education. (`EV-EO-001`, `EV-EO-002`,
  `EV-EO-010`)
- Prefer simple price-action structure over indicator stacks: support/resistance,
  price action, relative strength, and patience are the public method terms most
  directly tied to process. (`EV-EO-003`)
- A valid output may be "no clean setup." Cash/no-trade discipline appears in
  multiple public posts and should be first-class rather than treated as a
  failure to find picks. (`EV-EO-004`, `EV-EO-005`)
- Favor selectivity and confluence. The source material repeatedly emphasizes
  waiting, patience, and avoiding low-quality trading environments. Whop reviews
  confirm this is central to the paid service as well. (`EV-EO-004`,
  `EV-EO-005`, `EV-EO-009`, `EV-EO-010`)
- Keep risk/reward and trade-plan fields unknown unless a source-backed entry,
  invalidation level, and target level are available. The public 3:1 concept is
  useful, but current scanner output cannot compute it honestly. (`EV-EO-006`)
- Treat 0DTE and illiquid options as high-risk contexts once the data layer can
  identify DTE and contract liquidity. (`EV-EO-008`)
- Use profit-taking, avoiding average-down behavior, and emotion control as
  educational risk framing only. Do not convert these into buy/sell/size
  instructions. "Never average down" is explicit and repeated. (`EV-EO-007`)
- Preserve the stop-loss conflict as a major caveat, not as an automation rule.
  The source's central claim is that removing stop losses was a "breakthrough"
  from 7-figure to 8-figure profitability (Words of Rizdom podcast, EO-024).
  This directly contradicts standard risk management. The repo's guardrails
  prohibit position sizing and advice, so no agent should tell the user to hold
  through losses or size a contract for zero. (`EV-EO-011`)
- Strategy alone is insufficient per the source. The "7 things I wish I knew"
  thread leads with "A strategy won't make you profitable" and the two-pillar
  model (charts + self-mastery) puts psychology on equal footing with technicals.
  A profile should encode this caveat: rules are necessary but not sufficient.
  (`EV-EO-009`, `EV-EO-017`)
- The primary underlying focus appears to be large-cap / mega-cap names (TSLA
  is the most-mentioned ticker), not small-cap or micro-cap equities. This
  profile is a poor fit for the current small-cap scanner lens. (`EV-EO-014`)
- All performance claims ($10M+, $340K in an hour, $400K/month, starting with $6K) are
  self-reported and not independently verified. The podcast adds: age 34, former
  painter, self-funded ("no outside funding no fake screenshots"). Do not use
  performance claims as evidence of method effectiveness. (`EV-EO-013`, `EV-EO-020`)
- Journaling/trade logging is stated as foundational in the podcast (timestamp
  00:58:24). This can be referenced in Desk output as a process recommendation
  but is not a scanner rule. (`EV-EO-019`)
- Momentum/breakouts are the only explicit setup-type language found across all
  public sources (podcast timestamp 01:19:16), but no mechanical detail (what
  constitutes a breakout, what timeframe, what confirmation) was provided. Too
  vague for automation. (`EV-EO-018`)
- A YouTube clip title "How to Spot Strong Stocks: Insider Tips" exists on the
  clips channel but its content was not extractable. This and "Waiting for the
  Market Bottom: Will It Happen?" are the only titled references to stock
  selection or market regime in any video source. No transcript content was
  obtainable.
- The daily "market summary" provided during the paid Discord session (confirmed
  by Whop reviews) is the source's primary mechanism for pointing traders at
  "relevant stocks" — but this is paid content and out of scope.
- Three podcast timestamp section titles exist without transcript content:
  "Managing Risk and Success in Trading" (00:08:36), "Strategies for Trading
  Momentum and Breakouts" (01:19:16), and "Navigating Market Volatility:
  Strategies and Insights" (01:10:52). These confirm the topics are discussed
  but no rules are extractable. (`EV-EO-018a`, `EV-EO-018b`)

## Candidate Setup Rules

### Large-Cap Options Momentum Watchlist

- Evidence: `EV-EO-002`, `EV-EO-003`, `EV-EO-005`, `EV-EO-014`
- Current scanner mapping: partial only. Use underlying equities, not option
  contracts, until options-chain data exists.
- Pragmatic underlying filters for a future profile draft:
  - liquid large-cap or mega-cap underlying (TSLA, NVDA, AAPL, AMZN, META, etc.)
  - meaningful intraday or premarket direction
  - relative strength versus SPY/QQQ/sector when available
  - near a known support/resistance breakout or reclaim level
- Unsupported but important: option contract bid/ask spread, volume, open
  interest, IV, Greeks, expiration, DTE, and contract-level liquidity.
- Profile readiness: partial for underlying discovery; not ready for contract
  scanning.

### No-Trade / Cash Discipline Filter

- Evidence: `EV-EO-004`, `EV-EO-005`
- Current scanner mapping: not directly supported.
- Future mapping:
  - if market direction is unclear, output "no clean setup"
  - if underlying is inside chop/range with no relative strength, downgrade
  - if spread/liquidity cannot be verified, leave contract readiness unknown
- Unsupported but important: market-regime classification, trend/chop detection,
  opening range state, and intraday volume profile.
- Profile readiness: conceptually ready; data layer missing.

### Risk/Reward Review

- Evidence: `EV-EO-006`, `EV-EO-007`, `EV-EO-008`, `EV-EO-011`
- Current scanner mapping: not supported.
- Future mapping:
  - require a planned invalidation level and target level before computing
    risk/reward
  - flag 0DTE as high-risk when expiration is same-day
  - flag options contracts with wide spreads or low open interest as low quality
  - never output position size, target advice, or order instructions
- Unsupported but important: entry, invalidation, target, contract premium,
  option-chain liquidity, and user/account context.
- Profile readiness: not ready for automation.

### Profit-Taking Psychology Gate

- Evidence: `EV-EO-009`
- Current scanner mapping: not applicable (this is output language, not a scan
  filter).
- Future mapping:
  - when a setup has significant unrealized gain, add a Desk note about the
    source's greed/profit-taking framing
  - do not generate a "take profit" instruction; present the observation
- Profile readiness: can be added to Desk output language immediately.

## Red Flags

1. **Stop-loss philosophy**: The source's most prominent claim is that removing
   stop losses was a "breakthrough." This is the opposite of standard
   risk-management advice and conflicts with the project's guardrails against
   sizing/advice. It must never be automated as a rule. Any profile that
   references this source must carry a prominent caveat. (`EV-EO-011`)

2. **Self-reported performance**: All financial claims ($10M+, $340K/hour,
   starting with $6K) are self-reported. No independent audit or broker
   statement has been found in public sources. (`EV-EO-013`)

3. **Forward-looking predictions**: Multiple X posts contain specific price
   predictions ("TSLA getting very close to a bottom," "If you're selling TSLA
   in the $350's, I bet you'll be buying it back again when it breaks $500").
   These are not method rules; they are directional bets. Do not convert into
   scanner signals. (`EV-EO-014`)

4. **Marketing vs. method**: The public X feed mixes educational principles
   (patience, no averaging down, support/resistance) with marketing content
   ($340K/hour, "living the dream," follower giveaways). The two must be kept
   separate. Educational principles can inform a lens; marketing claims cannot.

5. **Paid service funnel**: The free community and beginner guide are funnels to
   the $189/month paid Discord. The public material is deliberately incomplete
   as a method source; the richest detail is behind the paywall. This is an
   inherent ceiling on what a free-source distillation can capture.
6. **Intentionally anti-mechanical philosophy**: Unlike Sykes, who publishes
   detailed, repeatable rules publicly, Brando explicitly downplays mechanical
   setups ("most traders spend all their time looking for the perfect setup").
   The absence of rules is the source's stated philosophy, not a gap in our
   research.

## Rules Not Yet Supported By Data

- Option contract identity: OCC symbol, underlying, call/put, strike, expiration,
  DTE, multiplier.
- Contract quote quality: bid, ask, midpoint, last trade, quote timestamp,
  spread percent, trade condition, and quote source.
- Liquidity: contract volume, open interest, option chain rank, and whether
  spreads are tradeable.
- Volatility context: implied volatility, IV rank/percentile, Greeks, expected
  move, earnings/event IV crush risk.
- Underlying structure: support/resistance levels, prior highs/lows, trend state,
  opening range, VWAP, and relative strength versus SPY/QQQ/sector.
- Event context: earnings, major news, macro events, Fed/CPI dates, and market
  regime.
- Risk plan: entry, invalidation, target, max loss, and risk/reward. These must
  be explicit inputs or derived from source-backed levels, never invented.

## Open Questions

- Which free or paid provider should be the canonical options-chain source?
- Should the first implementation be an underlying-only watchlist lens using the
  current equity data layer, or should we wait until options-chain support exists?
- What public sources beyond X/Whop/Instagram/podcast can provide deeper method
  detail without using paid Discord content?
- How should the agent express "no clean setup" in Desk output and MCP packets?
- Should Elite Options live beside Sykes as a trader profile first, or should it
  wait until the data layer can support options-specific tools?
- Can the YouTube/TikTok video content (EO-025, EO-026, EO-027, EO-033) be
  manually reviewed and transcribed? These likely contain the richest publicly
  available method detail.
- The free Whop beginner guide (EO-029) may contain structured method content
  accessible with a free sign-up. Should we attempt to access it?

## Profile Readiness

Status: **profile-only**

Rationale:

- The identity and broad style are source-backed enough for a research dossier.
- The public material supports an educational lens around options, price action,
  relative strength, patience, cash discipline, and risk psychology.
- **After exhaustive NotebookLM extraction with a 42-question granular prompt
  targeting entry logic, setup criteria, underlying selection, exit/risk rules,
  contract selection, market regime filters, specific trade examples, and tools,
  the result is definitive: the public sources contain zero mechanical trading
  rules.** Every question about entries, exits, invalidation, contract selection,
  DTE, strikes, Greeks, IV, position sizing, profit-taking, time-of-day,
  confirmation, support/resistance identification, volume, timeframes, chart
  patterns, specific tickers, screening methods, and market-regime classification
  returned "information missing." The only responses were: (1) the no-stop-loss
  marketing claim, (2) a psychology-first philosophy ("focus on yourself"),
  (3) podcast timestamp section titles with no transcript content behind them,
  and (4) self-reported performance claims. (`EV-EO-021`)
- The source explicitly downplays mechanical rules: "most traders spend all
  their time looking for the perfect setup the perfect strategy and the perfect
  watch list the truth is you need to focus on yourself." This is not a
  temporary gap in our research — it is the source's stated philosophy.
- The current project is still equity-first and small-cap oriented. It cannot
  honestly scan option contracts, compute option liquidity, or evaluate risk/reward.
- The source's primary underlying focus (mega-cap names like TSLA) does not
  overlap well with the existing small-cap scanner.
- The stop-loss conflict is a significant red flag that must be preserved as a
  caveat in any profile, not automated.
- A production Elite Options-style agent should not be built until both
  options-chain data AND source-backed mechanical rules exist. Currently neither
  condition is met.
- An underlying-watchlist draft is still possible as a lightweight profile, but
  it should be clearly labeled as a psychology-first lens with no automated
  entry/exit/contract logic, not a scanner in the Sykes-style sense.
- The free Whop beginner guide (EO-029), if accessible, is the only remaining
  source that might contain structured method content. The YouTube/TikTok clips
  are unlikely to add mechanical rules given the philosophy-first pattern.
- **This profile is fundamentally different from the Sykes distillation**: Sykes
  has detailed, repeatable, mechanical rules in public sources. Brando's public
  material is intentionally anti-mechanical. Any profile must reflect this.
