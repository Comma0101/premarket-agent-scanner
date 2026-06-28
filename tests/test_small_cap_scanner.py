from __future__ import annotations

from pathlib import Path

import pytest

from services.scanner_preset_service import PresetService


def test_load_sykes_small_cap_preset():
    service = PresetService()
    preset = service.get_preset("sykes_small_cap_v0")

    assert preset.name == "sykes_small_cap_v0"
    assert preset.cap_tiers == ["nano", "micro", "small"]
    assert preset.direction == "up"
    assert preset.min_gap_abs == 5.0
    assert preset.min_rel_volume == 2.0
    assert preset.include_low_confidence is False
    assert "float" in preset.missing_fields
    assert "catalyst" in preset.missing_fields


def test_unknown_preset_lists_valid_names(tmp_path: Path):
    path = tmp_path / "scanner_presets.yaml"
    path.write_text(
        "example:\n"
        "  cap_tiers: [small]\n"
        "  direction: up\n"
        "  min_gap_abs: 5\n",
        encoding="utf-8",
    )
    service = PresetService(path)

    with pytest.raises(KeyError) as exc:
        service.get_preset("missing")

    assert "example" in str(exc.value)


def test_preset_body_must_be_mapping(tmp_path: Path):
    path = tmp_path / "scanner_presets.yaml"
    path.write_text("bad: 1\n", encoding="utf-8")
    service = PresetService(path)

    with pytest.raises(ValueError, match="Preset 'bad'.*mapping"):
        service.get_preset("bad")


def test_cap_tiers_must_be_list(tmp_path: Path):
    path = tmp_path / "scanner_presets.yaml"
    path.write_text(
        "bad:\n"
        "  cap_tiers: small\n",
        encoding="utf-8",
    )
    service = PresetService(path)

    with pytest.raises(ValueError, match="Preset 'bad' field 'cap_tiers'.*list"):
        service.get_preset("bad")


@pytest.mark.parametrize("field", ["missing_fields", "notes"])
def test_string_list_fields_must_be_lists(tmp_path: Path, field: str):
    path = tmp_path / "scanner_presets.yaml"
    path.write_text(
        "bad:\n"
        "  cap_tiers: [small]\n"
        f"  {field}: scalar\n",
        encoding="utf-8",
    )
    service = PresetService(path)

    with pytest.raises(ValueError, match=f"Preset 'bad' field '{field}'.*list"):
        service.get_preset("bad")
