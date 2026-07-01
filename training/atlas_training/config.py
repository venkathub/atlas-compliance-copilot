"""Typed, fail-fast loader for the pinned QLoRA run config (the reproducibility contract).

`load(path) -> RunConfig` parses a committed `configs/qlora_*.yaml` and validates that every
field required to *reproduce an adapter from committed config* is present and well-typed. Any
unpinned/missing required field raises `ConfigError` naming the offending field — this is the
guard behind DoD item 1 ("a fine-tune run is reproducible from committed config").

Pure stdlib + PyYAML. Imports no torch/transformers, so it (and its tests) run GPU-free in CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Allowed enum-like values pinned by ADR-0069 (QLoRA 4-bit NF4).
_QUANT_TYPES = {"nf4", "fp4"}
_COMPUTE_DTYPES = {"bfloat16", "float16", "float32"}
_EARLY_STOP_METRICS = {"eval_loss", "loss"}


class ConfigError(ValueError):
    """Raised when the run config is missing or has an unpinned/invalid required field."""


@dataclass(frozen=True)
class QuantConfig:
    load_in_4bit: bool
    bnb_4bit_quant_type: str
    bnb_4bit_compute_dtype: str
    double_quant: bool


@dataclass(frozen=True)
class LoraConfig:
    r: int
    alpha: int
    dropout: float
    target_modules: tuple[str, ...]


@dataclass(frozen=True)
class TrainConfig:
    epochs: int
    lr: float
    batch_size: int
    grad_accum: int
    max_seq_len: int
    seed: int


@dataclass(frozen=True)
class EarlyStopping:
    metric: str
    patience: int
    min_delta: float


@dataclass(frozen=True)
class DatasetRefs:
    manifest: str
    train: str
    val: str


@dataclass(frozen=True)
class MlflowConfig:
    experiment: str
    run_name: str
    register_as: str


@dataclass(frozen=True)
class RunConfig:
    base_model: str
    quant: QuantConfig
    lora: LoraConfig
    train: TrainConfig
    early_stopping: EarlyStopping
    dataset: DatasetRefs
    mlflow: MlflowConfig

    @property
    def seed(self) -> int:
        """The single pinned seed; surfaced at top level for convenient plumbing."""
        return self.train.seed


# ── validation helpers ────────────────────────────────────────────────────────────────────────


def _require(mapping: Any, key: str, where: str) -> Any:
    if not isinstance(mapping, dict):
        raise ConfigError(f"'{where}' must be a mapping, got {type(mapping).__name__}")
    if key not in mapping or mapping[key] is None:
        raise ConfigError(f"missing required field: '{where}.{key}'" if where else
                          f"missing required field: '{key}'")
    return mapping[key]


def _require_type(value: Any, types: type | tuple[type, ...], field: str) -> Any:
    # bool is a subclass of int — guard against silently accepting True for an int field.
    if isinstance(types, type):
        types = (types,)
    if bool not in types and isinstance(value, bool):
        raise ConfigError(f"field '{field}' must be {types[0].__name__}, got bool")
    if not isinstance(value, types):
        names = "/".join(t.__name__ for t in types)
        raise ConfigError(f"field '{field}' must be {names}, got {type(value).__name__}")
    return value


def _require_choice(value: Any, allowed: set[str], field: str) -> str:
    if value not in allowed:
        raise ConfigError(f"field '{field}'='{value}' not in allowed {sorted(allowed)}")
    return value


def _quant(raw: Any) -> QuantConfig:
    return QuantConfig(
        load_in_4bit=_require_type(_require(raw, "load_in_4bit", "quant"), bool,
                                   "quant.load_in_4bit"),
        bnb_4bit_quant_type=_require_choice(
            _require(raw, "bnb_4bit_quant_type", "quant"), _QUANT_TYPES,
            "quant.bnb_4bit_quant_type"),
        bnb_4bit_compute_dtype=_require_choice(
            _require(raw, "bnb_4bit_compute_dtype", "quant"), _COMPUTE_DTYPES,
            "quant.bnb_4bit_compute_dtype"),
        double_quant=_require_type(_require(raw, "double_quant", "quant"), bool,
                                   "quant.double_quant"),
    )


def _lora(raw: Any) -> LoraConfig:
    modules = _require(raw, "target_modules", "lora")
    if not isinstance(modules, list) or not modules or not all(isinstance(m, str) for m in modules):
        raise ConfigError("field 'lora.target_modules' must be a non-empty list of strings")
    return LoraConfig(
        r=_require_type(_require(raw, "r", "lora"), int, "lora.r"),
        alpha=_require_type(_require(raw, "alpha", "lora"), int, "lora.alpha"),
        dropout=_require_type(_require(raw, "dropout", "lora"), (int, float), "lora.dropout"),
        target_modules=tuple(modules),
    )


def _train(raw: Any) -> TrainConfig:
    return TrainConfig(
        epochs=_require_type(_require(raw, "epochs", "train"), int, "train.epochs"),
        lr=_require_type(_require(raw, "lr", "train"), (int, float), "train.lr"),
        batch_size=_require_type(_require(raw, "batch_size", "train"), int, "train.batch_size"),
        grad_accum=_require_type(_require(raw, "grad_accum", "train"), int, "train.grad_accum"),
        max_seq_len=_require_type(_require(raw, "max_seq_len", "train"), int, "train.max_seq_len"),
        seed=_require_type(_require(raw, "seed", "train"), int, "train.seed"),
    )


def _early_stopping(raw: Any) -> EarlyStopping:
    return EarlyStopping(
        metric=_require_choice(_require(raw, "metric", "early_stopping"), _EARLY_STOP_METRICS,
                               "early_stopping.metric"),
        patience=_require_type(_require(raw, "patience", "early_stopping"), int,
                               "early_stopping.patience"),
        min_delta=_require_type(_require(raw, "min_delta", "early_stopping"), (int, float),
                                "early_stopping.min_delta"),
    )


def _dataset(raw: Any) -> DatasetRefs:
    return DatasetRefs(
        manifest=_require_type(_require(raw, "manifest", "dataset"), str, "dataset.manifest"),
        train=_require_type(_require(raw, "train", "dataset"), str, "dataset.train"),
        val=_require_type(_require(raw, "val", "dataset"), str, "dataset.val"),
    )


def _mlflow(raw: Any) -> MlflowConfig:
    return MlflowConfig(
        experiment=_require_type(_require(raw, "experiment", "mlflow"), str, "mlflow.experiment"),
        run_name=_require_type(_require(raw, "run_name", "mlflow"), str, "mlflow.run_name"),
        register_as=_require_type(
            _require(raw, "register_as", "mlflow"), str, "mlflow.register_as"),
    )


def load(path: str | Path) -> RunConfig:
    """Load + validate a pinned run config. Raises ConfigError on any unpinned required field."""
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"run config not found: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - exercised via malformed-yaml test
        raise ConfigError(f"invalid YAML in {p}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"run config {p} must be a mapping at top level")

    base_model = _require_type(_require(raw, "base_model", ""), str, "base_model")
    if not base_model.strip():
        raise ConfigError("field 'base_model' must be a non-empty string")

    return RunConfig(
        base_model=base_model,
        quant=_quant(_require(raw, "quant", "")),
        lora=_lora(_require(raw, "lora", "")),
        train=_train(_require(raw, "train", "")),
        early_stopping=_early_stopping(_require(raw, "early_stopping", "")),
        dataset=_dataset(_require(raw, "dataset", "")),
        mlflow=_mlflow(_require(raw, "mlflow", "")),
    )
