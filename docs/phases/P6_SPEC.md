# P6 — Fine-tuning Pipeline + Experiment Tracking — SPEC

> **Status:** Groomed (2026-06-30) — owner-confirmed decisions recorded in §3.1. Pending: log
> ADR-0069…0074 in `docs/DECISIONS.md`, then begin Task 1. No code until that go-ahead.
> **Phase goal (from ROADMAP §2 P6):** Own the **training half** of the model lifecycle that P0–P5
> only ever *consumed*. Produce a **versioned, QLoRA-fine-tuned small model** for Atlas's
> **citation-bound answer / grounded-refusal** format, tracked and registered reproducibly. Extends
> the "every model call evaluated, traced, governed" thesis from **inference to the model artifact
> itself**. Primarily hardens **R2** (hallucination / ungrounded answers) and contributes the
> training-side controls for **LLM03** (supply chain: adapter provenance) and **LLM04** (data/model
> poisoning: trusted-corpus-only training).

---

## 0. Context & what we inherit

P6 is a **net-new Python/MLOps subsystem** layered on a complete, deployed system. It writes **no Java**
(see §2.1). It reuses, rather than reinvents:

| Inherited asset | From | Reused for |
|---|---|---|
| JarvisLabs SDK provisioner + guaranteed-teardown watchdog | ADR-0066, ADR-0029 (`infra/gpu`) | episodic `resume→train→pause`, per-run cost capture |
| vLLM serving profile on L4 (`Qwen2.5-7B-Instruct-AWQ` validated) | ADR-0067/0068 | *reference* for base-model fit; **serving the adapter is P7, not P6** |
| Golden + adversarial eval datasets (`evals/data/golden.jsonl` 22 tuples, `adversarial.jsonl` 10 cases) | ADR-0028 | base-vs-FT comparison inputs |
| Calibrated eval floors (`evals/data/baseline.json`: faithfulness/relevancy/recall) | ADR-0024 | comparison reference; **enforced as a gate only in P7** |
| RAGAS runner + scorers (`evals/atlas_evals/metrics/`) | P2 | faithfulness scoring of FT outputs |
| Committed-benchmark pattern (`infra/bench/results/COMPARISON.md` + `results/*.json`) | ADR-0067 | exact shape for `training/COMPARISON.md` |
| FinanceBench corpus + provenance manifest (`financebench_id` snippets, Layer-2 overlay) | ADR-0017/0020/0004 | trusted-corpus-only training substrate |

**Hard boundary with P7.** P6 *produces and commits* a registered adapter + a base-vs-FT evidence
bundle. P7 *consumes* those committed artifacts **GPU-free** to enforce a promotion gate, wires the
router FT tier, serves via vLLM multi-LoRA, and demos drift. Nothing in P6 enforces a model-promotion
gate or serves the adapter in production.

---

## 1. Scope

### In scope
1. **`training/` module** (new Python `uv` project): config-pinned, reproducible-from-committed-config
   QLoRA fine-tune of a small instruct base model for the citation-bound-answer / grounded-refusal format.
2. **Dataset curation + synthetic data generation** grounded **only** in the committed trusted corpus
   (FinanceBench snippets + Layer-2 overlay), emitting a **provenance manifest** (source / generator model
   / license / size / seed) and a train/val split.
3. **QLoRA (4-bit NF4) training** via PEFT/TRL, with train/val-loss monitoring + early stopping; per-run
   training cost recorded.
