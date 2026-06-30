"""QLoRA SFT fine-tune (PEFT/TRL `SFTTrainer`) driven by the pinned run config (ADR-0069).

Split so the **reproducibility wiring** (config -> quantization / LoRA / SFT / early-stopping
kwargs,
dataset formatting, loss parsing) is pure stdlib and unit-tested GPU-free, while the heavy training
(`torch`/`transformers`/`peft`/`trl`/`bitsandbytes`) is lazily imported inside `run_training` and
only ever executes in the episodic GPU window. CI installs none of the `train` group, so importing
this module — and testing the wiring — never needs a GPU.

Flow (GPU window): build 4-bit NF4 base + LoRA -> load chat SFT train/val -> SFTTrainer with
early stopping on eval_loss -> stream train/val loss to MLflow (tracking.py) -> save adapter.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas_training.config import RunConfig, load

# ── pure config -> kwargs wiring (unit-tested, no torch) ──────────────────────────────────────────


def quantization_kwargs(config: RunConfig) -> dict[str, Any]:
    """BitsAndBytesConfig kwargs. `compute_dtype` stays a NAME here; resolved to a torch dtype in
    the heavy path (`_resolve_dtype`) so this function imports no torch."""
    q = config.quant
    return {
        "load_in_4bit": q.load_in_4bit,
        "bnb_4bit_quant_type": q.bnb_4bit_quant_type,
        "bnb_4bit_compute_dtype": q.bnb_4bit_compute_dtype,  # name, e.g. "bfloat16"
        "bnb_4bit_use_double_quant": q.double_quant,
    }


def lora_kwargs(config: RunConfig) -> dict[str, Any]:
    """PEFT LoraConfig kwargs from the pinned config."""
    lo = config.lora
    return {
        "r": lo.r,
        "lora_alpha": lo.alpha,
        "lora_dropout": lo.dropout,
        "target_modules": list(lo.target_modules),
        "bias": "none",
        "task_type": "CAUSAL_LM",
    }


def sft_kwargs(config: RunConfig, output_dir: str | Path) -> dict[str, Any]:
    """TRL SFTConfig kwargs. Early stopping needs eval each epoch + load-best-at-end on eval_loss.

    Uses `max_length` (current TRL ≥0.12; the older `max_seq_length` was renamed — confirmed on the
    box, which rejected `max_seq_length`).
    """
    tr = config.train
    return {
        "output_dir": str(output_dir),
        "num_train_epochs": tr.epochs,
        "learning_rate": tr.lr,
        "per_device_train_batch_size": tr.batch_size,
        "per_device_eval_batch_size": tr.batch_size,
        "gradient_accumulation_steps": tr.grad_accum,
        "max_length": tr.max_seq_len,
        "seed": tr.seed,
        "eval_strategy": "epoch",
        "save_strategy": "epoch",
        "logging_steps": 1,
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "report_to": [],  # MLflow logging is driven explicitly via tracking.py, not the autologger
    }


def early_stopping_kwargs(config: RunConfig) -> dict[str, Any]:
    """transformers EarlyStoppingCallback kwargs from the pinned early_stopping block."""
    es = config.early_stopping
    return {
        "early_stopping_patience": es.patience,
        "early_stopping_threshold": es.min_delta,
    }


def example_to_messages(example: dict) -> dict[str, Any]:
    """Map a committed SFTExample row to the trainer's chat row (`{"messages": [...]}`)."""
    return {"messages": [dict(m) for m in example["messages"]]}


