# P7 — Eval-Gated Promotion Gate, Base-vs-FT Benchmark & Drift Demo — SPEC

> Status: **APPROVED — grooming complete, implementation NOT started (2026-07-01).** This is the approved
> build contract for P7; the §6 Definition of Done is intentionally **all-unchecked `[ ]`** and will be
> checked honestly (with deviations noted inline) as the phase is built. No code, config, or tests have been
> written yet — the first diff will be §5 Task 1 (`evals/data/promotion-floors.json` + loader/validator).
> P7 is the **closing half of the MLOps lane**: it turns P6's *committed* fine-tuned adapter + base-vs-FT
> bundle into a **governed model-promotion path** — a **GPU-free CI gate that bites**, a router that *can*
> select the fine-tuned tier (capability, not uptime), a **one-shot seeded drift alert**, and a documented
> rollback. The deliverable is a **reproducible committed evidence bundle, not an always-on endpoint** (it
> mirrors the `infra/bench` vLLM-vs-Ollama artifact); the GPU is spun up **episodically** to generate evidence,
> then torn down. Primarily de-risks **R6** (model regression / train–serve skew) and reinforces **R7**
> (drift) + **LLM04** (poisoning controls extended to promotion time).
> All **8** §3 decisions (**D1–D8**) are **owner-confirmed** and logged as **ADR-0075–0082** (tag `Promotion`)
> in `docs/DECISIONS.md`; the §7 open questions (**Q1–Q6**) are all resolved; a **web-validated (2026-07-01)
> gap analysis (§8, W1–W5)** is folded into the sections below (the one substantive gap — statistical power on
> the N=30 comparison — is addressed by **D8/ADR-0082**, report-only).
> Date drafted: 2026-07-01 · Date approved: 2026-07-01 · Date completed: — (not started).
> **Owner-confirmed §3/§7 resolutions (2026-07-01):** D2 **hybrid** faithfulness semantics → the real P6
> adapter is the committed "promoted" example, **no re-train** (Q1); D4 **one episodic L4 window** regenerates
> base-vs-FT through the **served vLLM multi-LoRA** path + measures cost/latency (Q3); D3 **relative 10%**
> cost-per-request band, p95 latency report-only (Q2); D6 FT tier **flag-gated, never auto-selected** in prod
> (Q4); ADR tag **`Promotion`** (Q5); D8 statistical rigor **report-only** CIs + paired significance (Q6).
> Phase owner doc set: `CLAUDE.md` · `docs/ROADMAP.md` (§2 P7, §3 R6/R7, §4 skills-proof map, §7.1 LLM04) ·
> `docs/DECISIONS.md` (ADR-0075–0082 this phase; builds on ADR-0024 P2 gate/floors, ADR-0035 router, ADR-0064
> cost gate, ADR-0063 alerting, ADR-0066/0067/0068 GPU+vLLM, ADR-0072 MLflow registry, ADR-0073/0074 P6
> hand-off) · `docs/phases/P6_SPEC.md` (the adapter + comparison bundle this phase consumes) · `docs/RUNBOOK.md`.
> **Phase goal (from ROADMAP §2 P7):** Close the loop **as a committed evidence bundle, not a live endpoint** —
> prove a fine-tuned adapter reaches the router's production tier **only** by clearing the same eval+cost gate
> philosophy P2/P3 enforce on code, **now applied to model versions**, and prove the system can **detect
> drift**. Reproducible, committed proof; no always-on GPU.

---

P7 adds **no new model and no new intelligence**. The P6 QLoRA adapter, the P2 eval floors, the P3 router, the
ADR-0067/0068 vLLM profile, the ADR-0072 MLflow registry, and the ADR-0063 observability stack are all
**inherited and frozen in spirit** — P7 is a new *governance layer* over them: it consumes P6's committed
`comparison.json`, adds the promotion **gate** + **fixtures** that make the gate "bite", wires a **capability-only**
FT router tier, serves the adapter via **vLLM multi-LoRA** for one episodic window, and fires a **seeded** drift
alert. Everything the CI gate touches is **GPU-free**; the only GPU work is one bounded, self-destructing L4
window that produces committed evidence.

The **hard boundary with P6** (per `P6_SPEC.md §1`): P6 *produced and committed* the adapter + base-vs-FT
evidence and enforces **no** promotion gate, serves **no** adapter, ships **no** drift rule and **no** router FT
tier. P7 adds exactly those four things — **as committed proof, not uptime**. The load-bearing design fact P7
must handle is P6's honest result: **faithfulness −0.109** (above the 0.656 floor, outside the P2 0.05 band)
bought a **format-validity 0.000 → 0.955** jump — which is why the promotion gate uses **hybrid** semantics
(§3 D2) rather than the strict P2 no-regression band.

---

## 0. Context & what we inherit

P7 is the **closing half of the MLOps lane**. It writes **almost no new model code**: it turns P6's
*committed evidence* into a **governed model-promotion path** — a GPU-free CI gate that "bites", a
router that *can* select the fine-tuned tier, a one-shot drift alert, and a documented rollback. The
deliverable is a **reproducible committed evidence bundle, not an always-on endpoint** (mirrors the
`infra/bench` vLLM-vs-Ollama artifact). De-risks **R6** (model regression / train–serve skew).

