# Alex Temiz (MIC) — Agent C Research Instructions

You are building a source-backed trader distillation for Alex Temiz (My Investing
Club / MIC). Follow the exact format of `docs/research/lance_breitstein/`. Do NOT
touch any Python code. Output goes in `docs/research/alex_temiz/` only.

---

## Who Is Alex Temiz

- Full name: Alex Temiz
- Known for: My Investing Club (MIC), $16M+ in verified profits (per his claims)
- Primary instrument: US equities, small-cap day trading, short-selling
- X/Twitter: search for @AlexTemizMIC or similar handles
- YouTube: Chart Fanatics interviews, own channel content
- Podcasts: Chat With Traders, Humbled Traders, Words of Rizdom
- Key concept: "First Red Day" strategy
- Course/community: My Investing Club (MIC) — paid, out of scope for content

---

## Step 1: Find All Public Sources

Search for and catalog every free/public source. Use these search strategies:

### Primary sources to find:
1. **X/Twitter profile** — handle, bio, key posts with method rules
2. **YouTube interviews** — search "Alex Temiz" on YouTube. Known appearances:
   - Chart Fanatics / Words of Rizdom (he appeared in the "$16+ Million Trader vs
     15 Losing Traders" episode)
   - Chat With Traders podcast
   - Humbled Trader podcast
   - Any standalone strategy breakdown videos
3. **TradeZella strategy pages** — search
   `https://www.tradezella.com/strategies/` for any Temiz-authored pages
4. **Podcast episodes** — Spotify, Apple Podcasts, search "Alex Temiz"
5. **Articles/interviews** — blog posts, written interviews
6. **Instagram, TikTok** — short-form content with strategy clips
7. **Reddit** — r/Daytrading discussions about MIC/Temiz (for verification debate)

### For each source, record in source_inventory.md:
| ID | Source | Type | URL | Published / Updated | Accessed | Why It Matters |

Use IDs like `AT-001`, `AT-002`, etc.

---

## Step 2: Extract Method Detail

After finding sources, use NotebookLM or manual review to extract answers to
these specific questions. Record answers as evidence in evidence_matrix.md.

### A. Identity & Verification
- Real name, location, years trading
- Prop firm affiliation (if any)
- Performance claims ($16M+, verified how?)
- Is there independent audit? Broker statements? Kinfo? Profit.ly?
- Any claim inflation over time?
- Course selling? MIC membership price?
- Any controversy or community disputes?

### B. Markets / Instruments
- Equities only? Options? Futures?
- Small-cap vs large-cap?
- Direction: long, short, or both?
- Day trades only or swing trades too?
- Any mention of 0DTE, indexes, crypto?

### C. The "First Red Day" Setup (PRIMARY)
This is his most well-known strategy. Extract EVERY mechanical detail:

1. **What qualifies as a "First Red Day"?** Define precisely:
   - How many prior green/up days are required? (minimum streak length)
   - What constitutes a "red day"? (close below prior close? below open? below
     prior day low? gap down?)
   - Does the prior run need to be parabolic? How is that defined? (e.g., X%
     over Y days)
   - Must the stock have been a "runner" or "former runner"?

2. **Entry trigger:**
   - Does he enter on the red day itself, or wait for confirmation the next day?
   - Does he short the breakdown of a specific level? (prior day close? prior day
     low? VWAP? opening range low?)
   - Does he wait for the first pullback/rip on the red day, or enter immediately?
   - Any time-of-day preference for entry? (open, midday, close?)
   - Does he use limit orders or market orders?
   - Does he scale in or go all at once?

3. **Stop / invalidation:**
   - Where is the hard stop? (prior day high? VWAP? opening range high? HOD?)
   - Does he always use a hard stop?
   - Does he ever average down into a short?
   - What invalidates the thesis entirely?

4. **Target / profit-taking:**
   - Does he have a fixed target? (e.g., "scale out at VWAP, rest to previous
     day low")
   - Does he trail a stop? How?
   - Does he partial out? In what increments?
   - Does he let runners run or take full profit at a target?

5. **Conditions that strengthen the setup:**
   - High RVOL on the red day?
   - Gap down on the red day?
   - Stock closing weak (near lows) on the red day?
   - Failed VWAP reclaim on the red day?
   - Sector weakness?
   - Low float? High short interest?
   - News catalyst type (dilution, offering, downgrade vs. just profit-taking)?

### D. Other Setups (if discussed publicly)
6. **VWAP bounce/setup** — does he have a specific VWAP long or short setup?
   What are the exact conditions?
7. **VWAP rejection/short** — shorting stocks that fail at VWAP?
8. **Morning panic / bounce** — buying the first panic dip?
9. **Overextension / parabolic short** — shorting stocks that are extended far
   beyond VWAP?
10. **Continuation plays** — buying or shorting follow-through after a big move?

### E. Screening / Underlying Selection
11. How does he find candidates? Scanner settings? What does he scan for?
12. Does he watch the same tickers daily or screen fresh each morning?
13. Does he trade earnings plays?
14. Does he prefer low float or high float?
15. Does he filter by price level? (e.g., stocks under $20?)
16. Does he look at sector/industry?

### F. VWAP Usage
17. How exactly does he use VWAP? Is it a filter, an entry trigger, a target,
    or all three?
18. Does he have a "never long below VWAP" rule like Breitstein?
19. Does he use VWAP for stop placement?
20. Does he use anchored VWAP or session VWAP?

### G. Psychology / Rules
21. Daily loss limit? Max trades per day?
22. Walk-away rules after X consecutive losses?
23. Position sizing rules? (fixed dollar risk? % of account?)
24. Rules about revenge trading, overtrading, FOMO?
25. Does he grade his trades? Journal? Daily report card?
26. Any specific "golden rules" stated?

### H. Tools
27. What broker does he use?
28. What charting platform?
29. What scanner/screener?
30. What journaling tool? (TradeZella?)
31. Does he use Level 2, DOM, or time & sales?

### I. Specific Trade Examples
32. Does he walk through any specific trade start-to-finish? If so, capture:
    ticker, what he saw, why he entered, where he entered, where he stopped,
    where he took profit.

---

## Step 3: Build Evidence Matrix

For each extractable observation, create a row in evidence_matrix.md:

| ID | Sources | Theme | Source-Backed Observation | Confidence | Current Scanner Fields | Missing Fields / Data Needs | Implementation Note |

Use IDs like `EV-AT-001`, `EV-AT-002`, etc.

Confidence levels:
- **high** — repeated across multiple sources, or stated as a hard rule
- **medium** — mentioned once clearly
- **low** — vague, implied, or contradicted across sources

---

## Step 4: Write Distillation Notes

Follow the exact structure of `lance_breitstein/distillation_notes.md`:

1. **Scope** — non-impersonating educational lens, no paid MIC content
2. **Source-Backed Principles** — each principle tagged with evidence IDs
3. **Candidate Setup Rules** — for each setup:
   - Evidence IDs
   - Scanner filters (underlying identification)
   - Entry triggers
   - Confirmation required
   - Stop / invalidation
   - Target / profit-taking
   - Condition stacking
   - Current scanner mapping
   - Profile readiness
4. **Rules Not Yet Supported By Data**
5. **Red Flags** — verification gaps, claim inflation, course selling, controversy
6. **Open Questions**
7. **Profile Readiness** — one of:
   - profile-only (like Brando Le — no mechanical rules)
   - underlying-watchlist (can surface candidates but no entry signals)
   - underlying-watchlist with partial entry logic (like Breitstein Phase 1)
   - agent-ready (like Breitstein after bar data)

---

## Step 5: Write Data Gap Report

Follow the exact structure of `lance_breitstein/data_gap_report.md`:

1. **Current Repo Fit** — what can the existing scanner do for this profile?
2. **Required Data Before Production Scanner** — table with need, why, status,
   candidate sources, blocks profile?
3. **Structural Mismatches** — if any
4. **Guardrail Requirements**
5. **Recommended Next Build Step**
6. **Highest-Priority NotebookLM Extractions** — list specific video/podcast URLs
   with priority and why

---

## Step 6: Compare with Existing Profiles

At the end of distillation_notes.md, add a comparison table:

| Dimension | Brando Le | Timothy Sykes | Lance Breitstein | Alex Temiz |
|---|---|---|---|---|
| Mechanical rules in public sources | | | | |
| Entry triggers | | | | |
| Stop loss | | | | |
| Target | | | | |
| Instrument | | | | |
| Data layer needed | | | | |
| Profile readiness | | | | |

---

## Critical Rules

1. **Never invent a number.** Every price, gap, RVOL, win rate, float, market
   cap must come from a tool result or source. If you don't have it, say
   **unknown**.
2. **Use only public/free material.** No paid MIC Discord, no private member
   content, no leaked material.
3. **Separate marketing claims from method evidence.** "$16M+ in verified
   profits" is a marketing claim unless you find independent audit.
4. **Treat all performance claims as self-reported** unless independently
   verified.
5. **Yes, note controversy.** If Reddit or other sources question his
   verification or MIC's value, document it in Red Flags. Same treatment as
   Breitstein's claim inflation.
6. **Focus on mechanical rules.** The whole point is to find scannable,
   concrete, repeatable rules. Philosophy is secondary. If a rule can be
   expressed as a filter condition, entry trigger, or stop level, that's
   valuable. If it's just "be disciplined," note it in psychology but don't
   treat it as scannable.
7. **The "First Red Day" is the priority.** If you find detailed mechanical
   rules for this setup, this profile may be more agent-ready than Breitstein
   (since it works on daily data, not 2-min bars).

---

## Deliverables

Create these 4 files:
- `docs/research/alex_temiz/source_inventory.md`
- `docs/research/alex_temiz/evidence_matrix.md`
- `docs/research/alex_temiz/distillation_notes.md`
- `docs/research/alex_temiz/data_gap_report.md`

No Python files. No changes to any existing code. Research only.
