"""Unit tests for the promotion-floors loader/validator (P7 Task 1)."""

import json

import pytest

from atlas_evals.promotion_floors import (
    DEFAULT_PATH,
    FloorConfigError,
    PromotionFloors,
    load_floors,
)


def _valid_config() -> dict:
    return {
        "faithfulness": {"abs_floor": 0.656, "max_regression_vs_base": 0.05, "mode": "hybrid"},
        "format_validity": {"abs_floor": 0.95},
        "refusal_correctness": {"min_delta_vs_base": 0.0},
        "cost": {"max_regression_pct_vs_base": 10.0},
        "block_reason_required": True,
    }


def _write(tmp_path, cfg) -> object:
    p = tmp_path / "promotion-floors.json"
    p.write_text(json.dumps(cfg))
    return p


def test_committed_config_loads_and_validates():
    floors = load_floors(DEFAULT_PATH)
    assert isinstance(floors, PromotionFloors)
    assert floors.faithfulness.abs_floor == 0.656
    assert floors.faithfulness.mode == "hybrid"
    assert floors.format_validity.abs_floor == 0.95
    assert floors.block_reason_required is True


def test_round_trip(tmp_path):
    cfg = _valid_config()
    floors = load_floors(_write(tmp_path, cfg))
    assert floors.to_json()["faithfulness"]["mode"] == "hybrid"
    assert floors.cost.max_regression_pct_vs_base == 10.0


def test_missing_faithfulness_block_rejected(tmp_path):
    cfg = _valid_config()
    del cfg["faithfulness"]
    with pytest.raises(FloorConfigError, match="faithfulness"):
        load_floors(_write(tmp_path, cfg))


def test_missing_format_block_rejected(tmp_path):
    cfg = _valid_config()
    del cfg["format_validity"]
    with pytest.raises(FloorConfigError, match="format_validity"):
        load_floors(_write(tmp_path, cfg))


def test_invalid_mode_rejected(tmp_path):
    cfg = _valid_config()
    cfg["faithfulness"]["mode"] = "yolo"
    with pytest.raises(FloorConfigError, match="mode"):
        load_floors(_write(tmp_path, cfg))


def test_missing_abs_floor_rejected(tmp_path):
    cfg = _valid_config()
    del cfg["faithfulness"]["abs_floor"]
    with pytest.raises(FloorConfigError, match="malformed block"):
        load_floors(_write(tmp_path, cfg))


def test_out_of_range_floor_rejected(tmp_path):
    cfg = _valid_config()
    cfg["format_validity"]["abs_floor"] = 1.5
    with pytest.raises(FloorConfigError, match="out of range"):
        load_floors(_write(tmp_path, cfg))


def test_negative_cost_band_rejected(tmp_path):
    cfg = _valid_config()
    cfg["cost"]["max_regression_pct_vs_base"] = -5.0
    with pytest.raises(FloorConfigError, match="must be >= 0"):
        load_floors(_write(tmp_path, cfg))


def test_non_numeric_floor_rejected(tmp_path):
    cfg = _valid_config()
    cfg["faithfulness"]["abs_floor"] = "high"
    with pytest.raises(FloorConfigError, match="expected a number"):
        load_floors(_write(tmp_path, cfg))


def test_bool_is_not_a_number(tmp_path):
    cfg = _valid_config()
    cfg["faithfulness"]["abs_floor"] = True
    with pytest.raises(FloorConfigError, match="expected a number"):
        load_floors(_write(tmp_path, cfg))


def test_missing_file_rejected(tmp_path):
    with pytest.raises(FloorConfigError, match="not found"):
        load_floors(tmp_path / "nope.json")
