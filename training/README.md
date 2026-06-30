# training — Atlas QLoRA fine-tuning pipeline + experiment tracking (P6)

**Purpose.** Own the **training half** of the model lifecycle that P0–P5 only ever *consumed*.
Produce a **versioned, QLoRA-fine-tuned small model** for Atlas's **citation-bound answer /
grounded-refusal** format — tracked in MLflow, pushed durably to the Hugging Face Hub, and
benchmarked base-vs-FT — all **reproducible from committed config**. This extends Atlas's "every
model call evaluated, traced, governed" thesis from inference to the **model artifact itself**.

P6 produces and commits a registered adapter + a base-vs-FT evidence bundle. **P7 consumes** those
artifacts GPU-free to enforce a promotion gate and serve the adapter. See `docs/phases/P6_SPEC.md`.

## Design invariant: CI stays GPU-free
The LLM never runs locally (CLAUDE.md). Training and candidate-output generation happen only in a
**bounded episodic GPU window** (JarvisLabs L4, `resume → train → register → generate → teardown`).
Everything else — config loading, corpus/dataset curation, manifest validation, deterministic
scoring, report generation, the MLflow server — is **offline and unit-tested**. The heavy ML stack
(`transformers`, `peft`, `trl`, `bitsandbytes`, `mlflow`, …) lives in the optional `train`
dependency-group and is imported only by `train.py` / `infer.py`.

## Layout
```
configs/qlora_qwen7b.yaml        THE pinned run contract (base model, NF4/QLoRA, seed, dataset refs)
configs/qlora_qwen3b_smoke.yaml  fast pipeline-shakedown variant (3B, few steps)
atlas_training/config.py         typed, fail-fast loader for the pinned config  ← Task 1
atlas_training/data/             corpus loader, synth generation, manifest, builder   (Tasks 2–5)
atlas_training/train.py          QLoRA SFT (PEFT/TRL) — GPU window only                (Task 8)
atlas_training/tracking.py       MLflow logging + push adapter → HF Hub + register     (Task 7)
atlas_training/infer.py          base/FT candidate-output generation — GPU window      (Task 10)
atlas_training/cost.py           per-run training-cost capture                         (Task 9)
data/                            committed synthetic.jsonl + manifest.json
results/                         committed base/ft scores + COMPARISON.md
tests/                           offline GPU-free unit tests (CI)
```

## Setup (GPU-free, laptop/CI)
```bash
cd training
uv sync                 # installs pyyaml + pytest only — no torch, no GPU
uv run pytest           # offline unit tests
```

## Training run (episodic, GPU only — documented; not run in CI)
```bash
# On the JarvisLabs L4 window (see infra/gpu):
uv sync --group train               # installs the heavy ML stack on the GPU box
uv run python -m atlas_training.train --config configs/qlora_qwen7b.yaml
```

## Run config (the reproducibility contract)
`configs/qlora_*.yaml` is the pinned contract: base model, 4-bit NF4 quantization, LoRA params,
seed, dataset refs, early-stopping, and MLflow names. `config.load(path)` **fails fast** (raising
`ConfigError`) on any missing/unpinned required field — a re-run from the committed config
reproduces the adapter. See ADR-0069 (QLoRA 4-bit NF4 via PEFT/TRL) and ADR-0070 (Qwen2.5-7B base,
3B smoke).

## Results / metrics
_Populated by the episodic run (Task 11): base-vs-FT faithfulness, format-validity, and
refusal-correctness deltas, plus per-run training cost — committed to `results/COMPARISON.md`._
