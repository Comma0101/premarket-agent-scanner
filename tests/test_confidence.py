from app.models import CombinedSnapshot, ProviderPriceData
from services.confidence import determine_confidence


def snap(yf_price=101, alpaca_price=101, prev=100):
    yf = ProviderPriceData("A", "yfinance", previous_close=prev, premarket_price=yf_price, volume=100, timestamp="2099-01-01T00:00:00+00:00")
    ap = ProviderPriceData("A", "alpaca", previous_close=prev, premarket_price=alpaca_price, volume=100, timestamp="2099-01-01T00:00:00+00:00")
    return CombinedSnapshot("A", "2099-01-01T00:00:00+00:00", prev, yf_price, yf_price, None, None, None, 100, "yfinance", "alpaca", "OK", yfinance_data=yf, alpaca_data=ap)


def test_ok_when_sources_align():
    assert determine_confidence(snapshot=snap(), market_cap=100) == "OK"


def test_conflict_when_sources_disagree():
    assert determine_confidence(snapshot=snap(yf_price=101, alpaca_price=110), market_cap=100) == "CONFLICT"


def test_low_confidence_one_source():
    s = snap()
    s.alpaca_data = None
    assert determine_confidence(snapshot=s, market_cap=100) == "LOW_CONFIDENCE"


def test_missing_market_cap():
    assert determine_confidence(snapshot=snap(), market_cap=None) == "MISSING_MARKET_CAP"
