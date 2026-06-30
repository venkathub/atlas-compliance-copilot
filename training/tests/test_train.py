"""Offline, GPU-free unit tests for train.py config->kwargs wiring (P6 Task 8).

Only the pure helpers are exercised — torch/transformers/peft/trl are never imported (they live
inside run_training, the GPU-window orchestrator). Proves the pinned config plumbs through to the
quantization/LoRA/SFT/early-stopping kwargs and the dataset/loss helpers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_training.config import load
from atlas_training.train import (
    early_stopping_kwargs,
    example_to_messages,
    extract_losses,
    load_chat_rows,
    lora_kwargs,
    quantization_kwargs,
    sft_kwargs,
)

CONFIGS = Path(__file__).resolve().parent.parent / "configs"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def config():
    return load(CONFIGS / "qlora_qwen7b.yaml")


@pytest.fixture
def smoke():
    return load(CONFIGS / "qlora_qwen3b_smoke.yaml")


# ── kwargs builders ──────────────────────────────────────────────────────────────────────────────


def test_quantization_kwargs(config):
    q = quantization_kwargs(config)
    assert q["load_in_4bit"] is True
    assert q["bnb_4bit_quant_type"] == "nf4"
    assert q["bnb_4bit_compute_dtype"] == "bfloat16"  # name, not a torch dtype (no torch import)
    assert q["bnb_4bit_use_double_quant"] is True


def test_lora_kwargs(config):
    lo = lora_kwargs(config)
    assert lo["r"] == 16
    assert lo["lora_alpha"] == 32
    assert lo["lora_dropout"] == 0.05
    assert "q_proj" in lo["target_modules"] and "down_proj" in lo["target_modules"]
    assert lo["task_type"] == "CAUSAL_LM"
    assert lo["bias"] == "none"


def test_sft_kwargs(config, tmp_path):
    s = sft_kwargs(config, tmp_path / "out")
    assert s["num_train_epochs"] == 3
    assert s["learning_rate"] == pytest.approx(2.0e-4)
    assert s["per_device_train_batch_size"] == 4
    assert s["gradient_accumulation_steps"] == 4
    assert s["max_length"] == 2048
    assert s["seed"] == 42
    # early stopping needs per-epoch eval + load-best on eval_loss (lower is better)
    assert s["eval_strategy"] == "epoch"
    assert s["save_strategy"] == "epoch"
    assert s["load_best_model_at_end"] is True
    assert s["metric_for_best_model"] == "eval_loss"
    assert s["greater_is_better"] is False
    assert s["output_dir"] == str(tmp_path / "out")
    assert s["report_to"] == []


def test_sft_kwargs_smoke_differs(smoke, tmp_path):
    s = sft_kwargs(smoke, tmp_path)
    assert s["num_train_epochs"] == 1
    assert s["max_length"] == 1024


def test_early_stopping_kwargs(config):
    es = early_stopping_kwargs(config)
    assert es["early_stopping_patience"] == 2
    assert es["early_stopping_threshold"] == 0.005


# ── dataset + loss helpers ────────────────────────────────────────────────────────────────────


def test_example_to_messages():
    ex = {
        "messages": [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "U"},
            {"role": "assistant", "content": "A"},
        ],
        "label": "answer",
        "provenance_ref": "x",
    }
    row = example_to_messages(ex)
    assert list(row) == ["messages"]  # only the chat column is kept
    assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]


def test_load_chat_rows_from_committed_split():
    rows = load_chat_rows(DATA_DIR / "train.jsonl")
    assert rows, "committed train.jsonl is empty"
    for r in rows:
        assert set(r) == {"messages"}
        assert r["messages"][0]["role"] == "system"


@pytest.mark.parametrize(
    "logs,expected",
    [
        ({"loss": 2.5}, (2.5, None)),
        ({"eval_loss": 1.8}, (None, 1.8)),
        ({"loss": 2.0, "eval_loss": 1.5}, (2.0, 1.5)),
        ({"learning_rate": 1e-4}, (None, None)),
        ({}, (None, None)),
    ],
)
def test_extract_losses(logs, expected):
    assert extract_losses(logs) == expected
