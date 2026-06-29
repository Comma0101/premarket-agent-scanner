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
        data = self._preset_body(key, raw[key])
        return SmallCapScannerPreset(
            name=key,
            cap_tiers=self._string_list(data, key, "cap_tiers"),
            direction=data.get("direction", "up"),
            min_gap_abs=float(data.get("min_gap_abs", 5.0)),
            min_volume=_optional_float(data.get("min_volume")),
            min_rel_volume=_optional_float(data.get("min_rel_volume", 2.0)),
            include_low_confidence=bool(data.get("include_low_confidence", False)),
            missing_fields=self._string_list(data, key, "missing_fields"),
            notes=self._string_list(data, key, "notes"),
        )

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{self.path} must contain a mapping of preset names.")
        return loaded

    def _preset_body(self, name: str, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError(
                f"Preset '{name}' in {self.path} must be a mapping of preset fields."
            )
        return value

    def _string_list(
        self, data: dict[str, Any], preset_name: str, field_name: str
    ) -> list[str]:
        if field_name not in data:
            return []
        value = data[field_name]
        if not isinstance(value, list):
            raise ValueError(
                f"Preset '{preset_name}' field '{field_name}' in {self.path} "
                "must be a list."
            )
        return [str(item) for item in value]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
