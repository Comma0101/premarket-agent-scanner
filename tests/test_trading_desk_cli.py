from typer.testing import CliRunner


runner = CliRunner()


def test_trading_desk_cli_runs_one_desk(monkeypatch):
    import cli.trading_desk as module

    calls = {}

    class FakeTradingDeskService:
        def run(self, **kwargs):
            calls.update(kwargs)
            return {
                "agent_name": "trading_desk",
                "mode": "one_run",
                "status": "OK",
                "session_banner": "MARKET_OPEN desk",
                "desk_read": {"one_liner": "Lance: 1 active. Tim: 1 watch."},
                "operator_brief": "# Trading Desk Operator Brief\n\n## Desk Read\nLance: 1 active. Tim: 1 watch.",
                "top_slices": [
                    {
                        "agent": "lance",
                        "ticker": "IBM",
                        "lane": "intraday",
                        "state": "watching",
                        "setup": "mean_reversion",
                        "data": "confidence=OK",
                        "why": "why",
                        "watch": "watch",
                        "risk": "risk",
                    }
                ],
                "blocked_data": [{"agent": "tim_sykes", "ticker": "BAD"}],
                "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
            }

    monkeypatch.setattr(module, "TradingDeskService", FakeTradingDeskService)

    result = runner.invoke(module.app, ["--market-limit", "25", "--max-workers", "3"])

    assert result.exit_code == 0
    assert calls["market"] == "us-listed"
    assert calls["market_limit"] == 25
    assert calls["max_workers"] == 3
    assert "Trading Desk Operator Brief" in result.stdout
    assert "Lance: 1 active. Tim: 1 watch." in result.stdout


def test_trading_desk_cli_json(monkeypatch):
    import cli.trading_desk as module

    class FakeTradingDeskService:
        def run(self, **kwargs):
            return {"agent_name": "trading_desk", "top_slices": [{"ticker": "IBM"}]}

    monkeypatch.setattr(module, "TradingDeskService", FakeTradingDeskService)

    result = runner.invoke(module.app, ["--tickers", "IBM", "--json"])

    assert result.exit_code == 0
    assert '"agent_name": "trading_desk"' in result.stdout
    assert '"ticker": "IBM"' in result.stdout
