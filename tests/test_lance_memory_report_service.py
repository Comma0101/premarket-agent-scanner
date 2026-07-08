from __future__ import annotations

from app.db import initialize_database, insert_lance_outcome
from services.lance_memory_report_service import LanceMemoryReportService


def test_lance_memory_report_summarizes_outcomes_by_playbook_and_ticker(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="MRVL",
        playbook="mean_reversion_after_capitulation",
        outcome="worked",
        notes="Held relative strength.",
    )
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="MRVL",
        playbook="mean_reversion_after_capitulation",
        outcome="failed",
    )
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="HOOD",
        playbook="earnings_continuation",
        outcome="chop",
    )
    insert_lance_outcome(
        db_path,
        session_id="session-2",
        ticker="MRVL",
        playbook="mean_reversion_after_capitulation",
        outcome="unknown",
    )

    output = LanceMemoryReportService(db_path=db_path).summarize(limit=10)

    assert output["status"] == "OK"
    assert output["outcome_count"] == 4
    assert output["by_playbook"][0] == {
        "playbook": "mean_reversion_after_capitulation",
        "total": 3,
        "outcomes": {"worked": 1, "failed": 1, "chop": 0, "reversed": 0, "unknown": 1},
        "worked_rate": 0.5,
    }
    assert output["by_ticker"][0]["ticker"] == "MRVL"
    assert output["by_ticker"][0]["total"] == 3
    assert output["recent_outcomes"][0]["ticker"] == "MRVL"
    assert "journaled labels" in output["notes"][0]


def test_lance_memory_report_summarizes_unified_action_modes_and_alignment(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="IBM",
        playbook="relative_strength_continuation",
        outcome="worked",
        plan={
            "action_mode": "watch",
            "alignment": "aligned",
            "primary_timeframe": "daily_then_intraday",
        },
    )
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="MRVL",
        playbook="relative_strength_continuation",
        outcome="failed",
        plan={
            "action_mode": "watch",
            "alignment": "aligned",
            "primary_timeframe": "daily_then_intraday",
        },
    )
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="HOOD",
        playbook="review_conflict",
        outcome="chop",
        plan={
            "action_mode": "review",
            "alignment": "conflict",
            "primary_timeframe": "intraday_conflicts_with_daily",
        },
    )

    output = LanceMemoryReportService(db_path=db_path).summarize(limit=10)

    assert output["by_action_mode"][0] == {
        "action_mode": "watch",
        "total": 2,
        "outcomes": {"worked": 1, "failed": 1, "chop": 0, "reversed": 0, "unknown": 0},
        "worked_rate": 0.5,
    }
    assert output["by_alignment"][0] == {
        "alignment": "aligned",
        "total": 2,
        "outcomes": {"worked": 1, "failed": 1, "chop": 0, "reversed": 0, "unknown": 0},
        "worked_rate": 0.5,
    }
    assert output["by_primary_timeframe"][0]["primary_timeframe"] == "daily_then_intraday"


def test_lance_memory_report_filters_by_session_and_ticker(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="MRVL",
        playbook="mean_reversion_after_capitulation",
        outcome="worked",
    )
    insert_lance_outcome(
        db_path,
        session_id="session-2",
        ticker="HOOD",
        playbook="earnings_continuation",
        outcome="failed",
    )

    output = LanceMemoryReportService(db_path=db_path).summarize(
        session_id="session-2",
        ticker="HOOD",
        limit=10,
    )

    assert output["outcome_count"] == 1
    assert output["filters"] == {"session_id": "session-2", "ticker": "HOOD", "limit": 10}
    assert output["by_ticker"][0]["ticker"] == "HOOD"
    assert output["by_playbook"][0]["playbook"] == "earnings_continuation"


def test_lance_memory_report_empty_when_no_outcomes(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    output = LanceMemoryReportService(db_path=db_path).summarize(limit=10)

    assert output["status"] == "EMPTY"
    assert output["outcome_count"] == 0
    assert output["by_playbook"] == []
    assert output["by_ticker"] == []
    assert output["by_action_mode"] == []
    assert output["by_alignment"] == []
    assert output["by_primary_timeframe"] == []
