"""Offline, GPU-free unit tests for the pinned run-config loader (P6 Task 1).

Covers: both committed YAML configs round-trip; the loader fails fast (ConfigError) on every
unpinned/missing/ill-typed required field; seed plumbing is surfaced. No torch, network, or GPU.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml

from atlas_training.config import ConfigError, RunConfig, load

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"
PROD = CONFIGS_DIR / "qlora_qwen7b.yaml"
SMOKE = CONFIGS_DIR / "qlora_qwen3b_smoke.yaml"


# ── committed configs load & round-trip ─────────────────────────────────────────────────────────


def test_prod_config_loads_and_pins_expected_values():
    cfg = load(PROD)
    assert isinstance(cfg, RunConfig)
    assert cfg.base_model == "Qwen/Qwen2.5-7B-Instruct"
    assert cfg.quant.load_in_4bit is True
    assert cfg.quant.bnb_4bit_quant_type == "nf4"
    assert cfg.quant.bnb_4bit_compute_dtype == "bfloat16"
    assert cfg.quant.double_quant is True
    assert cfg.lora.r == 16
    assert cfg.lora.alpha == 32
    assert "q_proj" in cfg.lora.target_modules
    assert cfg.train.seed == 42
    assert cfg.early_stopping.metric == "eval_loss"
    assert cfg.dataset.manifest == "data/manifest.json"
    assert cfg.mlflow.register_as == "atlas-citation-adapter"


def test_smoke_config_loads_with_3b_base():
    cfg = load(SMOKE)
    assert cfg.base_model == "Qwen/Qwen2.5-3B-Instruct"
    assert cfg.train.epochs == 1
    # Same schema/contract as prod — exercises the identical validation path.
    assert cfg.train.seed == 42


def test_seed_surfaced_at_top_level():
    cfg = load(PROD)
    assert cfg.seed == cfg.train.seed == 42


def test_runconfig_is_frozen():
    cfg = load(PROD)
    with pytest.raises(FrozenInstanceError):
        cfg.base_model = "other"  # type: ignore[misc]


# ── fail-fast on missing/unpinned/invalid fields ────────────────────────────────────────────────


@pytest.fixture
def valid_raw() -> dict:
    return yaml.safe_load(PROD.read_text(encoding="utf-8"))


def _write(tmp_path: Path, raw: dict) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return p


def test_missing_file_raises():
    with pytest.raises(ConfigError, match="not found"):
        load("/no/such/config.yaml")


def test_non_mapping_top_level_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping at top level"):
        load(p)


@pytest.mark.parametrize(
    "field",
    ["base_model", "quant", "lora", "train", "early_stopping", "dataset", "mlflow"],
)
def test_missing_top_level_field_raises(tmp_path, valid_raw, field):
    valid_raw.pop(field)
    with pytest.raises(ConfigError, match=f"'{field}'"):
        load(_write(tmp_path, valid_raw))


def test_missing_seed_raises(tmp_path, valid_raw):
    valid_raw["train"].pop("seed")
    with pytest.raises(ConfigError, match="train.seed"):
        load(_write(tmp_path, valid_raw))


def test_missing_quant_param_raises(tmp_path, valid_raw):
    valid_raw["quant"].pop("bnb_4bit_quant_type")
    with pytest.raises(ConfigError, match="quant.bnb_4bit_quant_type"):
        load(_write(tmp_path, valid_raw))


def test_invalid_quant_type_raises(tmp_path, valid_raw):
    valid_raw["quant"]["bnb_4bit_quant_type"] = "int8"
    with pytest.raises(ConfigError, match="bnb_4bit_quant_type"):
        load(_write(tmp_path, valid_raw))


def test_invalid_compute_dtype_raises(tmp_path, valid_raw):
    valid_raw["quant"]["bnb_4bit_compute_dtype"] = "int4"
    with pytest.raises(ConfigError, match="bnb_4bit_compute_dtype"):
        load(_write(tmp_path, valid_raw))


def test_empty_base_model_raises(tmp_path, valid_raw):
    valid_raw["base_model"] = "   "
    with pytest.raises(ConfigError, match="base_model"):
        load(_write(tmp_path, valid_raw))


def test_bool_for_int_field_rejected(tmp_path, valid_raw):
    valid_raw["train"]["seed"] = True  # bool must not pass as int
    with pytest.raises(ConfigError, match="train.seed"):
        load(_write(tmp_path, valid_raw))


def test_seed_wrong_type_raises(tmp_path, valid_raw):
    valid_raw["train"]["seed"] = "42"
    with pytest.raises(ConfigError, match="train.seed"):
        load(_write(tmp_path, valid_raw))


def test_empty_target_modules_raises(tmp_path, valid_raw):
    valid_raw["lora"]["target_modules"] = []
    with pytest.raises(ConfigError, match="target_modules"):
        load(_write(tmp_path, valid_raw))


def test_missing_dataset_ref_raises(tmp_path, valid_raw):
    valid_raw["dataset"].pop("val")
    with pytest.raises(ConfigError, match="dataset.val"):
        load(_write(tmp_path, valid_raw))


def test_invalid_early_stopping_metric_raises(tmp_path, valid_raw):
    valid_raw["early_stopping"]["metric"] = "accuracy"
    with pytest.raises(ConfigError, match="early_stopping.metric"):
        load(_write(tmp_path, valid_raw))
