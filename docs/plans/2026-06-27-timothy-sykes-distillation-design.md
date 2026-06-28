# Timothy Sykes Public-Source Distillation Design

## Objective

Build a professional, source-backed distillation process for a Timothy
Sykes-style trading research profile. The first milestone is a research dossier,
not an agent implementation. The dossier should separate observed public
teaching from interpretation, then translate only well-supported ideas into
operational scanner rules and data-layer requirements.

The eventual agent must not impersonate Timothy Sykes, claim endorsement, or
invent market numbers. It should be framed as a source-backed "Timothy
Sykes-style" educational lens that uses this project's scanner tools for all
prices, gaps, volume, market cap, and confidence labels.

## Non-Goals

- Do not build a live trading or order-entry system.
- Do not scrape paid/private material.
- Do not create the final `trader_profiles/timothy_sykes.md` until the research
  dossier is complete enough to support operational rules.
- Do not claim access to Timothy Sykes, his private process, or current paid
  curriculum.
- Do not turn generic folklore into scanner rules without source evidence.

## Research Inputs

Use public/free sources first, with priority order:

1. Official Timothy Sykes pages and blog posts.
2. Public videos, podcast/interview appearances, and public social posts.
3. Public Profit.ly or related pages if accessible.
4. Credible third-party interviews or profiles for context only.
5. Regulatory, risk, and disclaimer sources where they clarify claims or limits.

Seed URLs to begin from:

- https://www.timothysykes.com/
- https://www.timothysykes.com/blog/
- https://www.timothysykes.com/blog/how-to-trade-in-premarket/
- https://www.timothysykes.com/blog/how-to-use-stock-scanners/
- https://www.timothysykes.com/blog/low-float-stocks/
- https://www.timothysykes.com/blog/penny-stock-patterns/

## Evidence Matrix

Create a structured evidence matrix before writing any profile. Each row should
capture:

- source URL
- source title
- source type: official, video, interview, third-party, disclaimer
- publish or update date when available
- extracted lesson as a short paraphrase
- direct quote excerpt only when useful and copyright-safe
- category: setup, scanner, risk, psychology, market structure, data gap
- confidence: high, medium, low
- supported scanner fields: gap %, gap $, volume, RVOL, market cap, direction,
  confidence label
- missing required fields: float, catalyst/news, dilution/offering risk, former
  runner history, intraday pattern, short interest, SEC filing context
- notes about ambiguity or conflicting evidence

Confidence rules:

- High: repeated in official sources or a detailed official source.
- Medium: supported by one official source or multiple credible secondary
  sources.
- Low: inferred from secondary commentary, old material, or unclear context.

Only high and medium confidence lessons can become scanner/profile rules. Low
confidence lessons go into open questions.

## Distillation Method

Distill in four passes:

1. Source inventory: collect links, metadata, and short descriptions.
2. Evidence extraction: write the matrix row-by-row with citations.
3. Operational translation: convert source-backed lessons into filterable rules
   and grading criteria.
4. Data-fit analysis: mark which rules the current scanner supports and which
   require new tools.

The current scanner supports:

- selected universes/watchlists
- explicit tickers
- gap percent and dollar gap
- direction
- market cap and cap tiers
- volume and relative volume
- confidence labels for missing, stale, low-confidence, and conflicting data

Known likely gaps for a Sykes-style lens:

- float and low-float classification
- catalyst/news detection and quality scoring
- press-release and SEC filing context
- dilution, offering, reverse split, and financing risk
- former-runner history
- intraday chart pattern state
- short interest/borrow context
- OTC vs listed exchange handling

## Deliverables

Milestone 1: Research dossier

- `docs/research/timothy_sykes/source_inventory.md`
- `docs/research/timothy_sykes/evidence_matrix.md`
- `docs/research/timothy_sykes/distillation_notes.md`
- `docs/research/timothy_sykes/data_gap_report.md`

Milestone 2: Profile design

- Draft `trader_profiles/timothy_sykes.md` from the dossier.
- Include only operational rules that map to existing or planned data fields.
- Keep all unsupported rules as open questions or future-data requirements.

Milestone 3: Agent integration

- Optionally add a dedicated desk agent after the profile is validated.
- The agent should load the profile, call MCP scanner tools, and cite only
  tool-returned market numbers.
- The agent should explain that it is a source-backed style lens, not Timothy
  Sykes and not endorsed by him.

## Testing And Review

Review the dossier before profile implementation:

- Every rule must have at least one source row.
- Every numeric filter must be justified by evidence or explicitly labeled as a
  pragmatic starting threshold.
- Every unsupported rule must appear in the data gap report.
- The resulting profile must not require the agent to invent price, volume,
  float, catalyst, or risk facts.

For later implementation, add tests around:

- profile file existence and parseability
- default scan mapping from profile rules
- no invented fields in output examples
- graceful handling when unsupported Sykes-style data is unavailable
