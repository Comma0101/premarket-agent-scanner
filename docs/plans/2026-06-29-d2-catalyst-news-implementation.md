# D2 Catalyst News Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add source-backed catalyst/news ingestion and conservative catalyst quality/recency signals to the Sykes-style small-cap scanner.

**Architecture:** Keep news acquisition behind a provider, persist catalyst events in the existing `ticker_news` cache, and let `SmallCapEvidenceService` attach cached/fetched catalysts to candidates. Catalyst grading is a post-enrichment adjustment in `SmallCapScannerService`, just like D1 float rotation, so raw scanner output remains provider-independent and missing news stays unknown.

**Tech Stack:** Python dataclasses, SQLite migrations, `xml.etree.ElementTree` RSS parsing, `urllib.request` or injected fetchers for live feeds, pytest fakes, Ruff.

---

## Read First

1. Read `AGENTS.md`. Prime directive: never invent market numbers or catalyst facts.
2. Use `.venv/bin/python`.
3. Tests must run offline with injected feed XML; no test may call a live RSS endpoint.
4. Commit after every task with `Co-Authored-By: Codex <codex@openai.com>`.
5. Do not push or merge without human approval.

## Source Notes

Validated by header checks on 2026-06-29:

- PRNewswire RSS: `https://www.prnewswire.com/rss/news-releases-list.rss` returned `200` and `application/xml`.
- GlobeNewswire RSS: `https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies` returned `200` and `application/rss+xml`.
- Business Wire RSS: `https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFpQWQ==` returned `200` and `application/rss+xml`.
- Accesswire candidate endpoint returned `403` from this environment, so keep it configurable/optional, not a default source.

The provider should treat RSS feeds as discovery sources only. A headline is a catalyst only when the event text explicitly mentions the ticker or symbol context; otherwise leave catalyst unknown.

---

### Task 1: Extend catalyst model and DB cache shape

**Files:**
- Modify: `app/models.py`
- Modify: `app/db.py`
- Test: `tests/test_small_cap_evidence.py`

**Step 1: Write the failing test**

Extend the existing news cache round-trip test to assert new catalyst fields:

```python
insert_news_event(
    db_path,
    CatalystEvent(
        ticker="HOT",
        headline="HOT wins supply deal",
        published_at="2026-06-29T12:00:00Z",
        source="fake-wire",
        url="https://example.test/hot",
        summary="Supply deal",
        confidence="OK",
        catalyst_quality="hard",
    ),
)
news = get_cached_news(db_path, "HOT")
assert news[0].catalyst_quality == "hard"
assert news[0].recency_minutes is None
```

**Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_small_cap_evidence.py::test_evidence_cache_round_trips_filings_news_and_runner_history -q
```

Expected: `CatalystEvent.__init__()` does not accept `catalyst_quality`.

**Step 3: Implement minimal model/cache support**

- Add `catalyst_quality: str | None = None` to `CatalystEvent`.
- Add `recency_minutes: float | None = None` to `CatalystEvent`. This is a transient derived field; do not persist it.
- Add `catalyst_quality TEXT` to `ticker_news`.
- Add `_migrate()` guard for existing `ticker_news` tables.
- Persist/read `catalyst_quality` in `insert_news_event()` and `get_cached_news()`.

**Step 4: Verify**

```bash
.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

**Step 5: Commit**

```bash
git add app/models.py app/db.py tests/test_small_cap_evidence.py
git commit -m "Add catalyst quality to news cache"
```

---

### Task 2: Add RSS news provider with offline parser tests

**Files:**
- Create: `providers/news_provider.py`
- Test: `tests/test_news_provider.py`

**Step 1: Write parser tests**

Create tests with local XML strings:

```python
def test_news_provider_parses_matching_rss_item():
    xml = """<?xml version="1.0"?><rss><channel><item>
      <title>HOT announces FDA clearance</title>
      <link>https://example.test/hot</link>
      <pubDate>Mon, 29 Jun 2026 12:00:00 GMT</pubDate>
      <description>HOT today announced FDA clearance.</description>
    </item></channel></rss>"""

    provider = RSSNewsProvider(
        feeds=[NewsFeed(name="fake-wire", url="https://example.test/rss")],
        fetcher=lambda url: xml,
    )

    events = provider.get_recent_news("HOT")
    assert events[0].ticker == "HOT"
    assert events[0].source == "fake-wire"
    assert events[0].catalyst_quality == "hard"
    assert events[0].confidence == "OK"
```

Also test:

