from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import BASE_DIR


def _dedupe_tickers(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for ticker in tickers:
        normalized = ticker.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _load_simple_yaml_mapping(path: Path) -> dict[str, list[str]]:
    try:
        import yaml

        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except ImportError:
        raw = _parse_simple_yaml(path)

    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a mapping of names to ticker lists.")

    output: dict[str, list[str]] = {}
    for name, tickers in raw.items():
        if tickers is None:
            output[str(name)] = []
            continue
        if not isinstance(tickers, list):
            raise ValueError(f"{path}:{name} must be a list of tickers.")
        output[str(name)] = _dedupe_tickers([str(ticker) for ticker in tickers])
    return output


def _parse_simple_yaml(path: Path) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    current_key: str | None = None
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if not line.startswith(" ") and line.endswith(":"):
                current_key = line[:-1].strip()
                output[current_key] = []
                continue
            if current_key and line.lstrip().startswith("- "):
                output[current_key].append(line.lstrip()[2:].strip())
                continue
            raise ValueError(f"Unsupported YAML shape in {path}: {raw_line.rstrip()}")
    return output


@dataclass
class UniverseSelection:
    tickers: list[str]
    memberships: dict[str, list[str]]
    label: str | None


class UniverseService:
    def __init__(
        self,
        universes_path: Path | None = None,
        watchlists_path: Path | None = None,
    ) -> None:
        self.universes_path = universes_path or BASE_DIR / "data" / "universes.yaml"
        self.watchlists_path = watchlists_path or BASE_DIR / "data" / "watchlists.yaml"

    def load_universes(self) -> dict[str, list[str]]:
        return _load_simple_yaml_mapping(self.universes_path)

    def load_watchlists(self) -> dict[str, list[str]]:
        if not self.watchlists_path.exists():
            return {}
        return _load_simple_yaml_mapping(self.watchlists_path)

    def list_universes(self) -> dict[str, list[str]]:
        return self.load_universes()

    def list_watchlists(self) -> dict[str, list[str]]:
        return self.load_watchlists()

    def get_universe(self, name: str) -> list[str]:
        universes = self.load_universes()
        key = name.upper()
        if key not in universes:
            raise KeyError(f"Unknown universe: {name}")
        return universes[key]

    def get_watchlist(self, name: str) -> list[str]:
        watchlists = self.load_watchlists()
        key = name.upper()
        if key not in watchlists:
            raise KeyError(f"Unknown watchlist: {name}")
        return watchlists[key]

    def memberships_for_ticker(self, ticker: str) -> list[str]:
        normalized = ticker.upper()
        memberships: list[str] = []
        for name, tickers in self.load_universes().items():
            if normalized in tickers:
                memberships.append(name)
        for name, tickers in self.load_watchlists().items():
            if normalized in tickers:
                memberships.append(f"WATCHLIST:{name}")
        return memberships

    def resolve_selection(
        self,
        *,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        tickers: list[str] | str | None = None,
        all_universes: bool = False,
    ) -> UniverseSelection:
        memberships: dict[str, list[str]] = {}
        selected: list[str] = []
        labels: list[str] = []

        universes = self.load_universes()
        watchlists = self.load_watchlists()

        universe_names = _coerce_names(universe)
        watchlist_names = _coerce_names(watchlist)

        if all_universes:
            universe_names = list(universes.keys())

        for name in universe_names:
            key = name.upper()
            if key not in universes:
                raise KeyError(f"Unknown universe: {name}")
            labels.append(key)
            for ticker in universes[key]:
                selected.append(ticker)
                memberships.setdefault(ticker, []).append(key)

        for name in watchlist_names:
            key = name.upper()
            if key not in watchlists:
                raise KeyError(f"Unknown watchlist: {name}")
            label = f"WATCHLIST:{key}"
            labels.append(label)
            for ticker in watchlists[key]:
                selected.append(ticker)
                memberships.setdefault(ticker, []).append(label)

        for ticker in _coerce_tickers(tickers):
            selected.append(ticker)
            memberships.setdefault(ticker, []).append("MANUAL")

        selected = _dedupe_tickers(selected)
        for ticker in selected:
            memberships.setdefault(ticker, [])

        label = ",".join(labels) if labels else None
        return UniverseSelection(tickers=selected, memberships=memberships, label=label)


def _coerce_names(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_tickers(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _dedupe_tickers([item for item in value.split(",")])
    return _dedupe_tickers([str(item) for item in value])
