# Trader Profile: Default Momentum Gapper

> A generic, sensible momentum-gapper style used when no specific trader profile
> is named. Replace with a real distilled profile as you collect data. The
> Premarket Desk agent maps the rules below to `scan_premarket` filters; it still
> only reports tool-sourced numbers.

## Identity
- **Trader / source:** Generic default (not a specific person).
- **Status of notes:** mature enough to use as a baseline.
- **Markets / instruments:** US equities, premarket.
- **Session focus:** Premarket gappers with real participation (volume/RVOL).

## Core edge (one paragraph)
Trade names that are *gapping with conviction* — a meaningful overnight move
backed by above-average relative volume, not a thin drift. Direction-agnostic by
default (both gap-ups and gap-downs are setups), but quality is gated on RVOL and
clean data. Small caps get a higher ceiling because outsized RVOL there signals a
real catalyst; large caps need a cleaner, bigger gap to be interesting.

## Preferred setups
- **Small-cap momentum gapper** — `cap_tier: small`, `direction: up`,
  `min_gap_abs: 5`, `min_rel_volume: 3`, `min_volume: 1_000_000`.
  - Why it qualifies: real catalyst + crowd participation.
  - Disqualifiers: RVOL < 2 (no participation), thin volume, flagged data.
- **Large-cap gap** — `cap_tier: large`, `direction: both`, `min_gap_abs: 2`.
  - Why it qualifies: large caps rarely gap; 2%+ is a notable dislocation.
  - Disqualifiers: gap < 2%, stale/conflicting data.

## Scanner filter mapping (the literal default scan)
When the user just asks "what's worth watching premarket" with no extra detail,
run a broad pass and let grading sort it:

```
scan_premarket(
    all_universes = true,      # or a named universe/watchlist if given
    direction = "both",
    min_gap_abs = 2,
    min_rel_volume = 1.5,
)
```

Then deepen the top names with `get_ticker_snapshot` before grading.

## Grading rubric (A / B / C)
- **A:** Gap ≥ 5% (small cap) or ≥ 3% (large cap), RVOL ≥ 3, `confidence: OK`.
- **B:** Solid gap but RVOL 1.5–3, or exactly one data caveat (e.g. STALE).
- **C:** Marginal gap, RVOL < 1.5, thin volume, or `CONFLICT`/`MISSING` data.

## Avoid / red flags
- RVOL < 1.5 — the move has no participation behind it.
- `CONFLICT` or `STALE_DATA` confidence — don't trust the print.
- `MISSING_MARKET_CAP` when a cap filter matters — can't confirm the tier.
- Very low `volume` — illiquid, hard to trade cleanly.

## Notes & open questions
- This is a placeholder. Swap in float / short-interest / catalyst rules once
  those data tools exist and once you've distilled a specific trader's playbook.
