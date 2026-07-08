from __future__ import annotations

from app.db import initialize_database
from services.lance_outcome_journal_service import LanceOutcomeJournalService


def test_lance_outcome_journal_records_and_returns_recent_outcomes(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    service = LanceOutcomeJournalService(db_path=db_path)
    output = service.record(
        session_id="session-1",
        ticker="NVDA",
        playbook="earnings_continuation",
        outcome="worked",
        notes="Held relative strength above QQQ.",
        plan={"ticker": "NVDA", "state": "setup_forming"},
    )

    assert output["status"] == "OK"
    assert output["recorded"]["ticker"] == "NVDA"
    assert output["recorded"]["outcome"] == "worked"
    assert output["recent_outcomes"][0]["plan"]["state"] == "setup_forming"


def test_lance_outcome_journal_returns_unified_plan_summary(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    output = LanceOutcomeJournalService(db_path=db_path).record(
        session_id="session-1",
        ticker="IBM",
        playbook="relative_strength_continuation",
        outcome="worked",
        plan={
            "action_mode": "watch",
            "alignment": "aligned",
            "primary_timeframe": "daily_then_intraday",
            "thesis": "Daily idea is valid; intraday timing is still forming.",
        },
    )

    assert output["status"] == "OK"
    assert output["recorded"]["plan_summary"] == {
        "action_mode": "watch",
        "alignment": "aligned",
        "primary_timeframe": "daily_then_intraday",
        "thesis": "Daily idea is valid; intraday timing is still forming.",
    }
    assert output["recent_outcomes"][0]["plan"]["action_mode"] == "watch"


def test_lance_outcome_journal_rejects_unknown_outcome(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    output = LanceOutcomeJournalService(db_path=db_path).record(
        session_id="session-1",
        ticker="NVDA",
        playbook="earnings_continuation",
        outcome="great",
    )

    assert "error" in output
    assert "outcome must be one of" in output["error"]