| Inherited asset | From | Reused for |
|---|---|---|
| Base-vs-FT comparison producer `build_comparison`/`write_comparison` → `comparison.json` + `COMPARISON.md`, schema `{base, ft, delta}` over `faithfulness / format_validity / refusal_correctness` | P6 `training/atlas_training/report.py` (`METRICS`, `TARGETS`) | The **exact input the promotion gate consumes** |
| Committed real evidence `training/results/{comparison.json, COMPARISON.md, base.json, ft.json, cost.json}` (L4 run 2026-06-30) | P6 | The "passing" fixture + cost-per-request base data |
| Deterministic GPU-free scorers `format_validity.score`, `refusal.score_rate` | P6 (built in `evals/atlas_evals/metrics/`, "reused verbatim by P7") | Gate scoring with **no GPU / no RAGAS import** |
| P2 replay/merge gate `evaluate_gate` + calibrated floors `baseline.json` (faithfulness floor **0.656**, `max_regression` 0.05) | P2 (`evals/atlas_evals/gate.py`, `baseline.py`) | Floor **reference** + gate-shape precedent (the model bar == the code bar) |
| Cost-regression gate `evaluate_cost_gate` + `gateway-baseline.json` | P3 (`evals/atlas_evals/cost_gate.py`) | Precedent for the model **cost-regression** check |
| Cassette replay (`Mode.REPLAY`, `CassetteMiss` = hard fail) under `evals/data/cassettes/{rag,judge}` | P2 (`cassettes.py`) | GPU-free re-scoring precedent |
| MLflow registry + HF-Hub-backed versions `MlflowRegistry.create_model_version(name, source=hf://…@rev)`; `register_adapter.py` | P6 (`training/atlas_training/tracking.py`) | **Stage/alias transitions** for promote/rollback (net-new) |
| Router `ModelTier` enum (`tier1-small / tier2-mid / tier3-frontier`) + `ModelRouter.route()` (gateway) and `ModelTierResolver` (rag-engine) | P3 (ADR-0035) | Adding a selectable **FT tier** (capability) |
| Global vLLM chat backend switch `atlas.chat.backend=vllm` → OpenAI-compatible `ChatModel` at `ATLAS_VLLM_BASE_URL` | P5/P6 (ADR-0068, `VllmChatConfig`) | **Multi-LoRA** serving of base + adapter (episodic) |
| GPU provisioner `infra/gpu` (`python -m atlas_gpu up/down/run`, guaranteed pause-in-`finally` + watchdog) | ADR-0066/0029 | Episodic window to serve + measure cost-per-request |
| Prometheus + Alertmanager + Grafana; pushgateway; metrics `atlas_eval_gate_passed`, `atlas_eval_metric_score`; rule `AtlasEvalGateFailing` | P2/P3 (ADR-0063) | **Version-tagged drift rule** + one-shot seeded alert |
| CI eval-gate job `ci.yml` → `evals-gate` (required check), `deploy.yml` → `gate` | P2 | Where the **promotion-gate step** slots in (GPU-free) |

**Hard boundary with P6.** P6 *produced and committed* a registered adapter + a base-vs-FT bundle. P6
enforces **no** promotion gate, serves **no** adapter, ships **no** drift rule and **no** router FT tier
(all explicitly deferred to P7 in `P6_SPEC.md §1`). P7 adds exactly those four things — **as committed
proof**, not uptime.

**Reality check we must design around (from the committed P6 run):**
faithfulness base **0.787** → ft **0.678** (Δ **−0.109**, still **above** the 0.656 floor);
format_validity **0.000** → **0.955**; refusal_correctness **0.375** → **0.375** (Δ 0).
So the real adapter **clears absolute floors** but **regresses faithfulness beyond the P2 0.05 band**.
Whether that adapter is "promotable" is the central design question — see **§3 D2** and **§7 Q1**.

---

## 1. Scope

### In scope
1. **GPU-free CI model-promotion gate** (`evals/`) that consumes the **committed** `training/results/comparison.json` and decides promote/block against **model-promotion floors** (faithfulness / format-validity / refusal-correctness) **plus a cost-regression check**. Wired into `ci.yml` as a required check alongside the P2 gate.
2. **Proof-it-bites fixtures**: a committed **passing** comparison (the real P6 adapter) **and** a committed **sub-floor** comparison fixture — the CI run shows the bad one **blocked**, the good one **promoted**.
3. **Base-vs-FT benchmark, extended with cost-per-request** (`COMPARISON.md` + `results/*.json`): quality (faithfulness/format/refusal, already committed) **and measured cost/latency-per-request, base vs FT on the same GPU** — the headline artifact, same format as `infra/bench`.
4. **Router FT-tier capability** (Java: gateway + rag-engine): the router **can select** a fine-tuned tier for the citation/refusal path, served by **vLLM multi-LoRA** (base + adapter). Proven by an **integration test** (capability, not uptime). Frontier tier stays shipped-**disabled**.
5. **vLLM multi-LoRA serving profile** (`infra/`, episodic): base model + LoRA adapter hot-loaded, OpenAI-compatible, brought up by the `infra/gpu` provisioner only to generate benchmark evidence + run the router IT, then **torn down**.
6. **One-shot drift demo**: a **seeded regression** pushes a degraded, **version-tagged** eval metric and fires an **Alertmanager** rule; the fired alert is captured as a **committed artifact**. No always-on monitor.
7. **Model-lifecycle operations**: MLflow registry **stage/alias transitions** for **promote** and **rollback**; a documented rollback runbook (registry demotion + router re-point). `docs/RUNBOOK.md` updated.
8. **One-command GPU-free reproduce**: `docker compose up mlflow` → browse registry → run the promotion gate on committed artifacts (satisfies the 30-second DoD path).
9. **Docs**: `docs/DECISIONS.md` (ADR-0075…), `evals`/`gateway`/`infra` README deltas, quantified `docs/PORTFOLIO.md` bullet.

