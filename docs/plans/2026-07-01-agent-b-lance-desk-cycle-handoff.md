# Agent B Handoff — Lance Desk Cycle UX

## Objective

Build the user-facing UX around the new `run_lance_desk_cycle` capability so the
human can run Lance as a live intraday desk without manually chaining five tools.

Codex owns the service/tool lane:

- `services/lance_desk_cycle_service.py`
- `agent_tools/tools.py::run_lance_desk_cycle`
- `agent_tools/definitions.py` schema and dispatch entry
- `tests/test_lance_desk_cycle_service.py`
- `tests/test_agent_tools.py` coverage

Agent B should avoid editing those files unless a focused test proves a bug.

## Required Reading

1. `AGENTS.md`
2. `.agents/skills/premarket-scanner/SKILL.md`
3. `.agents/skills/market-data-guardrails/SKILL.md`
4. `services/lance_desk_cycle_service.py`
5. `tests/test_lance_desk_cycle_service.py`
6. `trader_profiles/lance_breitstein.md`

## Recommended Feature Lane

Create a CLI/reporting layer for the desk cycle.

Suggested new files:

- `cli/lance_desk_cycle.py`
- `tests/test_lance_desk_cycle_cli.py`

Optional docs-only updates:

- `README.md`
- `.claude/agents/premarket-desk.md`

Avoid broad rewrites. Keep the CLI as a thin wrapper around
`agent_tools.tools.run_lance_desk_cycle` or `LanceDeskCycleService.run`.

## UX Shape

Command examples:

```bash
.venv/bin/python -m cli.lance_desk_cycle --tickers IBM,MRVL,HOOD --max-candidates 5
.venv/bin/python -m cli.lance_desk_cycle --all-universes --max-candidates 15 --persist
.venv/bin/python -m cli.lance_desk_cycle --watchlist hot_active --json
```

Readable output should be grouped:

1. Session and status
2. Market context / theme rotation
3. Top Lance watchlist rows
4. What changed since the last run
5. Pending manual review queue
6. Carryover prep
7. Disclaimer

Do not print bare market numbers. For every market row, include the available
source/as-of/gap_basis/confidence fields from the payload. If a field is missing,
print `unknown`; do not infer it.

## Acceptance Criteria

- `--json` returns the raw `run_lance_desk_cycle` payload.
- Human-readable mode includes the grouped sections above.
- Defaults are usable: if no tickers/universe/watchlist are supplied, use
  `all_universes=True`.
- Tests use fake services or monkeypatching only. No network in tests.
- Focused tests pass:

```bash
.venv/bin/python -m pytest tests/test_lance_desk_cycle_cli.py -q
```

- Full verification passes:

```bash
scripts/verify.sh
```

## Live Test Protocol

After tests pass, run the closed-market system check first. It must return
`Status: PASS` before live desk testing:

```bash
.venv/bin/python -m cli.lance_system_check --source-db data/market_data.sqlite --scratch-dir /tmp/lance_system_check
```

Then run a bounded smoke test with a small ticker list before scanning all
universes:

```bash
.venv/bin/python -m cli.lance_desk_cycle --tickers IBM,MRVL,HOOD --max-candidates 5 --persist
```

Report only tool/data-layer values. End market-facing output with:

`Matches your filter - not buy/sell advice. Verify before acting.`

## Copy/Paste Prompt For Agent B

Read `AGENTS.md`, then read
`docs/plans/2026-07-01-agent-b-lance-desk-cycle-handoff.md`.
Build the Lance desk cycle CLI/reporting UX exactly as scoped there. Use TDD:
write `tests/test_lance_desk_cycle_cli.py` first with fake service output, watch it
fail, then implement `cli/lance_desk_cycle.py`. Do not edit
`services/lance_desk_cycle_service.py`, `agent_tools/tools.py`, or
`agent_tools/definitions.py` unless a failing focused test proves a bug in the
service/tool layer. Stop after `scripts/verify.sh` passes and report the command
examples for live testing.
