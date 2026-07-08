from __future__ import annotations

import json

from typer.testing import CliRunner

from tests.test_lance_ticker_explain_service import _payload


runner = CliRunner()


def test_lance_explain_cli_prints_ticker_card(tmp_path):
    from cli import lance_explain

    payload_path = tmp_path / "latest_command_center.json"
    payload_path.write_text(json.dumps(_payload()), encoding="utf-8")

    result = runner.invoke(
        lance_explain.app,
        ["IBM", "--payload", str(payload_path)],
    )

    assert result.exit_code == 0
    assert "Lance Ticker Explain" in result.stdout
    assert "ticker=IBM" in result.stdout
    assert "status=FOUND" in result.stdout
    assert "confidence=OK" in result.stdout
    assert "gap_basis=premarket" in result.stdout
    assert "price=189.25" in result.stdout
    assert "rvol=4.20x" in result.stdout
    assert "Intraday" in result.stdout
    assert "waiting_for=hold above prior 2-minute high" in result.stdout
    assert "Swing" in result.stdout
    assert "invalidates_if=daily close loses reclaim level" in result.stdout
    assert "Matches your filter - not buy/sell advice. Verify before acting." in result.stdout


def test_lance_explain_cli_json_returns_payload(tmp_path):
    from cli import lance_explain

    payload_path = tmp_path / "latest_command_center.json"
    payload_path.write_text(json.dumps(_payload()), encoding="utf-8")

    result = runner.invoke(
        lance_explain.app,
        ["ARM", "--payload", str(payload_path), "--json"],
    )

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["ticker"] == "ARM"
    assert parsed["status"] == "OMITTED"
    assert parsed["omitted_reason"]["stage"] == "source_rows"
