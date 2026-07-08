from services.trading_desk_service import TradingDeskService


def test_trading_desk_one_run_combines_lance_and_sykes_slices():
    output = TradingDeskService(
        lance_service=FakeLanceService(),
        sykes_service=FakeSykesService(),
    ).run(market="us-listed", market_limit=50, max_workers=4, summary_limit=3)

    assert output["agent_name"] == "trading_desk"
    assert output["mode"] == "one_run"
    assert output["status"] == "OK"
    assert output["desk_read"]["one_liner"] == "Lance: 1 active monitor. Tim: 1 intraday watch."
    assert output["market_status"]["lance_session_banner"] == "MARKET_OPEN lance"
    assert output["market_status"]["sykes_session_banner"] == "MARKET_OPEN sykes"
    assert output["top_slices"] == [
        {
            "agent": "lance",
            "ticker": "IBM",
            "lane": "intraday",
            "state": "triggered_reference",
            "setup": "mean_reversion",
            "data": "price=100 confidence=OK",
            "why": "Lance why.",
            "watch": "hold level",
            "risk": "lose level",
        },
        {
            "agent": "tim_sykes",
            "ticker": "HOT",
            "lane": "intraday",
            "state": "primary_live_watch",
            "setup": "catalyst_spiker_watch",
            "data": "gap=12 confidence=OK",
            "why": "Tim why.",
            "watch": "verify catalyst",
            "risk": "volume fades",
        },
    ]
    assert output["blocked_data"] == [
        {"agent": "lance", "ticker": "BAD"},
        {"agent": "tim_sykes", "ticker": "CAVEAT"},
    ]
    assert output["agents"]["lance"]["agent_name"] == "lance_full_cycle"
    assert output["agents"]["tim_sykes"]["agent_name"] == "timothy_sykes"
    assert output["disclaimer"] == "Matches your filter - not buy/sell advice. Verify before acting."


class FakeLanceService:
    def run(self, **kwargs):
        assert kwargs["market"] == "us-listed"
        assert kwargs["market_limit"] == 50
        assert kwargs["max_workers"] == 4
        assert kwargs["summary_limit"] == 3
        return {
            "agent_name": "lance_full_cycle",
            "status": "OK",
            "session_banner": "MARKET_OPEN lance",
            "single_run_read": {"one_liner": "1 active monitor."},
            "decision_brief": {
                "ticker_slices": [
                    {
                        "ticker": "IBM",
                        "lane": "intraday",
                        "state": "triggered_reference",
                        "playbook": "mean_reversion",
                        "data": "price=100 confidence=OK",
                        "why": "Lance why.",
                        "watch": "hold level",
                        "risk": "lose level",
                    }
                ],
                "blocked": [{"ticker": "BAD"}],
            },
        }


class FakeSykesService:
    def run(self, **kwargs):
        assert kwargs["market"] == "us-listed"
        assert kwargs["market_limit"] == 50
        assert kwargs["max_workers"] == 4
        assert kwargs["summary_limit"] == 3
        return {
            "agent_name": "timothy_sykes",
            "status": "OK",
            "session_banner": "MARKET_OPEN sykes",
            "desk_read": {"one_liner": "1 intraday watch."},
            "auto_slices": [
                {
                    "ticker": "HOT",
                    "lane": "intraday",
                    "state": "primary_live_watch",
                    "setup": "catalyst_spiker_watch",
                    "data": "gap=12 confidence=OK",
                    "why": "Tim why.",
                    "watch": "verify catalyst",
                    "risk": "volume fades",
                }
            ],
            "blocked": [{"ticker": "CAVEAT"}],
        }
