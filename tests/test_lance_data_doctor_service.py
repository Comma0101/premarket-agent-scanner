from __future__ import annotations

from services.lance_data_doctor_service import LanceDataDoctorService


class FakeValidationService:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


def _validation_payload() -> dict:
    return {
        "agent_name": "market_validation",
        "status": "blocked",
        "session_mode": "MARKET_OPEN",
        "session_time_et": "Jul 3 10:15 AM ET",
        "ticker_count": 4,
        "ready_count": 1,
        "blocked_count": 3,
        "snapshot_checks": [
            {
                "ticker": "IBM",
                "readiness": "ready",
                "confidence": "OK",
                "gap_basis": "last_trade",
                "data_status": "live",
                "as_of_et": "Jul 3 10:15 AM ET",
                "blockers": [],
                "provider_failures": {},
            },
            {
                "ticker": "MU",
                "readiness": "blocked",
                "confidence": "ERROR",
                "gap_basis": None,
                "data_status": "provider_failure",
                "as_of_et": "Jul 3 10:15 AM ET",
                "blockers": [
                    "missing effective price",
                    "missing gap_basis",
                    "provider_failures present",
                ],
                "provider_failures": {"yfinance": "DNS failure"},
            },
            {
                "ticker": "AAOI",
                "readiness": "blocked",
                "confidence": "STALE_DATA",
                "gap_basis": "last_trade",
                "data_status": "stale",
                "as_of_et": "Jul 2 4:00 PM ET",
                "blockers": ["data_status=stale", "confidence=STALE_DATA"],
                "provider_failures": {},
            },
            {
                "ticker": "HALT",
                "readiness": "blocked",
                "confidence": "OK",
                "gap_basis": "premarket",
                "data_status": "live",
                "as_of_et": "Jul 3 10:15 AM ET",
                "blockers": ["halt_status=HALTED"],
                "provider_failures": {},
            },
        ],
        "notes": [],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_data_doctor_groups_root_causes_and_next_actions():
    service = FakeValidationService(_validation_payload())

    output = LanceDataDoctorService(validation_service=service).diagnose(
        tickers="IBM,MU,AAOI,HALT",
        max_candidates=4,
        now="2026-07-03T14:15:00Z",
    )

    assert service.calls == [{
        "tickers": "IBM,MU,AAOI,HALT",
        "max_candidates": 4,
        "persist": False,
        "summary_limit": 4,
        "review_limit": 10,
        "max_workers": 1,
        "now": "2026-07-03T14:15:00Z",
    }]
    assert output["agent_name"] == "lance_data_doctor"
    assert output["mode"] == "data_doctor"
    assert output["status"] == "blocked"
    assert output["doctor_read"]["one_liner"] == (
        "1 ready, 3 blocked. Main blockers: provider_failure=1, stale_or_off_session=1, halted=1."
    )
    assert output["root_causes"]["ready"] == ["IBM"]
    assert output["root_causes"]["provider_failure"] == ["MU"]
    assert output["root_causes"]["missing_price"] == ["MU"]
    assert output["root_causes"]["stale_or_off_session"] == ["AAOI"]
    assert output["root_causes"]["halted"] == ["HALT"]
    assert any("provider connectivity" in action for action in output["next_actions"])
    assert any("stale/off-session" in action for action in output["next_actions"])
    assert output["validation"]["status"] == "blocked"


def test_lance_data_doctor_builds_from_signal_quality_without_network():
    output = LanceDataDoctorService.from_signal_quality([
        {
            "ticker": "IBM",
            "confidence": "OK",
            "gap_basis": "premarket",
            "data_status": "live",
            "as_of_et": "Jul 3 10:15 AM ET",
        },
        {
            "ticker": "MU",
            "confidence": "ERROR",
            "gap_basis": None,
            "data_status": "provider_failure",
            "as_of_et": "Jul 3 10:15 AM ET",
        },
    ])

    assert output["status"] == "blocked"
    assert output["root_causes"]["ready"] == ["IBM"]
    assert output["root_causes"]["provider_failure"] == ["MU"]
    assert output["doctor_read"]["one_liner"].startswith("1 ready, 1 blocked")
