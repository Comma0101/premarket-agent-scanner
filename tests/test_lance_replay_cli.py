from __future__ import annotations

import json

from typer.testing import CliRunner

from app.db import (
    get_lance_outcomes,
    initialize_database,
    insert_lance_watchlist_event,
)


runner = CliRunner()


def _source_db(tmp_path):
    db_path = tmp_path / "source.sqlite"
    initialize_database(db_path)
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="OPEN",
        event_type="update",
        state="not_in_play",
        score=70,
        data_quality={
            "gap_pct": 8.9,
            "rel_volume": 1.7,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 1 1:45 PM ET",
        },
        payload={"playbook": "mean_reversion_after_capitulation"},
    )
    return db_path


def test_lance_replay_cli_prints_replay_summary_and_uses_scratch_db(tmp_path):
    from cli import lance_replay

    source_db = _source_db(tmp_path)
    scratch_db = tmp_path / "scratch.sqlite"

    result = runner.invoke(
        lance_replay.app,
        [
            "--source-db",
            str(source_db),
            "--scratch-db",
            str(scratch_db),
            "--session-id",
            "session-1",
            "--target-session-date",
            "2026-07-02",
            "--outcome",
            "OPEN:worked",
        ],
    )

    assert result.exit_code == 0
    assert "Lance Replay" in result.stdout
    assert "source_db=" in result.stdout
    assert "scratch_db=" in result.stdout
    assert "outcomes_applied=1" in result.stdout
    assert "OPEN outcome=worked playbook=mean_reversion_after_capitulation status=OK" in result.stdout
    assert "Memory: status=OK outcome_count=1" in result.stdout
    assert "Carryover: status=OK carryover_count=0 fresh_scan_required=True" in result.stdout
    assert "Matches your filter - not buy/sell advice. Verify before acting." in result.stdout
    assert get_lance_outcomes(source_db, session_id="session-1") == []


def test_lance_replay_cli_json_returns_raw_payload(tmp_path):
    from cli import lance_replay

    source_db = _source_db(tmp_path)
    scratch_db = tmp_path / "scratch.sqlite"

    result = runner.invoke(
        lance_replay.app,
        [
            "--source-db",
            str(source_db),
            "--scratch-db",
            str(scratch_db),
            "--session-id",
            "session-1",
            "--outcome",
            "OPEN:worked",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "replay"
    assert payload["outcomes_applied"][0]["ticker"] == "OPEN"
    assert payload["memory"]["outcome_count"] == 1


def test_lance_replay_cli_accepts_named_scenario(tmp_path):
    from cli import lance_replay

    source_db = _source_db(tmp_path)
    scratch_db = tmp_path / "scratch.sqlite"
    scenarios_path = tmp_path / "scenarios.yaml"
    scenarios_path.write_text(
        """
cli_scenario:
  description: CLI scenario test.
  session_id: session-1
  outcomes:
    - ticker: OPEN
      outcome: worked
  expected:
    memory_outcome_count: 1
    carryover_count: 0
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        lance_replay.app,
        [
            "--source-db",
            str(source_db),
            "--scratch-db",
            str(scratch_db),
            "--scenario",
            "cli_scenario",
            "--scenarios-path",
            str(scenarios_path),
            "--check",
        ],
    )

    assert result.exit_code == 0
    assert "Scenario: cli_scenario" in result.stdout
    assert "CLI scenario test." in result.stdout
    assert "Assertions: status=PASS checked=2 failed=0" in result.stdout
    assert "OPEN outcome=worked playbook=mean_reversion_after_capitulation status=OK" in result.stdout


def test_lance_replay_cli_check_exits_nonzero_when_assertions_fail(tmp_path):
    from cli import lance_replay

    source_db = _source_db(tmp_path)
    scratch_db = tmp_path / "scratch.sqlite"
    scenarios_path = tmp_path / "scenarios.yaml"
    scenarios_path.write_text(
        """
bad_cli_scenario:
  session_id: session-1
  outcomes:
    - ticker: OPEN
      outcome: worked
  expected:
    memory_outcome_count: 9
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        lance_replay.app,
        [
            "--source-db",
            str(source_db),
            "--scratch-db",
            str(scratch_db),
            "--scenario",
            "bad_cli_scenario",
            "--scenarios-path",
            str(scenarios_path),
            "--check",
        ],
    )

    assert result.exit_code == 1
    assert "Assertions: status=FAIL checked=1 failed=1" in result.stdout
    assert "- memory_outcome_count expected=9 actual=1 status=FAIL" in result.stdout