### Non-goals (explicit — prevent scope creep)
- **No always-on GPU / always-on FT endpoint.** The FT tier is a **proven capability**, served episodically to generate evidence, then torn down. Production default stays the small tier.
- **No new fine-tune / retrain.** P7 consumes the P6 adapter as-is. If a better adapter is needed to pass the chosen gate semantics, that is a **P6 re-run**, called out in §7 Q1 — not silent scope.
- **No new eval datasets or new metrics.** Reuses golden/adversarial + the P6 comparison metrics. No new RAGAS metric.
- **No LLM-judge in the promotion gate.** The gate is **deterministic + replay only** (faithfulness read from committed `comparison.json`; format/refusal recomputable deterministically). GPU-free is a hard constraint.
- **No always-on statistical drift monitoring / data-drift detectors.** One **seeded, one-shot** alert demonstrating the plumbing — not a production drift service.
- **No frontier tier enabled.** `frontier-enabled=false` remains; P7 does not wire a live frontier path.
- **No auto-promotion in production traffic.** Promotion is a **gated, human-triggered** registry transition; the router selecting the FT tier is a capability test, not a rollout.
- **No new datastore.** MLflow reuses `atlas-postgres`; adapter stays on HF Hub (P6, ADR-0072).
- **No embedding-model change.** pgvector stays pinned to `nomic-embed-text` (768-dim, ADR-0005).
- **No Alertmanager external routing** (Slack/PagerDuty) newly wired — the receiver stays the documented no-op stub; the demo captures the *fired* alert.
- **No shadow / canary evaluation on live production traffic.** The 2026 "eval-before-deploy → canary with auto-rollback" pattern assumes an always-on endpoint; Atlas's posture is a **committed offline evidence bundle** + a capability test. Canary/shadow is noted as the natural next step, deliberately out of P7 scope.
- **No always-on statistical drift service** (PSI/KS/CUSUM over sliding windows). P7 ships a **one-shot, seeded** threshold-vs-baseline alert to prove the plumbing; the windowed-statistical-test upgrade is called out as future work (§8), not built.

---

## 2. Design

### 2.1 Language / runtime split (and why)
| Concern | Language | Why |
|---|---|---|
| Promotion gate, floors, comparison-consumer, drift-metric emitter, fixtures | **Python** (`evals/`) | The gate must run in the **same GPU-free CI harness** as the P2 gate and **reuse P6's deterministic scorers verbatim**. Python is where evals live. |
| Cost-per-request measurement + vLLM multi-LoRA serving driver | **Python** (`training/` + `infra/gpu`) | Reuses the P6 episodic driver (`run_episodic.py`, `cost.py`) and the tested provisioner; it talks to vLLM over the OpenAI-compatible API. |
| Router FT-tier selection (decision + tier→model/endpoint resolution) | **Java / Spring Boot** (`gateway` + `rag-engine`) | The router is the production request path (ADR-0035); tiering is a **core Java moat** concern. The FT tier must live where routing already lives, exercised by JUnit integration tests. |
| MLflow registry stage/alias transitions | **Python** (`training/atlas_training/tracking.py`) | Registry client already lives here; promote/rollback are registry ops, GPU-free. |
| Drift alert rule + serving/observability wiring | **YAML / infra** (`infra/prometheus`, `infra/docker-compose*.yml`) | Alertmanager rule + vLLM env, no application code. |

**Net**: the *gate and evidence* are Python (GPU-free, CI-native); the *router capability* is Java
(the production moat); serving + alerting are infra config. No Java is written for the gate itself.

### 2.2 Component breakdown
1. **`evals/atlas_evals/promotion_gate.py`** *(new)* — pure `evaluate_promotion_gate(comparison, floors) -> PromotionGateResult` + CLI `python -m atlas_evals.promotion_gate`. Loads a committed `comparison.json`, applies model-promotion floors + cost-regression, exits non-zero on block. Mirrors `gate.py`'s pure-function-plus-thin-CLI shape.
2. **`evals/data/promotion-floors.json`** *(new)* — committed floor config for the gate (see §2.3). Kept **separate** from `baseline.json` so the code-merge bar and model-promotion bar are independently legible, while *referencing* the same faithfulness floor value (0.656).
3. **Fixtures** *(new)* — `evals/data/promotion/pass/comparison.json` (symlink/copy of the real P6 result) and `evals/data/promotion/blocked/comparison.json` (a hand-authored **sub-floor** adapter). Drive the proof-it-bites CI matrix.
4. **`training/atlas_training/report.py`** *(extend)* — add **cost-per-request** (and latency) fields to `ComparisonResult` for base vs FT; keep `{base, ft, delta}` schema stable so the gate is unaffected.
5. **`training/scripts/run_episodic.py`** *(extend)* — after generating base/FT outputs, also record **cost/latency per request** on the same GPU (reuse `cost.py` `CostMeter`); optionally drive generation **through vLLM multi-LoRA** (see §3 D4/D6).
6. **`training/atlas_training/tracking.py`** *(extend)* — `promote(name, version)` / `rollback(name)` via MLflow **aliases** (or stages — §3 D5). GPU-free.
7. **Gateway router FT tier** *(extend, Java)* — `ModelTier` gains a fourth constant (e.g. `TIER_FT_CITATION("tier-ft-citation")`); `ModelRouter.route()` selectable **only** behind an enable flag + explicit hint (never auto-selected in prod); `CostTable`/switches updated. `RoutingProperties` gains `ftTierEnabled` + `ftTierModel` (the vLLM LoRA name).
8. **rag-engine tier resolution** *(extend, Java)* — `ModelTierResolver` maps the FT tier to the vLLM LoRA model name; `ModelTierProperties` + `application.yml` gain the FT keys. (See §3 D6 for the endpoint-switch limitation.)
9. **vLLM multi-LoRA serving** *(infra, episodic)* — provisioner serves the base with `--enable-lora` (+ `--max-loras`, `--max-lora-rank` sized for the adapter); base and adapter are addressable as **distinct model names** on one endpoint. Adapters may be pre-registered at startup **or** hot-loaded at runtime via vLLM's dynamic LoRA API (`POST /v1/load_lora_adapter`, gated by env `VLLM_ALLOW_RUNTIME_LORA_UPDATING=1`) — the served path P7 verifies (R6). Used only in the episodic window; env `ATLAS_VLLM_*` already plumbed.
10. **Drift rule + emitter** *(infra + evals)* — a small `evals` step pushes a **version-tagged** degraded `atlas_eval_metric_score{model_version=…}` to pushgateway; a new Alertmanager rule (`AtlasModelQualityDrift`) fires; the fired alert JSON is captured (`amtool`/API) as a committed artifact. *(Method: threshold-vs-registered-baseline with a `for:` window — deliberately simple for a one-shot demo; a production build would use PSI/KS/CUSUM over a sliding window, see §8.)*
11. **Docs** — DECISIONS ADRs, RUNBOOK rollback section, PORTFOLIO bullet.