4. **MLflow** experiment tracking + **model registry** stood up in `/infra` on the **existing Postgres**
   backend for run/registry **metadata**; the **durable artifact store is the Hugging Face Hub** — the
   adapter is **pushed to HF from the GPU window before teardown** (the Oracle ARM box is not yet
   provisioned, ADR-0055, so it's deferred as a *future* second mirror). The MLflow registry version
   records the **HF repo + revision** as its source, so the adapter is a **versioned artifact decoupled
   from the disposable GPU**.
5. **Episodic GPU lifecycle** reusing the JarvisLabs provisioner (`resume→train→pause`, guaranteed teardown).
6. **Base-vs-fine-tuned comparison benchmark** harness (RAGAS **faithfulness** + **format-validity** +
   **refusal-correctness**) reusing existing eval datasets, emitting a committed evidence artifact
   (`training/COMPARISON.md` + `results/*.json`, candidate Δ vs base).
7. **Offline, GPU-free test suite** (dataset builders, manifest validation, config pinning, MLflow logging
   wrapper, format/refusal scorers, report generator) wired into CI — keeping CI **GPU-free** and green.
8. Docs: `docs/DECISIONS.md` entries, `training/README.md`, quantified `docs/PORTFOLIO.md` bullet.

### Non-goals (explicit — prevent scope creep)
- **No production serving of the fine-tuned model.** No vLLM **multi-LoRA hot-swap**, no router FT-tier
  wiring, no always-on FT endpoint. → **P7**.
- **No CI model-promotion gate / enforced eval floors on the model version.** P6 commits the *evidence*;
  P7 turns the floors into a GPU-free promotion gate that "bites". → **P7**.
- **No drift detection / Alertmanager rule.** → **P7**.
- **No full fine-tuning, RLHF, DPO, or other preference tuning.** QLoRA SFT only.
- **No fine-tuning of the embedding model.** The pgvector column is pinned to `nomic-embed-text` (768-dim,
  ADR-0005) — untouched.
- **No new datastore.** MLflow reuses the existing `atlas-postgres`; artifacts land on the Oracle box.
- **No always-on GPU.** Training and candidate-output generation happen in a bounded episodic window, then
  the GPU is torn down; CI never needs a GPU.
- **No Java changes.** Gateway/RAG/MCP code is not touched in P6.
- **No untrusted training data.** Training inputs are restricted to the committed corpus (LLM04).
- **No corpus expansion** beyond the committed FinanceBench subset + Layer-2 overlay (would require a new
  ADR superseding 0020).

---

## 2. Design

### 2.1 Language / runtime split (and why)

| Concern | Language | Why |
|---|---|---|
| Dataset curation, synthetic generation, QLoRA training, MLflow client, comparison harness | **Python** | The PEFT/TRL/Transformers/`bitsandbytes`/MLflow ecosystem is Python-native; `/evals` is already Python and the scorers are reused. Model *training* is a Python/MLOps concern end-to-end. |
| MLflow tracking server + registry | **Python service (containerized)** in `/infra` | Mirrors the Langfuse pattern (ADR-0025): a self-hosted service on the existing Postgres, no new managed dependency. |
| GPU provisioning / lifecycle | **Python** (`infra/gpu`, reused) | Already the SDK-backed JarvisLabs provisioner (ADR-0066). |
| **Java (gateway / RAG / MCP)** | **— none in P6 —** | The Java core *consumes* models; it does not train them. The gateway's ability to **select** the FT tier is a P7 deliverable (a router integration test), explicitly deferred so P6 stays a focused training subsystem. This is a deliberate, documented split, not an omission. |

### 2.2 Component breakdown

```
training/                              # new uv project (Python 3.12, pinned)
├── pyproject.toml / uv.lock           # pinned deps: transformers, peft, trl, bitsandbytes, datasets,
│                                      #   accelerate, mlflow, (optional) unsloth; torch pinned to GPU CUDA build
├── README.md                          # purpose, setup, how to run (episodic), results/metrics
├── configs/
│   └── qlora_<base>.yaml              # THE pinned run config: base model, NF4/QLoRA params, dataset refs,
│                                      #   seed, train/val split, early-stopping, MLflow run/experiment names
├── atlas_training/
│   ├── config.py                      # typed config loader + validation; fails fast on unpinned fields
│   ├── data/
│   │   ├── corpus.py                  # loads committed FinanceBench snippets + Layer-2 overlay (trusted only)
│   │   ├── synth.py                   # synthetic (context→cited-answer / grounded-refusal) pair generator
│   │   ├── manifest.py                # provenance manifest build + validate (source/generator/license/size/seed)
│   │   └── builder.py                 # assembles SFT chat-format dataset + deterministic train/val split
│   ├── train.py                       # QLoRA SFT (PEFT/TRL SFTTrainer); val-loss early stopping; MLflow logging
│   ├── tracking.py                    # MLflow wrapper: log params/metrics/loss; push adapter→HF Hub; register version (source=HF repo+rev)
│   ├── infer.py                       # adapter inference path for candidate-output generation (see D5)
│   └── cost.py                        # per-run training-cost capture (GPU ₹/hr × wall-clock from provisioner)
├── data/
│   ├── synthetic.jsonl                # committed synthetic seed set (small, provenance-tagged)
│   └── manifest.json                  # committed provenance manifest
├── results/
│   ├── base.json / ft.json            # committed candidate/base outputs + scores (generated in GPU window)
│   └── COMPARISON.md                  # committed headline: candidate Δ vs base
└── tests/                             # GPU-free offline unit tests (CI)

evals/atlas_evals/metrics/
├── format_validity.py                 # NEW deterministic validator (citation-bound / refusal schema)  ← reused by P7
└── refusal.py                         # NEW refusal-correctness scorer over a labeled refusal subset    ← reused by P7

infra/
├── docker-compose.yml                 # + `mlflow` service (Postgres-backed, artifact root volume/mount)
└── mlflow/                            # Dockerfile / entrypoint / artifact-root config
```

### 2.3 Data models / schemas

**Provenance manifest** (`training/data/manifest.json`) — the LLM04 / LLM03 trust artifact:
```jsonc
{
  "dataset_version": "p6-v1",
  "seed": 42,
  "sources": [
    { "kind": "financebench", "license": "CC-BY-NC-4.0", "ids": ["financebench_id_03029", "..."], "count": 12 },
    { "kind": "layer2_overlay", "license": "authored-internal", "docs": ["northwind_aml_memo", "..."], "count": 10 }
  ],
  "synthetic": {
    "generator_model": "<frontier-or-selfhosted model id>",   // see D3
    "generator_provider": "<provider>",
    "prompt_template_sha": "<sha>",
    "grounded_in": "trusted-corpus-only",                     // contexts drawn ONLY from sources above
    "count": <n>, "answer_pairs": <n>, "refusal_pairs": <n>
  },
  "split": { "train": <n>, "val": <n>, "strategy": "deterministic-by-id" },
  "generated_at": "<iso8601>", "git_sha": "<sha>"
}
```

**SFT training example** (chat-format; the unit of `builder.py` output):
```jsonc
{
  "messages": [
    { "role": "system",  "content": "<Atlas citation-bound answer / grounded-refusal instruction>" },
    { "role": "user",    "content": "<question>\n\n<retrieved context with [doc:ID] markers>" },
    { "role": "assistant","content": "<cited answer with [doc:ID] citations>  |  <grounded refusal>" }
  ],
  "label": "answer" | "refusal",
  "provenance_ref": "<source id or synthetic batch id>"
}
```

**Pinned run config** (`configs/qlora_<base>.yaml`) — reproducibility contract:
```yaml
base_model: Qwen/Qwen2.5-7B-Instruct          # D2
quant: { load_in_4bit: true, bnb_4bit_quant_type: nf4, bnb_4bit_compute_dtype: bfloat16, double_quant: true }
lora:  { r: 16, alpha: 32, dropout: 0.05, target_modules: [q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj] }
train: { epochs: 3, lr: 2.0e-4, batch_size: 4, grad_accum: 4, max_seq_len: 2048, seed: 42 }
early_stopping: { metric: eval_loss, patience: 2, min_delta: 0.005 }
dataset: { manifest: data/manifest.json, train: <ref>, val: <ref> }
mlflow: { experiment: atlas-citation-ft, run_name: qlora-qwen7b-<date>, register_as: atlas-citation-adapter }
```
*(Exact LoRA/train hyper-params are tuning details, finalized at run time; the **config is the pinned,
committed contract** — a re-run from it reproduces the adapter.)*

**Comparison result** (`training/results/*.json` + `COMPARISON.md`) — same shape as `infra/bench`:
per-metric `{ base, ft, delta }` for `faithfulness`, `format_validity`, `refusal_correctness`, plus
`training_cost`, `dataset_size`, `model_ids`, `git_sha`, `recorded_at`.

### 2.4 Key interfaces & contracts
- **`config.load(path) -> RunConfig`** — fails fast on any unpinned required field (base model, seed,
  dataset refs, quant params). Guarantees reproducibility-from-config (DoD item 1).
- **`manifest.validate(manifest, corpus) -> None`** — every source id resolves to a real committed corpus
  doc; synthetic contexts are grounded only in listed sources (LLM04 trusted-corpus invariant). Mirrors the
  P2 loader's "every reference resolves" guard (ADR-0028).
- **`format_validity.score(output) -> bool`** *(GPU-free, deterministic)* — output conforms to the
  citation-bound-answer schema (answer text + ≥1 resolvable `[doc:ID]` marker) **or** the grounded-refusal
  schema. Reusable verbatim by the P7 promotion gate.
- **`refusal.score(case, output) -> bool`** — on `should_refuse` cases the model refuses; on answerable
  cases it does not over-refuse. Operates on a small labeled refusal subset (see §4).
- **`tracking.register(run, adapter_path) -> ModelVersion`** — pushes the adapter to the **HF Hub** repo
  (write via `HF_TOKEN`, private by default), then logs the run + registers a versioned MLflow registry
  entry whose **source URI is the HF repo + revision**. The push happens **before GPU teardown** so the
  artifact is durable off-GPU. *(`HF_TOKEN` is a managed secret — `.env.example` only, never in code.)*

### 2.5 Request / data flow (episodic training run)
```
1. [laptop/CI, GPU-free]  curate corpus → generate synthetic pairs → build manifest + train/val split
                          → commit data/synthetic.jsonl + manifest.json  (offline, unit-tested)
2. [provisioner]          infra/gpu: resume/provision L4  (guaranteed-pause watchdog armed)
3. [GPU window]           train.py: QLoRA SFT from pinned config; stream train/val loss → MLflow;
                          early-stop on eval_loss; produce adapter
4. [GPU window]           tracking.register: PUSH adapter to HF Hub (durable, pre-teardown) → MLflow
                          registry version records HF repo+revision as source
5. [GPU window]           infer.py: generate base + FT candidate outputs over reused eval datasets
6. [GPU window]           score: RAGAS faithfulness + deterministic format-validity + refusal-correctness
7. [provisioner]          PAUSE/TEARDOWN GPU (cost recorded); balance verified
8. [laptop/CI, GPU-free]  commit results/*.json + COMPARISON.md + registry pointer; CI validates artifact
                          schema + runs offline unit tests (no GPU)
```
The GPU is the *only* episodic, paid step; everything before (1) and after (8) is GPU-free and committed —
exactly the ADR-0067 benchmark discipline, now applied to model artifacts. P7 reads the committed outputs.

---

## 3. Decisions to make now

> For each: options + trade-offs + recommendation. **Confirm and I will log them in `docs/DECISIONS.md`**
> as **ADR-0069…0074**, tagged **`Training`** (not `P6` — the `Phase` column now uses stable theme tags;
> the collided `P6` labels on ADR-0060–0065 were retagged `Deploy`, ADR-0032 `Backlog`, 2026-06-30).

### 3.1 Owner-confirmed (2026-06-30)
| # | Decision | Confirmed choice |
|---|---|---|
| D1 | Fine-tuning library | **PEFT + TRL `SFTTrainer`** (recommended default; Unsloth as a speed fallback if L4 wall-clock hurts) |
| D2 | Base model | **Qwen2.5-7B-Instruct** (Apache-2.0); 3B retained as a fast smoke config |
| D3 | Synthetic-data generator | **Bounded frontier seed + hand-authored refusals** — reserved frontier budget approved for *offline* generation |
| D4 | MLflow store + artifact dest | **Reuse `atlas-postgres` (separate db) for tracking/registry metadata; durable artifact store = Hugging Face Hub (primary)** — adapter pushed to HF from the GPU window pre-teardown. **Oracle box durable root is deferred** (not yet provisioned, per ADR-0055) → add as a second mirror once it exists. |
| D5 | Candidate-output path | **Transformers/PEFT inference in the GPU window** (vLLM multi-LoRA stays in P7) |
| D6 | format-validity / refusal-correctness | **Deterministic GPU-free validators** in `evals/atlas_evals/metrics/`, reused verbatim by P7 |
| Q1 | Episodic GPU budget | **~1 L4-day (≈₹1000)** across all train + benchmark runs |
| — | **Where it runs** | **Training + candidate-output generation run on the Cloud GPU (JarvisLabs L4), episodically — never local.** All curation, synthetic generation (frontier *API*), scoring, MLflow server, and registry browsing are GPU-free (laptop/CI). One resume → train → register → generate → teardown window. |

*Detailed options/trade-offs that produced these choices are retained below for the decision log.*

### D1 — Fine-tuning library
- **(a) PEFT + TRL `SFTTrainer`** — the de-facto standard; maximally transferable/interview-legible;
  best docs; works with `bitsandbytes` NF4. Slightly more boilerplate, somewhat slower than Unsloth.
- **(b) Unsloth** — ~2× faster, lower VRAM (fits 7B on L4 comfortably), cheaper episodic runs. Less
  "vanilla", extra dependency surface, some base-model coverage caveats.
- **(c) Axolotl** — YAML-config-first (nice for reproducibility), but heavier framework, more to learn,
  less aligned with our hand-pinned-config approach.
- **Recommendation: (a) PEFT + TRL.** It's the portfolio-legible standard and pairs cleanly with our
  own pinned-YAML config and MLflow logging. Note Unsloth as a drop-in speed optimization we can adopt
  if L4 wall-clock/cost on 7B proves painful (the `train.py` seam stays the same).

### D2 — Base model
- **(a) Qwen2.5-7B-Instruct (Apache-2.0)** — **matches the agent reasoning tier (ADR-0042) and the
  vLLM-validated `Qwen2.5-7B-Instruct-AWQ` (ADR-0067)**; the FT tier would be the same family, so P7's
  router tiering and serving are coherent. Heavier/slower to train on L4.
- **(b) Qwen2.5-3B-Instruct** — matches the RAG dev model (`qwen2.5:3b`, ADR-0005/baseline.json); much
  cheaper/faster episodic training; weaker ceiling, and diverges from the 7B serving family P7 expects.
- **(c) Llama-3.1-8B-Instruct** — strong, but introduces a third model family and a non-Apache license
  consideration; no existing Atlas validation on our GPU.
- **Recommendation: (a) Qwen2.5-7B-Instruct**, with **(b) 3B retained as a fast "smoke" config** for
  pipeline shakedown and CI-adjacent dry runs. 7B aligns the trained artifact with the family P7 will
  serve and tier, which is the whole point of the lifecycle story; 3B keeps iteration cheap.

### D3 — Synthetic-data generator (and budget posture)
- **(a) Bounded frontier model** (reserved cloud-frontier budget) generates context→answer/refusal pairs
  from our trusted contexts — highest quality teacher signal; costs a small, bounded frontier spend; record
  generator id + license in the manifest. *(Distillation from a frontier teacher; check provider ToS — fine
  for a non-commercial portfolio.)*
- **(b) Self-hosted larger Ollama model on the episodic GPU** (e.g. `llama3.1:8b` / `qwen2.5:7b`) — no
  external spend, all-local/no-egress story stays pure; lower-quality pairs, more curation needed.
- **(c) Hand-authored only** — full control + cleanest provenance; small N, slow to produce, limited
  diversity.
- **Recommendation: (a) bounded frontier seed + (c) hand-authored refusal cases**, all provenance-tagged.
  The frontier teacher produces the highest-signal answer pairs cheaply at small N; we hand-author the
  grounded-refusal edge cases (the safety-critical ones) so they're authoritative. Contexts are **always**
  drawn from the trusted corpus (LLM04). **Requires owner sign-off on using the reserved frontier budget
  for offline data generation** (see Q2).

### D4 — MLflow backend & artifact-store topology
- **(a) Reuse `atlas-postgres` (separate `mlflow` db) for tracking + durable artifact root on the Oracle
  ARM box** (optional HF Hub mirror) — mirrors the Langfuse footprint decision (ADR-0025): no new datastore,
  artifacts survive GPU teardown, one-command local bring-up.
- **(b) MLflow with local SQLite + local filesystem artifacts** — simplest, but not durable/shared and
  doesn't model a real registry; weak portfolio signal.
- **(c) Dedicated new Postgres + object store (MinIO)** — most "production", but new infra contradicts the
  no-new-datastore constraint and the ₹0 ethos.
- **Recommendation: (a), adapted to current infra.** Postgres-backed tracking + registry (reusing
  `atlas-postgres`). **Durable artifact store = Hugging Face Hub (primary)** because the Oracle ARM box is
  **not yet provisioned** (ADR-0055) — the adapter is pushed to a (private) HF repo from the GPU window
  **before teardown**, and the MLflow registry version records the HF repo+revision as its source. The Oracle
  durable root is **deferred** to a future second mirror once the box exists. The adapter is then a versioned
  artifact **decoupled from the disposable GPU** — pausing/destroying the GPU never loses the model (DoD
  invariant). Adds `HF_TOKEN` (write) as a managed secret.

### D5 — Candidate-output generation path for the benchmark
- **(a) Transformers + PEFT adapter inference in the same GPU window** (`infer.py` loads base + adapter) —
  keeps P6 fully self-contained; no dependency on P7's serving work; simplest path to committed outputs.
- **(b) Serve the adapter via vLLM multi-LoRA and generate through the OpenAI-compatible endpoint** — reuses
  ADR-0067/0068 serving and is closer to production, **but vLLM multi-LoRA hot-swap is explicitly a P7
  deliverable** — pulling it into P6 blurs the phase boundary.
- **Recommendation: (a).** Generate candidate/base outputs via PEFT/Transformers in the training window and
  commit them. P7 re-serves via vLLM for its production benchmark; P6 only needs committed evidence. This
  keeps the P6/P7 boundary clean and P6 independent of serving readiness.

### D6 — "Format-validity" & "refusal-correctness" definitions (the FT-specific metrics)
- **(a) Deterministic, GPU-free validators** — format-validity = parses to the citation-bound-answer schema
  (answer + ≥1 resolvable `[doc:ID]`) or the grounded-refusal schema; refusal-correctness = labeled
  `should_refuse` subset, exact refuse/answer match. Cheap, reproducible, **reusable verbatim in P7's
  GPU-free gate**.
- **(b) LLM-as-judge for both** — flexible, but costs GPU/$, adds variance, and can't run in a GPU-free CI
  gate (breaks P7's design).
- **Recommendation: (a) deterministic validators**, living in `evals/atlas_evals/metrics/` so P7 inherits
  them. Faithfulness stays RAGAS (LLM-judge, computed in the GPU window and committed). This is what makes
  P7's promotion gate able to run with **no GPU**.

---

## 4. Test strategy

**Principle:** CI stays **GPU-free and green**. The training run + candidate generation are episodic and
produce **committed** artifacts; CI exercises the offline logic and validates the committed artifacts'
schema/integrity — never a GPU.

### 4.1 Unit tests (offline, in CI — the bulk)
- `config.load` rejects unpinned/invalid configs; round-trips the pinned YAML.
- `manifest.build/validate`: every source id resolves to a committed corpus doc; rejects any synthetic
  context not grounded in a listed source (LLM04 invariant); split is deterministic by seed.
- `builder`: produces well-formed chat-format SFT examples; train/val disjoint; reproducible under seed.
- `synth` (generator mocked): prompt template + provenance tagging correct; no network in unit mode.
- `tracking` (MLflow client mocked/local): logs params/metrics; `register` points at the durable root, not
  a GPU-local path.
- `format_validity` / `refusal` scorers: table-driven cases (valid/invalid citations, correct/over/under
  refusal). These are the reused-by-P7 contracts — test them hard.
- `cost` capture: ₹/hr × wall-clock math; teardown always recorded.
- comparison **report generator**: given fixture base/ft scores, emits the expected `COMPARISON.md` + JSON.

### 4.2 Integration tests
- **MLflow round-trip** against a real local `mlflow` container (compose): log a run, register a version
  whose source is an HF repo+revision, read it back. The **HF push is behind a mockable seam** for CI; an
  optional `@live` test pushes a dummy adapter to a private test repo and resolves it. (CPU-only, no GPU.)
- **Tiny-model pipeline smoke** (`@live`/episodic, *not* in CI): a few-step QLoRA run on the 3B smoke
  config end-to-end (data→train→register→infer→score) to prove the wiring; asserts an adapter is produced
  and registered. Documented as the episodic verification, run on the GPU window.

### 4.3 Eval / comparison gate (phase touches RAG/model → required)
- **Dataset:** reuse `evals/data/golden.jsonl` (22 tuples) + `adversarial.jsonl` (refusal/access-bypass
  lane) + a **new small labeled refusal subset** (out-of-context / unanswerable / out-of-clearance cases)
  for refusal-correctness.
- **Metrics & thresholds (candidate vs base):**
  - **RAGAS faithfulness** — FT must **not regress** vs base beyond the P2 `max_regression` band (0.05);
    target FT ≥ base. Floor reference reused from `baseline.json` (faithfulness floor 0.656).
  - **format-validity** (deterministic) — **target FT ≥ 0.95**; report base for contrast (the core reason
    to fine-tune is format adherence).
  - **refusal-correctness** (deterministic) — **target FT ≥ base**; report both.
- **Gate semantics in P6:** P6's *committed deliverable* is the benchmark itself (`COMPARISON.md` +
  `results/*.json`) showing the candidate Δ — **same status as the `infra/bench` ADR-0067 artifact**. P6
  does **not** add a new GPU-requiring CI merge gate; the offline scorer/report **unit tests** are the CI
  gate, plus a CI check that the committed comparison artifact is schema-valid and present.
- **P7 hand-off:** P7 turns these same metrics into an enforced GPU-free promotion gate (sub-floor adapter
  provably blocked). P6 must therefore emit them in the exact schema P7 will consume.

### 4.4 Regression gate (inherited — must stay green)
- The existing P2/P5 CI gates (RAGAS replay, adversarial 100%-pass, cost-regression, agent gate) are
  **unaffected** — P6 touches no Java/serving path. CI run must remain green with the new `training/` tests
  added.

---

## 5. Task breakdown (ordered, independently committable)

1. **Scaffold `training/`** — uv project, pinned `pyproject.toml`/lock, `README` skeleton, `config.py` +
   pinned `configs/qlora_*.yaml` schema + loader, seed plumbing. *(GPU-free; unit tests.)*
2. **Corpus loader** (`data/corpus.py`) — load committed FinanceBench snippets + Layer-2 overlay as trusted
   training contexts. *(Unit tests: every id resolves.)*
3. **Provenance manifest** (`data/manifest.py`) — build + validate; trusted-corpus-only invariant. *(Unit.)*
4. **Synthetic generation** (`data/synth.py`) — context→answer/refusal pair generator (generator behind a
   seam, mockable); commit a small `data/synthetic.jsonl` + `manifest.json`. *(Unit with generator mocked;
   real generation is a one-off, committed.)*
5. **Dataset builder + split** (`data/builder.py`) — chat-format SFT examples, deterministic train/val. *(Unit.)*
6. **Format-validity + refusal scorers** in `evals/atlas_evals/metrics/` — deterministic, GPU-free, the
   P7-reused contracts. *(Unit, table-driven.)*
7. **MLflow stack in `/infra`** — compose `mlflow` service (Postgres-backed metadata) + `tracking.py`
   wrapper that pushes the adapter to HF Hub and records the HF repo+revision as the registry source.
   *(Integration: local MLflow round-trip; HF push behind a mockable seam + an optional `@live` push to a
   private test repo.)*
8. **QLoRA `train.py`** — PEFT/TRL SFTTrainer from pinned config, NF4, train/val-loss → MLflow, early
   stopping. *(Unit-test config wiring with a tiny/stub model; full run is episodic.)*
9. **GPU lifecycle wiring + `cost.py`** — reuse `infra/gpu` provisioner for `resume→train→pause`; capture
   per-run cost; guaranteed teardown. *(Unit: cost math; reuses ADR-0066 tested provisioner.)*
10. **`infer.py` + comparison harness** — generate base/FT outputs over reused datasets; score
    faithfulness/format/refusal; emit `results/*.json` + `COMPARISON.md`. *(Unit: report generator on
    fixtures.)*
11. **Episodic run** — execute the real train→register→benchmark on L4; commit adapter registry pointer +
    `synthetic.jsonl`/`manifest.json` + `results/` + `COMPARISON.md`; record training cost. *(The evidence
    drop.)*
12. **Docs** — `docs/DECISIONS.md` (ADR-0069…0074), `training/README.md`, quantified `docs/PORTFOLIO.md`
    bullet.

---

## 6. Definition of Done (P6 — generic CLAUDE.md DoD, instantiated)

- [ ] **Code complete & matches this spec.** `training/` module with a **pinned config** (base model, QLoRA
      4-bit NF4 params, dataset refs, seed); a fine-tune run is **reproducible from committed config**.
- [ ] **Unit + integration tests written and passing in CI (GPU-free):** dataset builders, manifest
      validation, config pinning, MLflow round-trip (local container), format-validity + refusal scorers,
      cost capture, report generator. Existing P2/P5 gates remain green.
- [ ] **Eval evidence met & recorded:** base-vs-FT **comparison benchmark** committed (`training/COMPARISON.md`
      + `results/*.json`) — faithfulness (no-regression band) + format-validity (≥0.95 target) +
      refusal-correctness, candidate Δ vs base — in the same shape as the vLLM-vs-Ollama benchmark; emitted
      in the schema P7's promotion gate will consume.
- [ ] **Dataset curated with provenance:** FinanceBench (CC-BY-NC-4.0) + Layer-2 overlay + bounded synthetic
      pairs, with a committed `manifest.json` (source / generator / license / size / seed); training inputs
      are trusted-corpus-only (LLM04).
- [ ] **MLflow tracking + registry** stood up in `/infra` on the existing Postgres (metadata); the adapter is
      **pushed to the Hugging Face Hub (durable store) before GPU teardown** and the registry version records
      the HF repo+revision; the adapter is a **versioned artifact decoupled from the disposable GPU** — GPU
      teardown never loses the model. *(Oracle durable mirror deferred until the box is provisioned.)*
- [ ] **Episodic GPU discipline:** run uses the JarvisLabs provisioner (`resume→train→pause`, guaranteed
      teardown); **per-run training cost recorded**.
- [ ] **Module README + `docs/DECISIONS.md` updated** (ADR-0069…0074: QLoRA-over-full-FT, base-model pick,
      FT library, synthetic-data generator, MLflow store, candidate-inference path).
- [ ] **Runs cleanly from scratch via documented setup:** `docker compose up mlflow` + `training/README.md`
      reproduces tracking/registry locally GPU-free; the episodic train command is documented.
- [ ] **30-second demo path:** `docker compose up mlflow` → browse the registry → open the registered adapter
      version (source = HF repo+revision, `hf` pull works) → open `training/COMPARISON.md` showing candidate Δ
      vs base (all GPU-free, from committed artifacts).
- [ ] **Resume-ready, quantified bullet** drafted in `docs/PORTFOLIO.md`: faithfulness / format-validity /
      refusal-correctness (FT vs base), training cost per run, dataset size + provenance.

**Done when.** A fine-tune run is reproducible from committed config; the adapter lands in the registry as a
versioned artifact **(durable off-GPU)**; the committed base-vs-FT benchmark shows the candidate's delta vs
base — all browsable GPU-free from a fresh clone.

---

## 7. Open questions / ambiguities

1. ~~**Episodic training budget ceiling.**~~ → **Resolved (§3.1):** ~1 L4-day (≈₹1000) across all train +
   benchmark runs.
2. ~~**Frontier budget for synthetic data (D3).**~~ → **Resolved (§3.1):** bounded frontier spend approved
   for offline synthetic-pair generation.
3. ~~**HF Hub mirror (D4).**~~ → **Resolved (§3.1):** Oracle box durable root **+** HF Hub mirror of the
   registered adapter (adds an `HF_TOKEN` env var + a mirror push step; repo private by default).
4. ~~**Where training runs.**~~ → **Resolved (§3.1):** Cloud GPU (JarvisLabs L4), episodic; everything else
   GPU-free on laptop/CI.
5. ~~**Doc-numbering note.**~~ → **Resolved (2026-06-30):** the `DECISIONS.md` `Phase` column now uses
   stable **theme tags**. The collided `P6` labels were retagged — **ADR-0060–0065 → `Deploy`**,
   **ADR-0032 → `Backlog`** — and these P6 fine-tuning decisions will be logged as **ADR-0069…0074, tag
   `Training`**. A legend note was added at the top of `DECISIONS.md`.

---

> **STOP — awaiting final go-ahead.** §3 (D1–D6) and the budget/runtime questions are confirmed (§3.1).
> On your go-ahead I'll log **ADR-0069…0074** in `docs/DECISIONS.md` and begin Task 1 (scaffold `training/`).
> No code until then. D1 (PEFT+TRL), D5 (Transformers/PEFT inference), and D6 (deterministic validators) are
> recorded as my recommendations — flag if you'd prefer otherwise before I log them.
