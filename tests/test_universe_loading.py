from pathlib import Path
import pytest
from services.universe_service import UniverseService


def write(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def svc(tmp_path):
    u = tmp_path / "universes.yaml"
    w = tmp_path / "watchlists.yaml"
    write(u, "A:\n  - msft\n  - MSFT\n  - nvda\nB:\n  - amd\n")
    write(w, "W:\n  - amat\n")
    return UniverseService(u, w)


def test_loads_yaml_universe(tmp_path):
    assert svc(tmp_path).get_universe("A") == ["MSFT", "NVDA"]


def test_handles_duplicate_tickers(tmp_path):
    assert len(svc(tmp_path).get_universe("A")) == 2


def test_unknown_universe(tmp_path):
    with pytest.raises(KeyError):
        svc(tmp_path).get_universe("Z")


def test_merges_multiple_universes(tmp_path):
    sel = svc(tmp_path).resolve_selection(universe=["A", "B"])
    assert sel.tickers == ["MSFT", "NVDA", "AMD"]