### 2.3 Data models / schemas
**`comparison.json` (consumed; extended with cost):**
```json
{
  "base_model": "Qwen/Qwen2.5-7B-Instruct",
  "ft_model": "hf://venkat2393/atlas-citation-adapter@<rev>",
  "n_cases": 30,
  "metrics": {
    "faithfulness":        {"base": 0.787, "ft": 0.678, "delta": -0.109, "ci95_delta": [-0.19, -0.02], "p_value": 0.03, "significant": true},
    "format_validity":     {"base": 0.000, "ft": 0.955, "delta":  0.955, "ci95_delta": [0.88, 1.00],  "p_value": 0.00, "significant": true},
    "refusal_correctness": {"base": 0.375, "ft": 0.375, "delta":  0.000, "ci95_delta": [-0.12, 0.12], "p_value": 1.00, "significant": false}
  },
  "n_cases": 30, "ci_method": "paired_bootstrap_10k", "sig_test": "wilcoxon",   // NEW in P7 (§3 D8)
  "cost": {                                     // NEW in P7
    "base": {"cost_units_per_req": 0.0, "latency_ms_p50": 0, "latency_ms_p95": 0},
    "ft":   {"cost_units_per_req": 0.0, "latency_ms_p50": 0, "latency_ms_p95": 0},
    "delta_pct": 0.0, "same_gpu": "L4"
  }
}
```
**`promotion-floors.json` (new, gate config):**
```json
{
  "faithfulness":        {"abs_floor": 0.656, "max_regression_vs_base": 0.05, "mode": "<see D2>"},
  "format_validity":     {"abs_floor": 0.95},
  "refusal_correctness": {"min_delta_vs_base": 0.0},
  "cost": {"max_regression_pct_vs_base": 10.0},
  "block_reason_required": true
}
```
**`PromotionGateResult`:** `{promoted: bool, decisions: [{metric, value, base, threshold, rule, passed}], blocked_reasons: [str], model_version: str, evaluated_at, git_sha}`. Emitted as `evals/report/promotion.json` + `promotion-summary.md` (same emitter style as `report.py`).

**Router:** `ModelTier` enum + `RoutingDecision(tier, model, escalated, reason)` unchanged in shape; a new `TIER_FT_CITATION` value + `ftTierModel` config. **Drift metric:** `atlas_eval_metric_score{metric, model_version}` (adds `model_version` label).

### 2.4 Key interfaces & contracts
- **Gate CLI:** `python -m atlas_evals.promotion_gate --comparison <path> --floors evals/data/promotion-floors.json` → exit 0 promote / non-zero block; always writes `evals/report/promotion.{json,md}`. **No network, no GPU, no RAGAS import** (contract).
- **CI contract:** a new required check **"Model promotion gate (base-vs-FT, floors + cost)"** in `ci.yml`; runs the gate over **both** fixtures (pass ⇒ exit 0; blocked ⇒ exit non-zero, asserted). Must not rename the existing `evals-gate` check (branch protection).
- **Router contract:** with `atlas.router.ft-tier-enabled=true` **and** an explicit FT hint, `route()` returns `TIER_FT_CITATION`; with the flag off (prod default) it is **never** selectable — an IT asserts both directions. Frontier remains disabled.
- **Registry contract:** `promote(name, version)` sets the production alias/stage; `rollback` re-points to the prior version; both are idempotent and logged. The router's `ftTierModel` maps to the served LoRA name.
- **Drift contract:** pushing a metric below its version-tagged baseline fires `AtlasModelQualityDrift` within the rule's `for:` window; the fired alert is captured to a committed file.

### 2.5 Request / data flow
**(a) CI promotion gate (GPU-free, every PR):** committed `comparison.json` → `promotion_gate` applies floors + cost-regression → `promotion.{json,md}` + exit code → CI green/red. Run twice (pass + blocked fixtures) = proof-it-bites.
**(b) Episodic evidence generation (one GPU window):** `infra/gpu up` → provisioner serves **vLLM base + LoRA** → `run_episodic.py` replays golden/refusal cases through base and FT, records outputs + **cost/latency per request** → writes extended `comparison.json` + `COMPARISON.md` → `register_adapter.py` records the MLflow version → `infra/gpu down` (guaranteed). All committed.
**(c) Router capability (JUnit IT, no GPU):** IT boots gateway with `ft-tier-enabled=true`, sends a query with the FT hint, asserts `route()`→FT tier and the `X-Atlas-Model-Tier` header is forwarded; a rag-engine IT asserts `ModelTierResolver` maps FT→the LoRA model name (vLLM call mocked).
**(d) Drift demo (one-shot, GPU-free):** emitter pushes a degraded version-tagged score → Prometheus scrapes pushgateway → `AtlasModelQualityDrift` fires → alert captured → committed artifact + RUNBOOK note.
**(e) Rollback (documented op):** `rollback(name)` demotes the registry version + router `ft-tier-model` re-point → RUNBOOK step.

---

## 3. Decisions to make now

> Options + trade-offs + recommendation. **Confirm and I will log them in `docs/DECISIONS.md`** as
> **ADR-0075…0082**, theme tag **`Promotion`**.

### 3.1 Owner-confirmed (2026-07-01)
| # | Decision | Confirmed choice |
|---|---|---|
| D1 | Gate module & floor location | **New `promotion_gate.py` + `promotion-floors.json`** (recommended default) |
| D2 | Faithfulness gate semantics | **Hybrid** — promote iff `ft ≥ 0.656` floor **AND** (`ft ≥ base − 0.05` **OR** format-validity jumped) **AND** refusal `Δ ≥ 0` **AND** cost OK. The **real P6 adapter is the committed "promoted" example**; **no new fine-tune required** |
| D3 | Cost-regression check | **Relative 10% band** on cost-units-per-request vs base; p95 latency reported alongside (report-only) |
| D4 | Candidate-output path | **Serve + regenerate base-vs-FT through the vLLM multi-LoRA served path** in one bounded L4 window (best train-serve-skew / R6 coverage) + measure cost/latency + run router live-IT |
| D5 | Promote/rollback mechanism | **MLflow aliases** (`@champion`/`@challenger`), with the legacy-stage equivalent narrated in docs (recommended default) |
| D6 | Router FT-tier wiring | **New `TIER_FT_CITATION`** enum, model-name = served LoRA on the single multi-LoRA vLLM backend; **flag-gated, never auto-selected in prod** (recommended default) |
| D7 | Drift mechanism | **Version-tagged metric + new `AtlasModelQualityDrift` rule** (recommended default) |
| D8 | Statistical rigor of the delta | **Report-only paired-bootstrap 95% CIs + paired significance (Wilcoxon/McNemar)** in `comparison.json`/`COMPARISON.md`; confirmed hybrid gate unchanged; seam left for a significance-aware gate (confirmed 2026-07-01, Q6) |
| — | ADR theme tag | **`Promotion`** (ADR-0075…0082) |