- non-matching ticker returns `[]`;
- soft phrases like `to present at conference` classify as `soft`;
- invalid XML or fetch error returns `[]`, not an exception.

**Step 2: Run tests to verify failure**

```bash
.venv/bin/python -m pytest tests/test_news_provider.py -q
```

Expected: module missing.

**Step 3: Implement provider**

Add:

```python
@dataclass
class NewsFeed:
    name: str
    url: str
```

Add `RSSNewsProvider`:

- constructor accepts `feeds: list[NewsFeed] | None`, `fetcher: Callable[[str], str] | None`, `timeout=15`;
- default feeds are PRNewswire, GlobeNewswire, Business Wire;
- `get_recent_news(ticker, limit=10) -> list[CatalystEvent]`;
- parse RSS with `xml.etree.ElementTree`;
- parse dates with `email.utils.parsedate_to_datetime`;
- match ticker conservatively against title + description using uppercase token boundaries and common formats like `$HOT`, `(NASDAQ: HOT)`, `(NYSE: HOT)`, ` HOT `;
- classify `hard` when text contains terms like `fda`, `clearance`, `approval`, `contract`, `award`, `earnings`, `merger`, `acquisition`, `uplist`, `patent`, `partnership`;
- classify `soft` when text contains terms like `conference`, `presentation`, `letter to shareholders`, `provides update`, `webinar`;
- otherwise `unknown`.

**Step 4: Verify**

```bash
.venv/bin/python -m pytest tests/test_news_provider.py -q
```

**Step 5: Commit**

```bash
git add providers/news_provider.py tests/test_news_provider.py
git commit -m "Add RSS news provider for catalyst discovery"
```

---

### Task 3: Wire news provider into evidence enrichment

**Files:**
- Modify: `services/small_cap_evidence_service.py`
- Test: `tests/test_small_cap_evidence.py`

**Step 1: Write failing tests**

Add a fake news provider:

```python
class FakeNewsProvider:
    def get_recent_news(self, ticker: str):
        return [
            CatalystEvent(
                ticker=ticker,
                headline="HOT announces FDA clearance",
                published_at="2026-06-29T12:00:00Z",
                source="fake-wire",
                url="https://example.test/hot",
                catalyst_quality="hard",
                confidence="OK",
            )
        ]
```

Test that `SmallCapEvidenceService(..., news_provider=FakeNewsProvider(), db_path=tmp_db)`:

- attaches the catalyst when cache is empty;
- removes `catalyst` from `missing_fields`;
- persists it so `get_cached_news()` returns it.

Add a failure-provider test that raises and assert:

- `catalyst` remains missing;
- evidence risk notes mention news lookup failed.

**Step 2: Run tests to verify failure**

```bash
.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

Expected: fetched news is not used.

**Step 3: Implement**

- Add `_news_error_by_ticker`.
- Replace `_get_cached_catalysts()` with `_get_recent_catalysts()`:
  - first read `get_cached_news()`;
  - if cached exists, return it;
  - if no provider, return [];
  - call `news_provider.get_recent_news(ticker)`;
  - persist each returned `CatalystEvent` with `insert_news_event()`;
  - return list only if it is a list.
- In `_build_evidence`, if news provider fails, add:
  `"news lookup failed: <error>; catalyst is unknown."`

**Step 4: Verify**

```bash
.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
```

**Step 5: Commit**

```bash
git add services/small_cap_evidence_service.py tests/test_small_cap_evidence.py
git commit -m "Fetch and cache catalyst news during evidence enrichment"
```

---

### Task 4: Derive catalyst recency

**Files:**
- Modify: `services/small_cap_evidence_service.py`
- Test: `tests/test_small_cap_evidence.py`

**Step 1: Write failing test**

Use an injectable clock on `SmallCapEvidenceService`, e.g. `now_fn`, with an event at `2026-06-29T12:00:00Z` and now at `2026-06-29T12:30:00Z`.

Assert:

```python
assert enriched.evidence.catalysts[0].recency_minutes == 30
```

**Step 2: Implement**

- Add `now_fn` constructor parameter defaulting to `utc_now_iso`.
- Add helper `_apply_catalyst_recency(catalysts, now_iso)`.
- Parse ISO timestamps defensively; if missing/unparseable, leave `recency_minutes=None`.

**Step 3: Verify and commit**

```bash
.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q
git add services/small_cap_evidence_service.py tests/test_small_cap_evidence.py
git commit -m "Derive catalyst recency in evidence enrichment"
```

---

### Task 5: Apply catalyst grade adjustment without inventing catalysts

**Files:**
- Modify: `services/small_cap_scanner_service.py`
- Test: `tests/test_small_cap_scanner.py`

**Step 1: Write failing tests**

Add scan-level tests where candidates are identical except catalyst evidence:

- hard catalyst with `recency_minutes <= 120` lifts score and can help reach `A_WATCH` when `gap_basis == "premarket"` and confidence OK;
- missing catalyst caps grade at `B_WATCH` even if score would otherwise reach A;
- `gap_basis == "last_trade"` still cannot reach `A_WATCH`.

**Step 2: Implement**

In post-enrichment adjustment:

- `_apply_catalyst_signals(candidate)`;
- if no catalysts, cap grade at B using existing `_grade` output then downgrade A to B;
- if first/any catalyst has `catalyst_quality == "hard"` and `recency_minutes is None or <= 120`, add `+15`, matched `fresh_hard_catalyst`;
- if `catalyst_quality == "soft"`, add `+5`, matched `soft_catalyst`;
- never create a catalyst label from price/volume alone.

Keep this next to `_apply_float_signals()`.

**Step 3: Verify and commit**

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
git add services/small_cap_scanner_service.py tests/test_small_cap_scanner.py
git commit -m "Adjust small-cap grades for verified catalysts"
```

