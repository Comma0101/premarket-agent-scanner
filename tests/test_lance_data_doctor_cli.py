from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _payload() -> dict:
    return {
        "agent_name": "lance_data_doctor",
        "mode": "data_doctor",
        "status": "blocked",
        "doctor_read": {
            "one_liner": "1 ready, 1 blocked. Main blockers: provider_failure=1.",
            "ready_count": 1,
            "blocked_count": 1,
        },
        "root_causes": {
            "ready": ["IBM"],
            "provider_failure": ["MU"],
            "missing_price": ["MU"],
            "stale_or_off_session": [],
            "halted": [],
            "confidence": ["MU"],
            "unknown": [],
        },
        "diagnostics": [],
        "next_actions": ["Check provider connectivity/credentials before trusting Lance output."],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_data_doctor_cli_readable(monkeypatch):
    from cli import lance_data_doctor

    calls: list[dict] = []

    def fake_doctor(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(lance_data_doctor, "run_lance_data_doctor", fake_doctor)

    result = runner.invoke(
        lance_data_doctor.app,
        ["--tickers", "IBM,MU", "--max-candidates", "2"],
    )

    assert result.exit_code == 0
    assert calls[0]["tickers"] == "IBM,MU"
    assert calls[0]["max_candidates"] == 2
    assert "Lance Data Doctor" in result.stdout
    assert "Status: blocked" in result.stdout
    assert "1 ready, 1 blocked. Main blockers: provider_failure=1." in result.stdout
    assert "provider_failure: MU" in result.stdout
    assert "Check provider connectivity" in result.stdout
    assert "Matches your filter - not buy/sell advice" in result.stdout


def test_lance_data_doctor_cli_json(monkeypatch):
    from cli import lance_data_doctor

    monkeypatch.setattr(lance_data_doctor, "run_lance_data_doctor", lambda **kwargs: _payload())

    result = runner.invoke(lance_data_doctor.app, ["--tickers", "IBM", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["mode"] == "data_doctor"