*Detailed options/trade-offs that produced these choices are retained below for the decision log.*

### D1 — Promotion-gate module shape & floor location
- **(a) New `promotion_gate.py` + new `promotion-floors.json`** — separate from the P2 `gate.py`/`baseline.json`. Clean separation of "code-merge bar" vs "model-promotion bar"; each independently legible; reuses P6 scorers.
- **(b) Extend `gate.py`** with a `--promotion` mode reading `comparison.json`. Less new code, one entrypoint; but overloads the P2 gate's semantics (replay-scored code vs pre-scored model deltas) and risks coupling two required checks.
- **(c) Put the gate in `training/`** next to `report.py`. Co-located with the producer; but splits the eval-harness story and duplicates gate plumbing.
- **Recommendation: (a).** A dedicated gate mirrors `cost_gate.py`'s precedent (its own baseline file), keeps the two required CI checks decoupled, and lets the promotion floors *reference* the P2 faithfulness floor (0.656) without entangling the two calibration lifecycles. "The model bar inherits the P2 floor value, not the P2 gate object."

### D2 — Promotion floor **semantics** for faithfulness (the load-bearing decision)
Given the real adapter (faithfulness 0.787→0.678, Δ −0.109; **above** the 0.656 floor but **outside** the P2 0.05 no-regression band):
- **(a) Absolute-floor-only:** promote iff `ft ≥ 0.656` (P2 floor) AND `format_validity ≥ 0.95` AND `refusal Δ ≥ 0` AND cost-regression OK. → **The real P6 adapter PASSES** (it's the "promoted" example); a fabricated sub-floor fixture is "blocked". Simple, ships today. **Tolerates a real faithfulness regression vs base** — must be argued honestly (the deliberate concise-format trade-off P6 documented).
- **(b) No-regression band (reuse P2 `max_regression`=0.05):** promote iff `ft ≥ base − 0.05` (and floor, format, refusal, cost). → **The real P6 adapter is BLOCKED** (Δ −0.109 > 0.05). Strict; identical bar to the code-merge gate; but then the "promoted" example requires a **better adapter (a P6 re-run)** — extra episodic GPU + scope (see §7 Q1).
- **(c) Hybrid (recommended):** promote iff **`ft ≥ 0.656` floor AND (`ft ≥ base − 0.05` OR format-validity improved ≥ a large margin AND refusal not regressed)** — i.e., allow a *bounded, justified* faithfulness regression **only** when it buys the format/refusal objective the fine-tune exists for, and never below floor. Encodes P6's "honest regression" finding as a policy. The real adapter **passes** (floor + format jump), a sub-floor or format-flat fixture is **blocked**.
- **Recommendation: (c) hybrid**, *falling back to (a)* if you prefer maximum simplicity. (c) tells the strongest portfolio story — "the gate accepts a *deliberate, bounded* quality trade-off but blocks silent regression and sub-floor adapters" — and lets the **committed real adapter be the passing example** with no P6 re-run. **This choice is coupled to §7 Q1 — please confirm.**

### D3 — Cost-regression check for model promotion
Note: base and FT share the **same 7B family** (base = `Qwen2.5-7B-Instruct`, FT = base + LoRA), so $/token is ~equal; the real cost signal is **latency/throughput** under vLLM multi-LoRA (adapter overhead), not price.
- **(a) Relative cost-per-request band:** block if `ft cost/req > base × (1 + 10%)`. Matches the P3 cost-gate philosophy; robust to absolute-unit drift.
- **(b) Absolute cost-per-request ceiling** (units): simplest, but arbitrary for same-family models.
- **(c) Latency-p95 regression band** instead of cost units: most honest for LoRA-overhead, but introduces a new metric surface.
- **Recommendation: (a) relative band on cost-units-per-request, with p95 latency reported alongside (report-only).** Reuses the P3 "regression-vs-baseline" pattern the reviewer already knows; latency shown for context. Threshold **10%** (tunable) — confirm in §7 Q2.

### D4 — Candidate-output generation path for the P7 benchmark
- **(a) Reuse P6's committed base/FT quality outputs**; the **only** new GPU work is measuring **cost/latency per request** on the same GPU (+ the router IT against live vLLM). Minimal GPU, tightest boundary.
- **(b) Regenerate everything through vLLM multi-LoRA** in a fresh window — most "production-faithful" (serving path == eval path), but re-does P6 quality work and costs more GPU.
- **Recommendation: (b) generate cost/latency AND re-derive quality through the vLLM multi-LoRA path in one episodic window**, because P7's whole point is proving the **served** adapter (not the PEFT/Transformers path P6 used) clears the bar — this is exactly the **train-serve-skew (R6)** risk. Keep it to **one** bounded window. If GPU budget is tight, fall back to (a) and treat quality as inherited. **Confirm budget in §7 Q3.**

### D5 — MLflow promote/rollback mechanism
- **(a) Registry aliases** (`@champion` / `@challenger`; MLflow ≥2.9) — the modern, non-deprecated API; promote = move `@champion`; rollback = re-point. Cleanest, future-proof.
- **(b) Legacy stages** (`Staging`/`Production`/`Archived`) — classic, instantly recognizable in interviews, but **deprecated** in current MLflow.
- **(c) Version tags** (`promoted=true`) — trivial, but not a real lifecycle primitive.
- **Recommendation: (a) aliases, and *narrate* the legacy-stage equivalent** in DECISIONS/README (so the interview covers both). Promote/rollback become alias moves the router reads indirectly (via `ftTierModel`). *(Web-confirmed 2026-07: MLflow ≥3.9 has deprecated Staging/Production/Archived stages in favour of aliases + tags; serving code should resolve `@champion`, never a version number, for instant rollback. Fallback: if a hosted registry lacks alias APIs, use a `champion=true` version **tag** as a pseudo-alias — not our case on self-hosted OSS MLflow.)*

### D6 — Router FT-tier wiring (given vLLM backend is a **global** switch, not per-route)
Current limit (confirmed): `atlas.chat.backend` picks **one** global `ChatModel`; the per-request `X-Atlas-Model-Tier` header only swaps the **model-name string**, not the endpoint.
- **(a) FT tier = a new `ModelTier` whose model-name is the vLLM LoRA name**, served by the **same** global vLLM backend (base + LoRA both hosted by one vLLM with `--enable-lora`). The tier switch stays a **model-name swap** — no per-route endpoint switching needed. Fits the existing architecture; multi-LoRA is a vLLM feature.
- **(b) Per-route endpoint switching** (each tier can point at a different base-URL) — most flexible, but a real router refactor (ADR-0068 territory) and larger Java surface than P7 warrants.
- **(c) Reuse `tier2-mid`** to point at the FT model — no enum change, but conflates "mid quality" with "fine-tuned" and muddies the cost table + story.
- **Recommendation: (a).** A dedicated `TIER_FT_CITATION` (enable-flag-gated, never auto-selected) whose model-name is the served LoRA, on the **single** vLLM backend with multi-LoRA. Proves router tiering + multi-adapter serving **without** a router endpoint-refactor. Frontier stays disabled.

### D7 — Drift-alert mechanism
- **(a) Version-tagged metric + new rule** `AtlasModelQualityDrift`: emitter pushes `atlas_eval_metric_score{metric,model_version}`; rule fires when a version's score drops below its registered baseline by a margin for `for: <window>`. Purpose-built; shows lead-time.
- **(b) Reuse `AtlasEvalGateFailing`** (binary `atlas_eval_gate_passed==0`) — zero new rule, but it's pass/fail, not "drift", and not version-tagged.
- **Recommendation: (a).** A dedicated version-tagged drift rule is the honest artifact for R6/R7 and yields a measurable **alert lead-time** number for PORTFOLIO. Seeded one-shot; no always-on monitor.

### D8 — Statistical rigor of the base-vs-FT delta *(web-validated 2026-07-01; owner-confirmed report-only — §7 Q6)*
With **N=30** cases, deciding promote/block on **point deltas** alone is the "statistical-power problem" (2026 consensus: report **confidence intervals + paired significance**, not point estimates). The real run makes this concrete: format Δ +0.955 is obviously significant, but faithfulness Δ −0.109 on N=30 may or may not be.
- **(a) Point deltas only** (status quo) — simplest; but a −0.109 "regression" could be noise, and a small format gain could be luck. Weakest interview story.
- **(b) Report-only CIs + paired significance** — the gate still decides on the confirmed hybrid floors, **but** `comparison.json` additionally carries **paired-bootstrap 95% CIs** on each metric delta and a **paired significance test** (Wilcoxon signed-rank for continuous faithfulness; McNemar for binary format/refusal). Surfaced in `COMPARISON.md`; no new blocking logic. Low risk, high signal.
- **(c) Significance-aware gate** — additionally **don't block** on a faithfulness regression whose CI crosses 0 (not significant) and **don't credit** a format gain that isn't significant. Most rigorous, but couples gate behavior to a stats test and can make the gate harder to reason about.
- **Recommendation: (b) now, design the seam for (c).** Add CIs + paired significance as **report-only** fields (non-breaking; the confirmed hybrid gate is unchanged), and note (c) as a fast-follow. This directly hardens the "honest regression" narrative — we can *state whether the −0.109 is statistically real* — at near-zero risk. (Also mitigates the small-N weakness of the whole benchmark.)

---

## 4. Test strategy

**Principle (inherited):** CI stays **GPU-free and green**. The promotion gate runs against **committed**
artifacts; the GPU is episodic and produces committed evidence only.

### 4.1 Unit tests (offline, in CI — the bulk)
- `evaluate_promotion_gate`: table-driven over the chosen D2 semantics — pass (real-adapter-shaped), block-on-faithfulness-below-floor, block-on-format<0.95, block-on-refusal-regression, block-on-cost-regression; each asserts `blocked_reasons` content (reason-required contract).
- Floor-config loader: rejects malformed/unpinned `promotion-floors.json`; round-trips.
- `comparison.json` schema/cost-field validator (missing metric ⇒ hard fail; cost block well-formed).
- Report emitter: fixture in → expected `promotion.json` + `promotion-summary.md`.
- MLflow `promote`/`rollback` (client mocked): alias moves + idempotency; rollback restores prior version.
- Drift emitter: builds correct version-tagged Prometheus text; below-baseline value crosses the rule threshold (rule expression unit-checked with `promtool test rules`).

### 4.2 Integration tests
- **Router FT-tier IT (JUnit, gateway):** `ft-tier-enabled=true` + FT hint ⇒ `route()`→`TIER_FT_CITATION`; flag off ⇒ never selected; frontier stays disabled. Header forwarding asserted.
- **rag-engine resolver IT (JUnit):** FT tier ⇒ vLLM LoRA model-name; vLLM call mocked (no GPU).
- **MLflow round-trip IT** (local `mlflow` container, CPU): register a version, `promote`, read alias, `rollback`.
- **`promtool`/`amtool` rule IT:** seeded degraded metric ⇒ `AtlasModelQualityDrift` fires; capture fired alert.
- **Episodic serving smoke (`@live`, not in CI):** vLLM base+LoRA up via provisioner; one base + one FT request; asserts adapter is served + cost/latency recorded. Guaranteed teardown.

### 4.3 Eval / promotion gate (phase touches RAG/model → **required**)
- **Datasets:** reuse golden (`evals/data/golden.jsonl`, 22) + adversarial (10) + the P6 refusal subset. No new sets.
- **Metrics & floors (candidate vs base), per §3 D2/D3:**
  - **faithfulness** — abs_floor **0.656**; regression policy per confirmed D2 (recommend hybrid: bounded regression allowed only above floor when format improves).
  - **format-validity** — abs_floor **0.95** (real ft 0.955 passes; base 0.000 blocks — the contrast headline).
  - **refusal-correctness** — `Δ ≥ 0` vs base.
  - **cost-per-request** — regression ≤ **10%** vs base (same GPU), latency-p95 report-only.
- **Proof-it-bites (the gate's own gate):** CI runs the promotion gate over **both** committed fixtures — asserts the **passing** adapter promotes (exit 0) **and** the **sub-floor** fixture is blocked (exit non-zero, expected). This dual run is the committed evidence.
- **Statistical rigor (D8, report-only):** `comparison.json`/`COMPARISON.md` carry **paired-bootstrap 95% CIs** on each metric delta + a **paired significance test** (Wilcoxon / McNemar). Unit-tested on fixtures with known CIs; states whether the faithfulness −0.109 is statistically real. Non-blocking in P7.
- **Adversarial 100%-pass** remains a promotion precondition (no adapter promoted if it leaks above-clearance context in the refusal lane) — reuse `score_adversarial`.

### 4.4 Regression gate (inherited — must stay green)
- Existing P2/P5 checks (`evals-gate` RAGAS replay, adversarial, cost-regression, agent gate) and all Java tests (gateway/rag-engine/mcp) must stay green. The new `ModelTier` value must not break `ModelRouterTest`/`CostTableTest`/`ModelTierResolverTest` (exhaustive switches updated).

---

## 5. Task breakdown (ordered, independently committable)
1. **Promotion floors config + schema** — add `evals/data/promotion-floors.json` (per confirmed D2/D3) + a loader/validator. *(Unit.)*
2. **`promotion_gate.py`** — pure `evaluate_promotion_gate` + thin CLI + `promotion.{json,md}` emitter, reusing P6 scorers; no GPU/RAGAS import. *(Unit, table-driven.)*
3. **Proof-it-bites fixtures** — commit `evals/data/promotion/pass/comparison.json` (real P6 result) + `.../blocked/comparison.json` (hand-authored sub-floor). *(Consumed by CI.)*
4. **CI wiring** — new required check running the gate over both fixtures (assert promote + block); `deploy.yml` mirror. *(CI.)*
5. **`report.py` + `run_episodic.py` cost extension** — add cost/latency-per-request base-vs-FT fields **and paired-bootstrap 95% CIs + a paired significance test (Wilcoxon/McNemar) per metric (D8, report-only)**; keep `{base,ft,delta}` stable. *(Unit on emitter + CI/significance math on fixtures; real capture is episodic.)*
6. **MLflow `promote`/`rollback`** — alias transitions in `tracking.py` + `scripts/promote.py`/`rollback.py`. *(Unit mocked + local-container IT.)*
7. **Router FT tier (gateway Java)** — `ModelTier.TIER_FT_CITATION`, `RoutingProperties.ftTier*`, `route()` flag-gated selection, `CostTable`/switch updates + `application.yml`. *(JUnit unit + IT.)*
8. **rag-engine FT resolution (Java)** — `ModelTierResolver` FT→LoRA-name, `ModelTierProperties` + `application.yml`. *(JUnit unit + IT.)*
9. **vLLM multi-LoRA serving profile (infra/gpu)** — provisioner `--serve vllm --enable-lora <adapter>`; env plumbing; documented episodic bring-up. *(`@live` smoke.)*
10. **Drift rule + emitter** — version-tagged `atlas_eval_metric_score`, `AtlasModelQualityDrift` in `alerts.rules.yml`, emitter step, capture script. *(`promtool` test + unit.)*
11. **Episodic evidence run** — one GPU window: serve vLLM base+LoRA, generate cost/latency (+ quality if D4=(b)), commit extended `COMPARISON.md`/`results/*`, register + `promote` the version, tear down. *(The evidence drop.)*
12. **Rollback runbook + docs** — `RUNBOOK.md` rollback section; `DECISIONS.md` ADR-0075…0082; README deltas; quantified `PORTFOLIO.md` bullet.

---

## 6. Definition of Done (P7 — generic CLAUDE.md DoD, instantiated)
- [ ] **Code complete & matches this spec.** GPU-free promotion gate, router FT-tier capability, vLLM multi-LoRA episodic profile, drift rule, promote/rollback — all present and matching §2.
- [ ] **Unit + integration tests written & passing in CI (GPU-free):** promotion-gate table tests, floor loader, cost-field validator, report emitter, MLflow promote/rollback (mocked + local-container IT), router FT-tier IT (both directions), rag-engine resolver IT, `promtool` drift-rule test. Existing P2/P5 gates + all Java tests remain green.
- [ ] **Eval evidence met & recorded:** the promotion gate runs over **both** committed fixtures — a **sub-floor adapter is provably blocked** and a **passing adapter is promoted** (committed CI run = proof-it-bites). Recorded numbers: candidate Δ vs base (faithfulness/format/refusal) + **measured cost/latency-per-request base vs FT, same GPU**.
- [ ] **Base-vs-FT benchmark committed** (`training/results/COMPARISON.md` + `results/*.json`) with the cost/latency dimension added — same format as `infra/bench`.
- [ ] **Router integration test green** — router **can select** the FT tier for the citation/refusal path (capability, flag-gated); frontier stays disabled.
- [ ] **One-shot drift demo committed** — a seeded regression fires `AtlasModelQualityDrift`; the fired alert is a committed artifact with a measured **lead-time**.
- [ ] **Rollback path documented** — registry alias demotion + router re-point in `docs/RUNBOOK.md`.
- [ ] **Module README(s) + `docs/DECISIONS.md` updated** (ADR-0075…0082, tag `Promotion`).
- [ ] **Runs cleanly from scratch (GPU-free):** `docker compose up mlflow` → browse registry → `python -m atlas_evals.promotion_gate` over committed artifacts → see promote + block.
- [ ] **30-second demo path:** `docker compose up mlflow` → open the promoted registry version (source = HF repo@rev) → run the promotion gate showing the sub-floor adapter blocked → open `COMPARISON.md`. All GPU-free, committed.
- [ ] **Resume-ready, quantified bullet** in `docs/PORTFOLIO.md`: candidate Δ vs base (faithfulness/format/refusal); measured cost/latency-per-request base vs FT (same GPU); # promotions **blocked by the gate**; drift-alert **lead time**.

**Done when.** A committed CI run shows a sub-floor adapter **blocked** and a passing one **promoted**; the
router-integration test is green; the cost-extended base-vs-FT benchmark is committed; a seeded regression
fires the drift alert — all **reproducible from a fresh clone, no always-on GPU**.

**Quantify.** candidate Δ vs base (faithfulness / format-validity / refusal-correctness) **with paired
95% CIs + significance (D8)**; measured cost/latency-per-request base vs FT (same GPU); promotions blocked
by the gate (proof it bites); drift-alert lead time on the seeded regression.

---

## 7. Open questions / ambiguities
1. ~~**[D2] Faithfulness gate semantics & the "promoted" example.**~~ → **Resolved (§3.1):** **hybrid** —
   the real P6 adapter (Δ −0.109, above floor, big format jump) is the committed **"promoted"** example; a
   hand-authored sub-floor fixture is the **"blocked"** example. **No new fine-tune required.**
2. ~~**[D3] Cost-regression threshold.**~~ → **Resolved (§3.1):** **10%** relative cost-per-request band vs
   base; p95 latency report-only.
3. ~~**[D4/budget] Episodic GPU scope.**~~ → **Resolved (§3.1):** **one** bounded L4 window regenerates
   base-vs-FT through the **served vLLM multi-LoRA** path + measures cost/latency + runs the router live-IT
   (best R6 coverage).
4. ~~**[D6] Router FT-tier exposure.**~~ → **Resolved (§3.1):** FT tier is **flag-gated, never auto-selected
   in prod**; production default stays `tier1-small`; FT reachable only via explicit hint +
   `ft-tier-enabled=true`. Frontier stays disabled.
5. ~~**[tag] DECISIONS theme tag.**~~ → **Resolved (§3.1):** **`Promotion`** (ADR-0075…0082).
6. ~~**[NEW — D8, needs confirm] Statistical rigor of the base-vs-FT delta.**~~ → **Resolved (2026-07-01, Q6):**
   **report-only** — add **paired-bootstrap 95% CIs + a paired significance test (Wilcoxon/McNemar)** to
   `comparison.json`/`COMPARISON.md`; the confirmed hybrid gate logic is **unchanged** (non-breaking); leave a
   seam for a significance-aware gate as a fast-follow. Lets us state whether the faithfulness −0.109 is
   statistically real.

*All grooming questions (1–6) resolved 2026-07-01. Spec **approved**; ADR-0075…0082 (tag `Promotion`) logged
in `docs/DECISIONS.md`. Implementation not started (per owner).*

---

## 8. Web-validated refinements (2026-07-01)

A web-search pass against current (mid-2026) MLOps/LLMOps practice was run to gap-check this spec vs the
Atlas roadmap. Findings and resulting changes:

| # | Finding (source theme) | Verdict for P7 | Change made |
|---|---|---|---|
| W1 | **MLflow stages deprecated (≥2.9, hard in 3.9/2026) → aliases + tags**; champion/challenger; serving resolves an alias, never a version number, for instant rollback. | **Confirms D5.** Our alias choice is current, not legacy. | Annotated **D5** with the deprecation + tag-fallback note. |
| W2 | **vLLM multi-LoRA** supports base + N adapters as distinct model names on one endpoint, **plus runtime dynamic load/unload** via `/v1/load_lora_adapter` gated by `VLLM_ALLOW_RUNTIME_LORA_UPDATING`; sized by `--max-loras`/`--max-lora-rank`. | **Confirms D6/§2.2-9**, adds precision. | Tightened **§2.2 component 9** with the runtime API, env flag, and sizing knobs. |
| W3 | **Eval-gated promotion is the 2026 norm** ("eval before deploy", separate build from deploy, canary/shadow with auto-rollback). | Core design **validated**. Canary/shadow assume an always-on endpoint → **out of our committed-evidence scope**. | Added explicit **non-goal** (no shadow/canary on live traffic) + noted as fast-follow. |
| W4 | **Statistical rigor for small-N evals**: point estimates are underpowered; report **bootstrap CIs + paired significance** (Wilcoxon/McNemar), paired analysis, power-size the set. Directly hits our **N=30**, Δ −0.109 faithfulness call. | **Real gap.** The gate decides on point deltas. | Added **D8** (report-only CIs + paired significance; seam for a significance-aware gate), extended the **`comparison.json` schema**, **task 5**, **§4.3 tests**, and the **DoD quantify** line. Opened **§7 Q6**. |
| W5 | **Drift detection** best practice uses PSI/KS/CUSUM over sliding windows with noise-aware alerting; offline evals are necessary-but-insufficient vs online eval. | Our **one-shot seeded** threshold demo is honest for a portfolio, but shouldn't imply a production drift service. | Annotated **§2.2 component 10** + added a **non-goal** scoping the windowed-statistical-test upgrade as future work. |

**Net:** the roadmap's P7 shape holds up well against 2026 practice — the only substantive gap was
**statistical power on the small comparison set (W4)**, now addressed as a non-breaking, report-only
addition (**D8**) pending your confirm. W1–W3, W5 were precision/scope clarifications, not redesigns.

Sources consulted (themes): MLflow model-registry docs + stage-deprecation RFC #10336; vLLM LoRA-adapters
docs (runtime loading); LLMOps CI/CD eval-gate guides (2026); LLM-eval statistical-rigor / statistical-power
write-ups (2026); production model-drift-detection guides (2026).
