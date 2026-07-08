from typer.testing import CliRunner


runner = CliRunner()


def test_sykes_cli_defaults_to_us_listed_market(monkeypatch):
    import cli.sykes as module

    calls = {}

    class FakeSykesLivePlanService:
        def run(self, **kwargs):
            calls.update(kwargs)
            return {
                "agent_name": "timothy_sykes",
                "mode": "live_and_swing",
                "status": "OK",
                "session_banner": "MARKET_OPEN, Jul 6 10:00 AM ET.",
                "desk_read": {"one_liner": "0 intraday watch, 0 swing watch, 0 blocked."},
                "intraday_watchlist": [],
                "swing_watchlist": [],
                "blocked": [],
                "auto_slices": [],
                "scanner": {"candidate_count": 0},
                "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
            }

    monkeypatch.setattr(module, "SykesLivePlanService", FakeSykesLivePlanService)

    result = runner.invoke(module.app, ["--market-limit", "5", "--no-json"])

    assert result.exit_code == 0
    assert calls["market"] == "us-listed"
    assert calls["market_limit"] == 5
    assert calls["live_intraday"] is True
    assert "Tim Sykes Live" in result.stdout


def test_sykes_cli_json_prints_payload(monkeypatch):
    import cli.sykes as module

    class FakeSykesLivePlanService:
        def run(self, **kwargs):
            return {
                "agent_name": "timothy_sykes",
                "mode": "live_and_swing",
                "status": "OK",
                "intraday_watchlist": [{"ticker": "HOT"}],
                "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
            }

    monkeypatch.setattr(module, "SykesLivePlanService", FakeSykesLivePlanService)

    result = runner.invoke(module.app, ["--tickers", "HOT", "--json"])

    assert result.exit_code == 0
    assert '"ticker": "HOT"' in result.stdout
