# D1 — Float & Float Rotation — Implementation Plan (for Codex)

> **For Codex:** Execute task by task, in order. Run each verification block and
> commit before moving on. Do **not** push or merge until the final task says to ask
> the human. If reality differs from this document (especially provider payloads),
> **stop and report** rather than guessing — that is the prime directive.

## Read first

1. Read `AGENTS.md`. Prime directive: **never invent a number**; surface unknowns.
2. Env: `.venv/bin/python` (3.12). Tests run **offline** with injected fakes — never
   hit the network in a test.
   - Test: `.venv/bin/python -m pytest -q`
   - Lint: `.venv/bin/ruff check .`
3. Branch off the integrated `main`:
   ```bash
   git switch main && git pull --ff-only && git switch -c feature/data-d1-float
   ```
4. Commit trailer: `Co-Authored-By: Codex <codex@openai.com>`. No `git push` in this plan.

## Goal

Two outcomes:
- **Reliable float** — `SmallCapEvidence.float_shares` should be populated whenever a
  free public source has it, regardless of which provider supplied the rest of the
  profile. Today FMP's v3 `/profile` payload frequently omits `floatShares`, so float
  silently becomes `None` on the FMP path.
- **Float rotation** — add the derived signal `float_rotation = day_volume / float`
  ("how many times the tradeable float has turned over") through the model, evidence,
  **grade**, tool output, orchestrator, and CLI. This is the first signal that makes a
  grade read like Sykes ("low float, rotating") instead of a generic gapper.

## What already exists (do not rebuild)

- `AssetProfile.float_shares` / `shares_outstanding` (`app/models.py`).
- `FMPProvider.get_profile` and `YFinanceProvider.get_profile` both set
  `float_shares=_num(record/info.get("floatShares"))`.
- `ProfileService` resolves: fresh cache → FMP → yfinance → stale cache.
- `SmallCapEvidence` has `float_shares`, `shares_outstanding`, `float_source`,
  `is_low_float`; `SmallCapEvidenceService` sets `is_low_float = float_shares <=
  low_float_threshold` (10M) and adds matched signals `float_known` / `low_float_context`.

## ⚠️ Critical flow fact

In `SmallCapScannerService.scan`, candidates are **graded first**
(`grade_small_cap_candidate`), and evidence (float) is attached **after** via
`evidence_service.enrich_candidates`. So float/rotation are **not** available at grade
time. To let them affect the grade you MUST add a **post-enrichment adjustment**
(Task 3) — do not try to read float inside `grade_small_cap_candidate`.

---

### Task 1: Model field + pure compute helper

**Files:** `app/models.py`, `services/small_cap_scanner_service.py` (or a small utils
location next to the other `compute_*` helpers in `services/scanner_service.py`),
`tests/test_small_cap_scanner.py`.

**Step 1 — failing test:**

```python
from services.scanner_service import compute_float_rotation  # place beside compute_rel_volume

def test_compute_float_rotation():
    assert compute_float_rotation(5_000_000, 5_000_000) == 1.0   # full rotation
    assert compute_float_rotation(2_000_000, 8_000_000) == 0.25
    assert compute_float_rotation(1_000_000, None) is None
    assert compute_float_rotation(None, 8_000_000) is None
    assert compute_float_rotation(1_000_000, 0) is None
```

**Step 2 — implement** `compute_float_rotation(volume, float_shares)` next to
`compute_rel_volume` in `services/scanner_service.py`: return `volume / float_shares`
when both are present and `float_shares > 0`, else `None`. (Round to 4 dp like the
other compute_* helpers if they round.)

**Step 3 — model:** add `float_rotation: float | None = None` to `SmallCapEvidence`
in `app/models.py`.

**Verify:** `.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q` ; commit.

---

### Task 2: Evidence service computes & stores float_rotation (data only)

**Files:** `services/small_cap_evidence_service.py`, `tests/test_small_cap_evidence.py`.

`enrich_candidates` already iterates candidates and builds evidence per candidate.
Inside `_build_evidence` (it receives the candidate), after `float_shares` is resolved:

- `evidence.float_rotation = compute_float_rotation(candidate.volume, evidence.float_shares)`
- Add a risk note when float is known but rotation is `None`/low, e.g.
  `"float rotation unknown (volume or float missing)."` Keep it honest — do not infer.

**Step 1 — failing test** in `tests/test_small_cap_evidence.py`: with a fake profile
service returning `float_shares=5_000_000` and a candidate with `volume=10_000_000`,
assert `evidence.float_rotation == 2.0` and `evidence.is_low_float is True`.

**Step 2 — implement.** **Step 3 — verify** + commit.

