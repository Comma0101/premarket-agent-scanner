# Sykes Data-Layer Roadmap (acquire / derive, tiered)

## Frame

Goal: make the data layer rich enough that a single trader — **Timothy Sykes-style
small-cap** — can be expressed *faithfully*, citing real numbers for the signals that
define his edge. Sykes is the **forcing function**; the same data unlocks every
legendary trader after him, so each subsequent profile becomes ~a rubric file.

Prime directive holds throughout: every new field is sourced and cited, or surfaced
as **unknown**. New data feeds the existing `SmallCapEvidence` + grading on the
integrated base — not a parallel structure.

Key insight: **most Sykes signals are *derived*, not bought.** Three base inputs
(float, intraday bars, persisted daily history) unlock a long list of free
derivations. So the acquire list is short; the leverage is in deriving well.

Sequencing rule: each milestone is **its own branch off the integrated `main`**,
TDD + offline tests, exposed through evidence/tool output, gated by
confidence/unknown. Closes specific rows in
`docs/research/timothy_sykes/data_gap_report.md`.

---

## Dependency order (at a glance)

```
D1 Float ───────────────┐
                         ├─► float_rotation (derive)
D3 Daily history ──┐     │
                   ├─────┴─► former_runner, supernova, gap_fill, ATR, key levels (derive)
D4 Intraday bars ──┘         └─► VWAP, premarket H/L, opening range, session phase (derive)
D2 News/catalyst ──────────► catalyst quality/recency (derive)
Dilution-depth (extends existing live SEC filings)
D5 Paid tier (short interest / borrow / halts / L2)  ← optional, last
```

D1, D2, D3 are independent and can be built in any order; D4 wants D3's persistence
plumbing; D5 is optional/paid and comes last.

---

## D1 — Float & float rotation  🟢 cheap, highest single-filter leverage

- **Acquire:** free-float shares (and shares outstanding). Source: extend
  `providers/fmp_provider.py`; fall back to yfinance `floatShares`; Polygon if a
  paid key is present.
- **Derive (free):** `float_rotation = day_volume / float` ("trading multiples of
  its float = in play"); low-float tiering (e.g. <10M micro-float, <5M nano-float).
- **Surfaces in:** `SmallCapEvidence.float_shares`/`is_low_float` already exist —
  make the source reliable, add `float_rotation` to evidence + the grade
  (low float + high rotation should *raise* the read).
- **Closes data_gap rows:** float / low-float classification.
- **Grade impact:** turns "small cap" into "low-float, rotating" — a core Sykes tell.

## D2 — Catalyst / news  🟡 the trigger; biggest fidelity jump

- **Acquire:** PR-wire feeds first (free-ish): GlobeNewswire / Businesswire /
  Accesswire / PRNewswire RSS, plus SEC 8-K as a catalyst signal (we already pull
  filings). Optional paid upgrade: **Benzinga** (the desk-standard small-cap news API).
  New `providers/news_provider.py`; populate the `news`/catalyst cache the evidence
  service already reads (`get_cached_news`).
- **Derive:** catalyst **recency** (minutes since headline) and a coarse **quality
  class** — hard (FDA, contract, earnings, uplisting) vs soft (CEO letter,
  conference, "provides update"). Sykes weights hard catalysts heavily.
- **Closes data_gap rows:** catalyst/news quality. Removes the current cache **stub**.
- **Grade impact:** "no fresh catalyst" should cap the grade; a hard, fresh catalyst
  should lift it. This is the single largest step from "generic gapper" to "Sykes."

## D3 — Persisted daily history & its derivations  🟢 cheap, compounding

- **Acquire:** persist a daily OHLCV bar per tracked ticker (backfillable from
  yfinance for history; then append daily). New table + `services/history_service.py`.
- **Derive (free, high value):**
  - **former_runner** — has it spiked before (max prior gap/%/volume)? (replaces the
    `get_runner_history` **stub** with a real populator)
  - **supernova stage** — day 1/2/3+ of a multi-day parabolic run.
  - **gap-fill tendency** — does *this* name historically fade its gaps?
  - **ATR / typical range**, **52-wk range**, **distance from highs/lows**,
    **prior-day high/close** as key levels.
- **Closes data_gap rows:** former-runner history; multi-day pattern context.
- **Note:** start the daily append job early so live observations compound; daily
  history itself backfills, but our own scan observations do not.

## D4 — Intraday bars & session levels  🟠 limited free depth, paid for more

- **Acquire:** intraday 1–5m bars incl. premarket. Free: yfinance
  `history(prepost=True)` (1m ≈ 8 days, 5m ≈ 60 days). Depth/older: Alpaca SIP or
  Polygon (paid). New `providers/intraday_provider.py`.
- **Derive (free):** **VWAP**, **premarket high/low**, **opening range**, morning-panic
  / first green-or-red candle, and **session phase** (premarket / first-15 / midday /
  power hour) from the timestamp we already carry.
- **Closes data_gap rows:** intraday pattern state.
- **Grade impact:** lets the read reference *levels* ("reclaimed VWAP", "broke
  premarket high"), which is how Sykes actually frames entries.

## Cross-cutting — Dilution depth  🟡 extends what we already have live

- We already list SEC filings + keyword-tag risk. Deepen by **reading filing bodies**:
  active shelf (S-3) / ATM capacity, warrants/convertibles ("death-spiral"),
  "going concern" / cash runway, reverse-split history (yfinance splits).
- **Closes data_gap rows:** dilution / offering / financing risk.
- **Grade impact:** the key Sykes **short** context — overhead supply that caps pumps.

## Identity / red-flags  🟢 cheap, from profile

- OTC vs listed, **country (China shell-risk flag)**, sector/industry +
  **sympathy/peer mapping** (one runner flags its theme peers), SEC
  enforcement / trading-suspension list. Mostly profile-derived.

## D5 — Paid / hard tier  ⚪ optional, last

- **Short interest + days-to-cover** (FINRA free bi-monthly; Ortex/S3 paid fresh),
  **borrow availability / locate / fee**, **halt feed** (LUDP / news-pending),
  **L2 / bid-ask depth**. Squeeze fuel + shortability + thin-liquidity risk. Gate
  all of these behind explicit "paid feed configured" checks; degrade to *unknown*.

---

## Recommended build order

1. **D1 Float + rotation** — cheap, immediate grade upgrade, no paid dep.
2. **D2 Catalyst/news (PR-wire tier)** — biggest fidelity jump; paid Benzinga later.
3. **D3 Daily history + derivations** — start the append job; unlocks former-runner/supernova.
4. **D4 Intraday levels** — free tier first; paid depth only if needed.
5. **Dilution depth + identity flags** — fold in alongside as evidence enrichment.
6. **D5 paid tier** — only when a real edge needs it.

After D1–D3 land, write the real `trader_profiles/timothy_sykes.md`, validate it
grades the way Sykes would (low float + fresh hard catalyst + former runner + clean
first day), and use it as the **template** for the next legendary trader.
