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
atlas_training/tracking.py       MLflow logging + push adapter → HF Hub + register     (Task 7)atlas_training/infer.py          base/FT candidate-output generation — GPU window      (Task 10)
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
uv run python -m atlas_training.train \
  --config configs/qlora_qwen7b.yaml --data-dir data --out out/adapter --register
```
`--register` pushes the trained adapter to the HF Hub and registers the MLflow version
(`source = hf://<repo>@<rev>`). Without it, the adapter is just saved locally. The config→trainer
wiring (quantization / LoRA / SFT / early-stopping kwargs) is unit-tested GPU-free; only
`run_training` imports torch/transformers/peft/trl (lazily), so CI never needs a GPU.

### Per-run cost (cost discipline)
`atlas_training/cost.py` captures the window's cost = `ATLAS_GPU_COST_PER_HOUR` × wall-clock into a
committed `CostRecord`. It composes with `infra/gpu`'s guaranteed-teardown `GpuSession` (ADR-0066)
via a duck-typed seam — the cost is recorded even if training raises:
```python
from atlas_gpu.lifecycle import GpuSession           # ADR-0066: pause guaranteed on exit
from atlas_training.cost import costed_gpu_window, gpu_rate_from_env
rate, _ = gpu_rate_from_env()
result, cost = costed_gpu_window(GpuSession(provider), body=run_one, rate_per_hour=rate)
cost.save("results/cost.json")
```
The GPU rate is never hardcoded — set `ATLAS_GPU_COST_PER_HOUR` (+ `ATLAS_GPU_COST_CURRENCY`).

## Run config (the reproducibility contract)
`configs/qlora_*.yaml` is the pinned contract: base model, 4-bit NF4 quantization, LoRA params,
seed, dataset refs, early-stopping, and MLflow names. `config.load(path)` **fails fast** (raising
`ConfigError`) on any missing/unpinned required field — a re-run from the committed config
reproduces the adapter. See ADR-0069 (QLoRA 4-bit NF4 via PEFT/TRL) and ADR-0070 (Qwen2.5-7B base,
3B smoke).

## Experiment tracking + model registry (ADR-0072)
`atlas_training/tracking.py` logs params/metrics/loss to **MLflow** (Postgres-backed, `infra/`
`docker compose up mlflow`), then **pushes the adapter to the Hugging Face Hub** (the durable
store) and registers a model version whose **source URI is `hf://<repo>@<revision>`** — so the
adapter is decoupled from the disposable GPU (teardown never loses it). Both the HF and MLflow
clients are injectable seams, so the unit tests run GPU-free with no `mlflow`/`huggingface_hub`
import. A live round-trip is opt-in (not in CI):
```bash
docker compose -f infra/docker-compose.yml up -d mlflow
ATLAS_MLFLOW_IT=1 MLFLOW_TRACKING_URI=http://localhost:5000 \
  uv run --directory training --group train pytest tests/test_tracking_it.py -q
```
Config via env: `MLFLOW_TRACKING_URI`, `ATLAS_HF_ADAPTER_REPO`, `HF_TOKEN` (write, secret),
`HF_PRIVATE`.

## Dataset & provenance
`data/synthetic.jsonl` + `data/manifest.json` are the committed, provenance-tagged dataset. The
seed is **hand-authored** (cited answers grounded in verbatim FinanceBench figures + authored
grounded refusals), all drawn **only** from the trusted corpus (LLM04). The bounded-frontier
answer-pair expansion (`FrontierGenerator`, ADR-0071) is an **offline one-off** run in Task 11
(needs the `synth` dep group + `ATLAS_SYNTH_*` env); it never runs in CI. `manifest.validate`
enforces that every source id resolves in the committed corpus and synthetic pairs are grounded
only in listed sources. `data/train.jsonl` + `data/val.jsonl` are the committed, deterministic
(seed-42) chat-format SFT split the run config points at; `builder.split_dataset` regenerates them
identically from the seed (train/val disjoint, sizes matching the manifest).

## Base-vs-FT benchmark (ADR-0073)
In the GPU window, `infer.generate` produces base and base+adapter (FT) outputs over the reused
eval prompts (golden + the labeled `evals/data/refusal.jsonl` subset). `infer.score_outputs` scores
them into three metrics — RAGAS **faithfulness** (computed in-window) + the deterministic
**format-validity** and **refusal-correctness** scorers from `evals` (the same ones P7 reuses; the
sibling `atlas-evals` is a path dep in the `train` group only). `report.build_comparison` then
writes the committed evidence — `results/comparison.json` + `results/COMPARISON.md` — in the
`{base, ft, delta}` shape P7's promotion gate consumes. The report generator is pure and CI-tested
on fixtures; generation/scoring are episodic (GPU).

## Results / metrics
_Populated by the episodic run (Task 11): base-vs-FT faithfulness, format-validity, and
refusal-correctness deltas, plus per-run training cost — committed to `results/COMPARISON.md`._