> Note: `enrich_candidates(candidates)` currently takes only candidates and reads
> `candidate.volume` — confirm `volume` is on the candidate (it is). Do not add new
> network calls here.

---

### Task 3: Make float/rotation affect the grade (post-enrichment adjustment)

**Files:** `services/small_cap_scanner_service.py`, `tests/test_small_cap_scanner.py`.

**Step 1 — failing test:** two candidates identical except one has
`evidence.float_rotation=2.0` + `is_low_float=True`; after a scan, assert the
low-float/rotating one scores **higher** and, when `gap_basis=="premarket"` and
confidence OK, can reach `A_WATCH`; assert a non-premarket basis still cannot reach
`A_WATCH` (the existing gap_basis gate must still hold).

**Step 2 — implement** an adjustment applied **after** `enrich_candidates` in
`SmallCapScannerService.scan` (e.g. `_apply_float_signals(candidate)`), which:
- adds score for `is_low_float` and for rotation tiers — pragmatic, labeled defaults:
  `float_rotation >= 1.0` → `+15`, matched `full_float_rotation`;
  `>= 0.5` → `+8`, matched `high_float_rotation`; `is_low_float` → `+10`, matched
  `low_float_fit` (avoid double-counting if already present).
- **re-derives the grade by reusing the existing grade gate** (the same `_grade(...)`
  used in `grade_small_cap_candidate`, including the `gap_basis == "premarket"`
  requirement for `A_WATCH`). Do NOT bypass that gate.

Keep all grading logic in `small_cap_scanner_service.py` (one place). Thresholds are
pragmatic, not claimed as Sykes's exact criteria — say so in a comment.

**Verify** full `tests/test_small_cap_scanner.py` + commit.

---

### Task 4: Reliable float backfill (honest source)

**Files:** `services/profile_service.py`, `services/small_cap_evidence_service.py`,
their tests.

**Goal:** when the resolved profile lacks `float_shares`, backfill it from a free
source and record where float actually came from — without misreporting `float_source`.

**Step 1 — confirm the gap first.** Inspect (or test against a recorded/fake payload)
whether FMP v3 `/profile` returns `floatShares`. If it does, this task may reduce to a
test; if it does not (common), implement the backfill. **Report what you find.**

**Step 2 — implement** a small resolver on `ProfileService`, e.g.
`resolve_float(ticker) -> tuple[float | None, str | None]` returning
`(float_shares, source)`: prefer the cached/primary profile's float; if `None`, fall
back to a yfinance float lookup. yfinance is free (no budget gate), so this adds no API
cost. Keep it injectable for offline tests.

**Step 3 — wire** the evidence service to use it: when `profile.float_shares is None`,
call `resolve_float`, and set `evidence.float_shares` **and** `evidence.float_source`
to the true origin (e.g. `"yfinance"`), so `float_source` never lies. Recompute
`is_low_float` and `float_rotation` after backfill.

**Step 4 — tests** (offline, fake providers): primary profile float `None` + yfinance
float `8_000_000` → `evidence.float_shares == 8_000_000`,
`evidence.float_source == "yfinance"`. **Verify** + commit.

---

### Task 5: Surface float_rotation everywhere it should appear

**Files:** `agent_tools/tools.py`, `agent_orchestrator/` (models + `trading_agent.py`),
`cli/scan_small_caps.py`, tests.

- `agent_tools/tools.py::_small_cap_evidence_to_dict` → add
  `"float_rotation": evidence.float_rotation` (next to `is_low_float`).
- Orchestrator `_evidence_summary` → include rotation when known, e.g.
  `float=5.0M low rot=2.0x`.
- CLI `_format_evidence_summary` (or the evidence column) → show rotation.
- Update/extend the existing tool + orchestrator tests to assert `float_rotation` is
  present in the JSON.

**Verify** `.venv/bin/python -m pytest -q` + commit.

---

### Task 6: Docs + close the data-gap row + full verification

- README "Small-Cap Discovery Scanner": one line that candidates now surface
  **float** and **float rotation** (volume ÷ float).
- `docs/research/timothy_sykes/data_gap_report.md`: move the **float / low-float**
  row from `unsupported` to `supported` (or `partial` if FMP float remains spotty),
  noting the yfinance backfill + the new `float_rotation` derivation.

**Verify:**
```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
git diff --check
```
Commit.

---

### Task 7: Stop and report

Summarize: new field(s), the float-backfill source behavior, the grade adjustment +
that the `gap_basis` A-gate still holds, tests added, and whether FMP float turned out
reliable or needed the yfinance backfill. Then **ask** before merging
`feature/data-d1-float` into `main`, pushing, or starting D2 (catalyst/news). Do not
merge or push without approval.