def load_chat_rows(path: str | Path) -> list[dict]:
    """Read an SFT jsonl (builder output) into trainer chat rows."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(example_to_messages(json.loads(line)))
    return rows


def extract_losses(logs: dict) -> tuple[float | None, float | None]:
    """Parse a HF Trainer `on_log` dict into (train_loss, eval_loss); either may be absent."""
    train_loss = logs.get("loss")
    eval_loss = logs.get("eval_loss")
    return (
        float(train_loss) if train_loss is not None else None,
        float(eval_loss) if eval_loss is not None else None,
    )


@dataclass(frozen=True)
class TrainResult:
    adapter_path: str
    train_loss: float | None
    eval_loss: float | None
    steps: int
    run_id: str | None = None


# ── heavy orchestrator (lazy imports; GPU window only) ────────────────────────────────────────────


def _resolve_dtype(name: str):  # pragma: no cover - torch only present in the GPU window
    import torch

    return {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[name]


def run_training(  # pragma: no cover - executed only in the episodic GPU window
    config: RunConfig,
    data_dir: str | Path,
    output_dir: str | Path,
    tracker=None,
) -> TrainResult:
    """Run the QLoRA SFT fine-tune. Heavy deps imported lazily; needs a GPU."""
    import datasets
    from peft import LoraConfig
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        EarlyStoppingCallback,
        TrainerCallback,
    )
    from trl import SFTConfig, SFTTrainer

    data_dir = Path(data_dir)
    output_dir = Path(output_dir)

    bnb = BitsAndBytesConfig(
        **{**quantization_kwargs(config),
           "bnb_4bit_compute_dtype": _resolve_dtype(config.quant.bnb_4bit_compute_dtype)}
    )
    tokenizer = AutoTokenizer.from_pretrained(config.base_model)
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model, quantization_config=bnb, device_map="auto"
    )
    peft_config = LoraConfig(**lora_kwargs(config))

    train_ds = datasets.Dataset.from_list(load_chat_rows(data_dir / "train.jsonl"))
    val_ds = datasets.Dataset.from_list(load_chat_rows(data_dir / "val.jsonl"))

    sft_config = SFTConfig(**sft_kwargs(config, output_dir))

    class _LossToMlflow(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kw):
            if not (logs and tracker):
                return
            train_loss, eval_loss = extract_losses(logs)
            if train_loss is not None or eval_loss is not None:
                tracker.log_loss(int(state.global_step),
                                 train_loss=train_loss if train_loss is not None else float("nan"),
                                 eval_loss=eval_loss)

    callbacks = [EarlyStoppingCallback(**early_stopping_kwargs(config))]
    run_id = None
    if tracker is not None:
        run_id = tracker.log_run(config)
        callbacks.append(_LossToMlflow())

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        peft_config=peft_config,
        processing_class=tokenizer,
        callbacks=callbacks,
    )
    trainer.train()
    trainer.save_model(str(output_dir))

    history = trainer.state.log_history
    last_train = next((h["loss"] for h in reversed(history) if "loss" in h), None)
    last_eval = next((h["eval_loss"] for h in reversed(history) if "eval_loss" in h), None)
    return TrainResult(
        adapter_path=str(output_dir),
        train_loss=last_train,
        eval_loss=last_eval,
        steps=int(trainer.state.global_step),
        run_id=run_id,
    )


def _main(argv: list[str] | None = None) -> int:  # pragma: no cover - episodic entrypoint
    parser = argparse.ArgumentParser(description="Atlas QLoRA SFT fine-tune (episodic, GPU).")
    parser.add_argument("--config", required=True, help="path to configs/qlora_*.yaml")
    parser.add_argument("--data-dir", default="data", help="dir with train.jsonl + val.jsonl")
    parser.add_argument("--out", default="out/adapter", help="adapter output dir")
    parser.add_argument("--register", action="store_true",
                        help="after training, push to HF Hub + register the MLflow version")
    args = parser.parse_args(argv)

    config = load(args.config)

    tracker = None
    if args.register:
        from atlas_training.tracking import HfHubClient, MlflowRegistry, Tracker

        tracker = Tracker.from_env(MlflowRegistry(), HfHubClient())

    result = run_training(config, args.data_dir, args.out, tracker=tracker)

    if args.register and tracker is not None:
        mv = tracker.register_adapter(
            result.run_id, result.adapter_path, config.mlflow.register_as
        )
        print(f"registered {mv.name} v{mv.version} <- {mv.source}")
    print(f"adapter: {result.adapter_path}  train_loss={result.train_loss} "
          f"eval_loss={result.eval_loss} steps={result.steps}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
