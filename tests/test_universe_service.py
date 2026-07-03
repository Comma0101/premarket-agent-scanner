from services.universe_service import UniverseService


def test_curated_ai_and_active_universes_include_requested_traders_list() -> None:
    service = UniverseService()

    universes = service.list_universes()
    watchlists = service.list_watchlists()

    assert {"AI_SEMIS_MEMORY", "AI_INFRA_POWER", "SPECULATIVE_ACTIVE", "THEME_ETFS_MACRO"} <= set(
        universes
    )
    assert "HOT_ACTIVE" in watchlists

    hot_active = set(watchlists["HOT_ACTIVE"])
    assert {"MRVL", "HOOD", "SPCX", "ARM", "MU"} <= hot_active
    assert {"PLTR", "COIN", "MSTR"}.isdisjoint(hot_active)

    assert {"MRVL", "ARM", "MU"} <= set(universes["AI_SEMIS_MEMORY"])
    assert {"SMCI", "DELL", "CRWV", "CEG", "GEV", "OKLO"} <= set(universes["AI_INFRA_POWER"])
    assert {"PLTR", "COIN", "MSTR"} <= set(universes["SPECULATIVE_ACTIVE"])
    assert {"SPY", "QQQ", "TQQQ", "SMH", "DRAM"} <= set(universes["THEME_ETFS_MACRO"])


def test_hot_active_watchlist_resolves_membership_without_market_data() -> None:
    selection = UniverseService().resolve_selection(watchlist="HOT_ACTIVE")

    assert {"HOOD", "SPCX", "MRVL"} <= set(selection.tickers)
    assert "WATCHLIST:HOT_ACTIVE" in selection.memberships["HOOD"]
    assert "WATCHLIST:HOT_ACTIVE" in selection.memberships["SPCX"]
    assert selection.label == "WATCHLIST:HOT_ACTIVE"