---

### Task 6: Surface catalyst quality and recency

**Files:**
- Modify: `agent_tools/tools.py`
- Modify: `agent_orchestrator/trading_agent.py`
- Modify: `cli/scan_small_caps.py`
- Test: `tests/test_agent_tools.py`
- Test: `tests/test_agent_orchestrator.py`
- Test: `tests/test_small_cap_scanner.py`

**Step 1: Write failing tests**

Assert serialized catalyst dict includes:

- `catalyst_quality`
- `recency_minutes`

Assert orchestrator summary includes, for example:

```text
catalyst=hard 30m PR: HOT announces FDA clearance
```

Assert CLI compact evidence includes `hard` or `30m` when available.

**Step 2: Implement serializers/formatters**

- Add fields in `_catalyst_event_to_dict()`.
- In orchestrator summary, include quality and recency before source/headline.
- In CLI, keep compact width stable; use `hard`, `soft`, and `30m` tokens rather than long descriptions.

**Step 3: Verify and commit**

```bash
.venv/bin/python -m pytest -q
git add agent_tools/tools.py agent_orchestrator/trading_agent.py cli/scan_small_caps.py \
        tests/test_agent_tools.py tests/test_agent_orchestrator.py tests/test_small_cap_scanner.py
git commit -m "Surface catalyst quality and recency"
```

---

### Task 7: CLI provider refresh entry point

**Files:**
- Modify: `cli/scan_small_caps.py`
- Or create: `cli/refresh_news.py`
- Test: `tests/test_small_cap_scanner.py` or new `tests/test_news_cli.py`

**Step 1: Choose simple surface**

Prefer adding `--refresh-news` to `cli.scan_small_caps` only if the enrichment path needs an explicit trigger. Otherwise create `python -m cli.refresh_news --tickers HOT,COOL`.

Recommendation: create `cli/refresh_news.py` to keep live RSS work explicit and avoid surprising full-market scans.

**Step 2: Implement offline-tested CLI**

- Accept `--tickers`.
- Use `RSSNewsProvider` and `insert_news_event`.
- Print count per ticker.
- Catch provider errors cleanly.

**Step 3: Verify and commit**

```bash
.venv/bin/python -m pytest -q
git add cli/refresh_news.py tests/test_news_cli.py
git commit -m "Add explicit news refresh CLI"
```

---

### Task 8: Docs and data-gap report

**Files:**
- Modify: `README.md`
- Modify: `docs/research/timothy_sykes/data_gap_report.md`

**Step 1: Update docs**

- README: mention catalyst provider uses verified RSS feeds and cached news evidence.
- Data gap report: move catalyst/news from unsupported to partial, noting RSS source limitations and that missing catalysts remain unknown.

**Step 2: Full verification**

```bash
scripts/verify.sh
```

Expected:

- pytest passes;
- Ruff passes;
- `git diff --check` passes.

**Step 3: Commit**

```bash
git add README.md docs/research/timothy_sykes/data_gap_report.md
git commit -m "Document catalyst news support and limits"
```

---

### Task 9: Stop and report

Report:

- provider defaults and which sources were verified;
- catalyst quality labels and recency behavior;
- cache behavior and unknown handling;
- grade adjustment and A-grade gates;
- final test count;
- any live-feed limitations.

Ask before merging, pushing, or starting D3.

