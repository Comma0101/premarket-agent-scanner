from __future__ import annotations

import json

from typer.testing import CliRunner

from app.db import initialize_database, insert_lance_watchlist_event


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


def test_lance_replay_suite_cli_prints_suite_summary(tmp_path):
    from cli import lance_replay_suite

    source_db = _source_db(tmp_path)
    scenarios_path = tmp_path / "scenarios.yaml"
    scenarios_path.write_text(
        """
passing:
  session_id: session-1
  outcomes:
    - ticker: OPEN
      outcome: worked
  expected:
    memory_outcome_count: 1
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        lance_replay_suite.app,
        [
            "--source-db",
            str(source_db),
            "--scenarios-path",
            str(scenarios_path),
            "--scratch-dir",
            str(tmp_path / "scratch"),
        ],
    )

    assert result.exit_code == 0
    assert "Lance Replay Suite" in result.stdout
    assert "Status: PASS" in result.stdout
    assert "scenario_count=1 passed=1 failed=0" in result.stdout
    assert "- passing assertion_status=PASS checked=1 failed=0" in result.stdout
    assert "Matches your filter - not buy/sell advice. Verify before acting." in result.stdout


def test_lance_replay_suite_cli_exits_nonzero_on_failed_scenario(tmp_path):
    from cli import lance_replay_suite

    source_db = _source_db(tmp_path)
    scenarios_path = tmp_path / "scenarios.yaml"
    scenarios_path.write_text(
        """
failing:
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
        lance_replay_suite.app,
        [
            "--source-db",
            str(source_db),
            "--scenarios-path",
            str(scenarios_path),
            "--scratch-dir",
            str(tmp_path / "scratch"),
        ],
    )

    assert result.exit_code == 1
    assert "Status: FAIL" in result.stdout
    assert "- failing assertion_status=FAIL checked=1 failed=1" in result.stdout


def test_lance_replay_suite_cli_json_returns_raw_payload(tmp_path):
    from cli import lance_replay_suite

    source_db = _source_db(tmp_path)
    scenarios_path = tmp_path / "scenarios.yaml"
    scenarios_path.write_text(
        """
passing:
  session_id: session-1
  outcomes:
    - ticker: OPEN
      outcome: worked
  expected:
    memory_outcome_count: 1
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        lance_replay_suite.app,
        [
            "--source-db",
            str(source_db),
            "--scenarios-path",
            str(scenarios_path),
            "--scratch-dir",
            str(tmp_path / "scratch"),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["results"][0]["scenario_name"] == "passing"
