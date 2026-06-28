from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config import BASE_DIR
from app.models import SmallCapScannerPreset


class PresetService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or BASE_DIR / "data" / "scanner_presets.yaml"

    def list_presets(self) -> list[str]:
        return sorted(self._load().keys())

    def get_preset(self, name: str) -> SmallCapScannerPreset:
        raw = self._load()
        key = name.strip()
        if key not in raw:
            valid = ", ".join(sorted(raw)) or "(none)"
            raise KeyError(f"Unknown scanner preset: {name}. Valid presets: {valid}.")
        data = raw[key] or {}
        return SmallCapScannerPreset(
            name=key,
            cap_tiers=[str(item) for item in data.get("cap_tiers", [])],
            direction=data.get("direction", "up"),
            min_gap_abs=float(data.get("min_gap_abs", 5.0)),
            min_volume=_optional_float(data.get("min_volume")),
            min_rel_volume=_optional_float(data.get("min_rel_volume", 2.0)),
            include_low_confidence=bool(data.get("include_low_confidence", False)),
            missing_fields=[str(item) for item in data.get("missing_fields", [])],
            notes=[str(item) for item in data.get("notes", [])],
        )

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{self.path} must contain a mapping of preset names.")
        return loaded


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
