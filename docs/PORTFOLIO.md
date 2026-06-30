# Atlas — Portfolio Highlights

Resume-ready, quantified outcomes per phase. Atlas is a permission-aware, cost-routed, evaluated enterprise
AI copilot for a financial/compliance domain (**Spring AI + LangGraph + MCP**).
Repo: <https://github.com/venkathub/atlas-compliance-copilot>

---

## Production model serving — vLLM profile + on-GPU benchmark (2026-06-29)

**One-liner:** Added vLLM as a swappable, production-grade serving profile alongside Ollama and **proved**
the gain with a same-GPU benchmark — turning a synthetic cost-unit into a measured one.

**Resume bullets (draft):**
- Built a **from-scratch GPU provisioner** (JarvisLabs SDK) that creates a cloud GPU, installs and serves
  **Ollama and/or vLLM** behind an OpenAI-compatible endpoint, probe-classifies the public endpoints, and
  **guarantees teardown** (finally + idle watchdog) — live-validated end-to-end (create/pause/resume/destroy)
  for **≈₹45 (~$0.55)** total, surfacing and fixing 3 real cloud-only bugs.
- **Benchmarked vLLM vs Ollama on the same L4 GPU** (Qwen2.5-7B, on-box concurrency sweep): vLLM sustained
  **23.6× higher throughput** (1208 vs 51 tok/s at 32 concurrent requests) with **23× lower p99 latency**
  (3.0 s vs 69 s) thanks to **PagedAttention + continuous batching**, cutting **measured cost from ₹224 → ₹9.50
  per 1M output tokens (~24×)**.
- Kept **Ollama as the quantized dev/CI default** and added vLLM as the production chat profile —
  a cost-aware serving layer where the **chat backend is config-selectable** (`ATLAS_CHAT_BACKEND=ollama|vllm`:
  Spring AI's Ollama-native client or an OpenAI-compatible vLLM client), with **embeddings pinned to Ollama**
  (nomic-embed, 768-dim pgvector), and the benchmark harness + results committed for reproducibility.

**Evidence:** `infra/bench/results/{ollama,vllm}-L4.json` + `COMPARISON.md` · ADR-0066/0067/0068 · rag-engine
**`VllmChatLiveIT`** (real Spring `ChatModel` generated via vLLM) + `VllmChatConfigTest` · 98 rag-engine + 42 gpu
+ 16 bench tests green · **eval REPLAY gate PASS** (no RAG regression) · live runs on JarvisLabs L4 (instances
destroyed, balance verified).

**Quantified:** 23.6× throughput · 23× lower p99 · ~24× cheaper/token · vLLM scales 53→1208 tok/s (c=1→32)
while Ollama stays flat ~51 · all instances torn down (zero idle spend).

---

## Fine-tuning lifecycle — QLoRA + MLflow + HF registry + base-vs-FT eval (P6 · 2026-06-30)

**One-liner:** Owned the **training half** of the model lifecycle P0–P5 only consumed — a reproducible-from-
committed-config **QLoRA fine-tune** of Qwen2.5-7B for Atlas's citation-bound-answer format, with a
self-hosted-teacher synthetic dataset (trusted-corpus-only, LLM04), MLflow tracking + a Hugging Face Hub
model registry (adapter durable off-GPU), per-run cost capture, and an **honest base-vs-FT benchmark** —
all on a single episodic, self-destructing JarvisLabs L4 window.

**What shipped:** `training/` (new `uv` project) — pinned `qlora_*.yaml` run contract + fail-fast loader;
trusted-corpus loader + provenance manifest (`validate()` enforces every source resolves + grounded-only);
self-hosted-teacher synthetic generation (Ollama, citations post-enforced); deterministic train/val split;
QLoRA `SFTTrainer` (4-bit NF4, eval-loss early stop, loss→MLflow); HF-Hub push + MLflow version (source =
`hf://repo@rev`); per-run `CostMeter` (₹/hr × wall-clock); base/FT inference + comparison report. Plus
deterministic **format-validity + refusal-correctness** scorers in `evals/` (reused verbatim by P7's gate),
a Postgres-backed **MLflow** service in `/infra`, and a self-contained boot-script launcher that runs the
whole pipeline unattended and lands artifacts on HF. **GPU-free CI stays green** (135+ offline tests; the
heavy stack never installs in CI).

**The honest result (bake-in eval — no citation instruction given to either model):**

| Metric | base | ft | Δ | note |
|---|---|---|---|---|
| **format_validity** | **0.000** | **0.955** | **+0.955** | FT ≥ 0.95 target **met** — base can't cite unprompted |
| refusal_correctness | 0.375 | 0.375 | +0.000 | held |
| faithfulness | 0.787 | 0.678 | −0.109 | ft above the 0.656 floor; a structural trade-off (see below) |

> _Committed evidence: gpt-oss:20b-teacher run (₹49.9 / 71 min), `training/results/COMPARISON.md`,
> adapter `hf://venkat2393/atlas-citation-adapter@386e3d3…`._

**Two-teacher experiment (an honest negative sub-result that strengthens the story):** ran the
fine-tune with **both** a same-family `qwen2.5:14b` teacher and a stronger cross-family `gpt-oss:20b`
teacher. The **format-validity +0.955 win is robust across both** (the base scores 0.000 unprompted
either way). The stronger teacher did **not** improve faithfulness — it produced *terser* cited
answers, so faithfulness fell further (gpt-oss −0.109 vs qwen14b −0.062). Conclusion: the
faithfulness dip is a **structural trade-off of the concise citation format**, not a teacher-quality
gap — precisely what the **P7 promotion gate** is built to weigh.

**Quantified:** format-validity **0.00 → 0.955** (the FT guarantees `[doc:ID]` answers with **zero prompt
overhead**, where the base scores 0 without a ~60-token instruction) · adapter **versioned off-GPU** (HF +
MLflow, survives teardown) · **~₹50/run** measured (×2 teachers) · dataset **~150 pairs**, trusted-corpus-
only with a committed provenance manifest · **6 ADRs** (0069–0074) · base-vs-FT evidence committed in the
P7-gate schema.

**Why it's a senior-level story:** the benchmark is **honest** — it surfaced that a strong instruct base is
already near-ceiling *when instructed*, so the FT's real value is **internalizing the format** (the base
scores 0 unprompted). And the faithfulness −0.062 is exactly the kind of regression P7's promotion gate is
built to catch — the eval gate *works*.

### Challenges & traceability (episodic-run debugging log)
The fine-tune ran on a disposable L4 with **no SSH/exec** (the SDK allows only a boot script), so every issue
was diagnosed from the box log + HF artifacts and fixed forward. Each was caught **before** paid training
where possible, and the instance destroyed immediately (≈₹250 total across ~10 short instances).

| # | Challenge | Root cause | Fix (commit) |
|---|---|---|---|
| 1 | `uv sync --group train` / `import atlas_training` failed on the box | sibling projects weren't installable packages (no build-system) | hatchling backends for `atlas-evals` + `atlas-training` (`db66ff8`, `9358901`) |
| 2 | `SFTConfig` rejected `max_seq_length` | TRL API drift (renamed `max_length`) | rename + drop greedy `temperature` (`50c143c`) |
| 3 | `generate()` crashed on `.shape` | recent `apply_chat_template` returns a `BatchEncoding`, not a tensor | `return_dict=True` + `generate(**inputs)` (`ec56861`) |
| 4 | Ollama `404` model-not-found at generation | serve died across the long `uv sync`; models pulled against a stale serve | `ensure_ollama` (setsid + health-wait) re-checked pre-run; pull **after** final ensure; pciutils for GPU detect (`fbcd59a`, `e2efc39`) |
| 5 | RAGAS faithfulness timed out (~3 min/sample, all NaN) | torch 7B held the GPU → Ollama judge fell back to CPU | `free_gpu()` (empty_cache) after generation → judge on L4 (**6.7 s/item**) (`a2886c3`) |
| 6 | format-validity 0.0 for **both** base and FT | train/inference prompt mismatch — trained with the Atlas system prompt, evaluated without it | pass the same system prompt at inference (`11c73c9`) |
| 7 | FT regressed all metrics vs base | strong instruct base near-ceiling + distillation from a weaker teacher on ~150 pairs | **bake-in** (minimal system → FT learns format unprompted, +0.955) + stronger teacher (`9db1409`) |
| 8 | No way to run training on the box (SDK = boot script only) | JarvisLabs SDK exposes create/pause/destroy + boot script, no SSH/exec | self-contained boot script: clone public repo → install → run → upload results to HF (secrets in the JL-stored script only, never committed) (`19805d7`, `4b7c028`) |

**Lessons:** episodic-GPU MLOps is an *integration* problem (packaging, API drift, server lifecycle, GPU
contention, train/eval parity) more than a modelling one; an **honest** eval that can show a regression is
worth more than a vanity metric; and on a strong instruct base, the durable FT value is **format guarantee
with zero prompt overhead**, not raw accuracy.

---

## P0 — Foundations (complete · 2026-06-13)

**One-liner:** Stood up a reproducible, secure, CI-gated polyglot monorepo and proved an env-swappable
remote-LLM integration — the production scaffolding before any AI logic.

**Resume bullets (draft):**
- Bootstrapped a polyglot **Java/Spring + Python** monorepo with a **5-job GitHub Actions** gate
  (build/test, `ruff`/`pytest`, **gitleaks** secret scan, **Trivy** dependency/config scan, **Syft** SBOM),
  green on `main` — supply-chain controls mapped to **OWASP LLM03**.
- Built and validated a **multi-arch (amd64 + arm64) distroless** container image with a **digest-pinned**
  base for the **Oracle Ampere A1 ARM** target, layering the architecture-independent Spring Boot jar to
  build arm64 with **zero QEMU emulation**.
- Integrated **Spring AI 1.0 ↔ remote Ollama** with fully **env-swappable** model config and an automated
  **live smoke test** asserting a chat completion + a **768-dim** embedding, **gated out of CI** to keep the
  pipeline GPU-free.
- Engineered a **snap-Docker-confinement-safe** local stack (Postgres + pgvector, Redis) via stdin/exec
  patterns (no host bind mounts), reproducible with a single `make up`.

**Evidence:** CI run #2 green (5/5 jobs) · `mvn verify` + live IT (3/3) green · multi-arch manifest verified
(amd64 + arm64) · ADR-0008–0010.

**Quantified:** 6 commits · 5 CI jobs · 2 healthchecked services · pgvector 0.8.2 · warm chat ~0.75 s ·
embedding 768-dim · distroless image (no shell, nonroot).

---

## P1 — Permission-aware RAG (complete · 2026-06-13)

**One-liner:** Built the production RAG core — permission-aware hybrid retrieval over pgvector with
inline-cited, grounded answers and a hard, CI-gated guarantee of **zero cross-clearance leaks**.

**Resume bullets (draft):**
- Built a **permission-aware hybrid RAG engine** (Java/**Spring AI 1.0**, **pgvector/PG16**): dense **HNSW**
  + sparse **tsvector** retrieval fused with **Reciprocal Rank Fusion**, with hierarchical RBAC
  (`public<analyst<compliance<restricted`) **pushed into SQL** so above-clearance chunks are never fetched.
- Enforced the RBAC boundary as a **hard CI gate** — a negative-access golden set (6 scenarios × dense/sparse/
  hybrid = **18 assertions**) proves **0 of 18 cross-clearance leaks**; any leak fails the build.
- Shipped **grounded QA with chunk-level inline `[n]` citations** over `POST /v1/query`, with a defense-in-depth
  per-citation clearance re-check and a **no-LLM grounded-refusal** path when nothing authorized is found.
- Hardened ingestion + prompts against **OWASP LLM01/LLM04**: trusted-source-only admission with **SHA-256**
  provenance, and a prompt-injection guardrail that **quarantined 3/3 poisoned documents** (spotlighting +
  heuristic scanner) while preserving benign content.
- Engineered a deterministic, **GPU-free test suite** (**92 tests**: 58 unit + 34 **Testcontainers** ITs) via a
  stub embedder/chat model, keeping the whole RAG pipeline CI-verifiable without a GPU; real-model path covered
  by a profile-gated live E2E test.

**Evidence:** `mvn verify` green — 58 unit + 34 IT (incl. `RbacNegativeAccessIT` 18/18 no-leak, `PromptInjectionIT`
3/3, `IngestionIT` 24 docs/24 chunks) · ADR-0011–0020 · 7 feature commits.

**Quantified:** 24 documents / 24 chunks ingested · 4 clearance levels · 0/18 RBAC leaks · 3/3 injection payloads
quarantined · RRF k=60 · 768-dim embeddings · **live E2E green vs. real Ollama (`qwen2.5:3b`): `POST /v1/query`
p50 ≈ 5.5 s, 6-source cited compliance answer, per-caller RBAC enforced (public→public … compliance→compliance,
restricted never cited)** · OWASP LLM01/04/08/09 mapped. _(Grounded-citation + faithfulness recorded 2026-06-13;
automated as RAGAS thresholds in P2.)_

---
## P2 — Evaluation & observability (complete · 2026-06-14)

**One-liner:** Made RAG quality **measurable and non-regressable before any agent exists** — a CI-gated
RAGAS + adversarial eval harness, OTel `gen_ai.*` tracing into Langfuse, and Grafana dashboards, with a
deterministic offline gate and a fail-safe live-GPU calibration lane.

**Resume bullets (draft):**
- Built a **CI-gated RAG eval harness** (Python/**RAGAS 0.2**) over **22 golden cases** (12 authoritative
  **FinanceBench** + 10 authored AML/Northwind): merge-blocking floors on **faithfulness 0.80 /
  answer-relevancy 0.70 / context-recall 0.78** with a **no-regression band**, judged by a **cross-family
  `llama3.1:8b` LLM-as-judge at temp 0** (pinned to attribute drift to the RAG, not the judge).
- Shipped a **100%-pass adversarial/red-team gate** (OWASP **LLM01/LLM07**: prompt-injection, jailbreak,
  system-prompt-leak, access-bypass) — **0 violations across 10 cases** — reusing the P1 fixtures *by reference*
  so P1↔P2 cannot drift; plus a periodic **Promptfoo** OWASP sweep in the live lane.
- Made the merge gate **deterministic, offline, and free** via a **record/replay cassette** design (RAG +
  per-sample judge scores) — the per-PR gate runs with **no GPU, no Ollama, RAGAS not even installed**; a
  cassette miss fails loudly rather than silently calling out.
- Instrumented every retrieval + model call as **OpenTelemetry `gen_ai.*` spans** (Micrometer→OTel→Langfuse)
  with the required `gen_ai.client.operation.duration` + token metrics; **content-capture is OFF/redaction-gated
  by default** so above-clearance text/PII never reach the trace plane (**LLM02/LLM07**).
- Automated **fail-safe GPU cost discipline**: an `infra/gpu` driver resumes the rented GPU, health-polls,
  discovers the endpoint, and **guarantees a pause** (`finally`/trap + watchdog) — verified end-to-end against
  a live JarvisLabs instance (the live run caught 3 real bugs incl. machine-id-drift-on-resume).
- Drove the deferred reranker as an **evidence-based decision**: implemented an LLM-reranker + `websearch`
  sparse fix behind flags, ran a live harness **A/B**, and **re-deferred** them when the data showed a
  trade-off (precision/relevancy +0.07 but two gating metrics regressed) rather than a clear lift.

**Evidence:** `evals` 49 pytest + `infra/gpu` 24 pytest green; eval gate **PASS** (offline replay); Java
**74 unit + 40 IT** green incl. extended **D4 negative-access on `contexts[]` (24 cases)** + **D7 injection**;
live calibration recorded 22 cassettes + `baseline.json`; eval scores flow to Prometheus/Grafana via Pushgateway.
ADR-0021–0031.

**Quantified:** 22 golden + 10 adversarial cases · gating floors faithfulness ≥0.749 / relevancy ≥0.648 /
recall ≥0.711 · **adversarial 1.000 pass-rate (0 violations)** · judge `llama3.1:8b` @ temp 0 (pinned) ·
**offline gate: 0 GPU / 0 LLM calls** · 6 observability services (Langfuse v3 + ClickHouse + MinIO +
Prometheus + Pushgateway + Grafana) · GPU guaranteed-pause verified live · reranker A/B → evidence-based
re-deferral · OWASP LLM01/02/07 automated.

---
## P3 — Cost-aware gateway (complete · 2026-06-17)

**One-liner:** Built the production **Spring Cloud Gateway** front door — a single trust boundary that
authenticates, cost-routes, semantically caches (clearance-safe), rate-limits, caps spend, redacts PII, and
makes the cost story a live dashboard — and proved routing/caching never trade quality below the eval floor.

**Resume bullets (draft):**
- Built a **cost-aware API Gateway** (Java/**Spring Cloud Gateway WebMVC**) fronting the RAG engine:
  simulated-IdP **JWT trust boundary**, cost-aware model router, clearance-safe semantic cache, rate
  limiting, budget caps, circuit breaker, PII egress redaction, and token/cost/latency metering — the whole
  front door in one runtime.
- Realized a **verifiable-clearance trust boundary** (HS256 JWT, Nimbus): the gateway validates the caller
  token and **re-asserts a signed internal clearance** that rag-engine independently verifies, **retiring the
  P1 client-trusted header** (defense-in-depth) — P1 **D4 negative-access stays 0/24 leaks** through the gateway.
- Engineered a **clearance-partitioned semantic cache** on **Redis Stack / RediSearch** (KNN, native TTL,
  trusted-write) whose RBAC invariant is **structural** — a mandatory clearance-partition pre-filter makes a
  cross-clearance hit impossible — proven by a hard gate: **0 cross-clearance cache hits** against real Redis.
- Implemented the **OWASP LLM10** resource-control surface: a Redis **Lua token-bucket** rate limiter (429),
  per-user **daily budget caps** (402), per-request input-size (413) + max-output-token caps + timeout, and a
  **Resilience4j circuit breaker** with a typed **503 + Retry-After** fallback.
- Shipped **deterministic PII egress redaction (LLM02)** + **output sanitization (LLM05)** on the hot path —
  hard-gated to **0 restricted-PII strings and 0 unsafe payloads at egress** — with metadata-only redaction
  traces (counts/types, never the PII).
- Made cost a **first-class, observable feature**: Micrometer→Prometheus→**Grafana** dashboard for
  cost-units/tokens/latency per route/tier/user + cache hit-rate, rejections, redaction counts, and a
  cost-spike threshold panel; cost computed from **real model token usage** surfaced over the clean seam.
- Ran the **reused P2 RAGAS gate THROUGH the gateway path** (auth + route + cache + redact) as a CI step,
  proving routing/caching don't drop quality below the floor (**R2**), plus a `cost_report` harness that
  quantifies **% cheaper at equal eval score** (target band **≥30%**, ADR-0040/§8.3).

**Evidence:** `mvn verify` green — **gateway 59 unit + 14 IT**, **rag-engine 90 unit + 40 IT** — incl. hard
gates `RedisSemanticCacheIT` (0 cross-clearance hits, real Redis Stack), `PiiEgressGateTest` (0 PII / 0 unsafe),
`RbacNegativeAccessIT` 24/24 + `PromptInjectionIT` 3/3 still green through the trust boundary; `evals` 63 pytest
green; **both eval gates PASS (direct + through-Gateway)** against the live-recalibrated baseline. ADR-0033–0040.

**Quantified:** 8 ADRs (0033–0040) · 4 clearance levels · **0 cross-clearance cache hits** · **0/24 RBAC leaks** ·
**3/3 injection quarantined** · **0 PII strings / 0 unsafe payloads at egress** · token-bucket 60 req/min default ·
daily budget cap (cost-units) · breaker 50% / 10 s · cache cosine threshold 0.95 (eval-calibrated) ·
3 model tiers (small default / mid escalation / frontier reserved) · Redis Stack (multi-arch, digest-pinned) ·
HS256/Nimbus dual-hop JWT.

**Live-calibrated (real Cloud GPU, 2026-06-19):** re-recorded the RAGAS cassettes + recalibrated the baseline
through the Gateway (RAGAS floors hold — **routing/caching don't degrade quality, R2**); measured the
cost-delta end-to-end — a **semantic-cache hit serves a recurring query at ~0 serving cost (100% serving-cost
elimination on a hit; cold→warm ceiling 20.11 → 0.0 cost-units on the golden set)**, blended savings scaling
with the production repeat rate. The live run also **caught + fixed two real bugs** the fast offline stubs had
masked — Spring Cloud's default **1-second TimeLimiter** (which 503'd every real ~3 s model call) and the
semantic cache **not recreating its RediSearch index after a Redis restart** — each now covered by a
regression IT. *(Off-path Presidio NER deep-scan, task 9, remains optional/env-gated — P3_SPEC §6.1.)*

## P4 — Governed agentic actions (complete · 2026-06-21)

**One-liner:** Turned answers into **governed actions** — a LangGraph planner-executor agent that retrieves
through the P3 Gateway, deterministically decides the reporting-threshold breach, **pauses for mandatory human
approval**, and only then opens a draft SAR through a Spring-AI **MCP tool server** secured as an **OAuth 2.1
resource server**, with an **append-only, hash-chained audit log** and a **merge-blocking agent eval gate** —
no LLM on the safety path, so the whole flow is deterministic and GPU-free.

**Resume bullets (draft):**
- Built a **governed MCP tool server** (Java/**Spring AI 1.1**, **Streamable HTTP**, MCP spec `2025-11-25`)
  exposing one least-privilege write tool (`open_draft_sar`) with **structured output** — secured as an
  **OAuth 2.1 resource server** validating **RFC 8707 audience-restricted** JWTs (sig+exp+iss+aud) and a
  **per-call clearance re-check** (OWASP **LLM06/ASI03**) that refuses sub-`compliance` callers independently
  of upstream RBAC.
- Engineered an **append-only, tamper-evident audit log** (Postgres): every tool invocation writes an immutable
  **SHA-256 hash-chained** row, enforced by **two independent guards** — a least-privilege role (INSERT/SELECT
  only) **and** an owner-proof `BEFORE UPDATE/DELETE` trigger — with a chain verifier that **detects** post-hoc
  tampering (proven by an IT that disables the guard, mutates a row, and is caught).
- Wrote the governed write as a **single transaction** (draft-SAR row + `SUCCESS` audit row, all-or-nothing) —
  hard-tested for **0 orphan drafts** on a forced mid-transaction failure.
- Built the agent (Python/**LangGraph**) as an **explicit planner-executor state graph** with a
  **durable Postgres checkpointer**: a run **survives process restart** mid-decision and resumes from the
  persisted checkpoint (proven by a fresh-instance resume IT).
- Made human-in-the-loop a **graph-structural** safety invariant: the governed-write node is reachable **only**
  through a LangGraph **`interrupt()` approval gate**, and the approval is **single-use / replay-protected**
  (OWASP **ASI07**) — a consumed approval cannot authorize a second or mutated write.
- Made the safety-critical path **fully deterministic** (no LLM): the breach decision + routing are a pure
  function of retrieved citations, so a **prompt-injected source document cannot steer the agent into skipping
  the gate or filing a SAR** (OWASP **ASI01**) — and the agent eval runs offline with no GPU.
- Added **mid-task field confirmation** (a second durable graph interrupt): on an ambiguous, non-machine-
  readable breach the agent **asks a human to clarify** rather than guess — and a clarified breach still passes
  the write-approval gate. Proved the agent **inherits P1/P3 guarantees by construction** (offline gate: it
  calls only the governed `/v1/query` with the caller's Bearer and no clearance header) plus a live end-to-end
  gate (0 cross-clearance citations / 0 PII / injection-quarantined *through the agent path*).
- Shipped a **merge-blocking, trajectory-first agent eval** (12 versioned scenarios — forcing story,
  wrong-clearance, injection-in-source, rejection, tool-deny, …) scoring task-success, tool-selection,
  argument-correctness, step-efficiency, and plan-adherence **plus** the binary **HITL-respected** and
  **authorization-respected** hard gates; **12/12 pass, 0 unapproved / 0 unauthorized writes**.
- Extended the sim-IdP to mint **RFC 8707 resource-scoped, single-use** tokens for the agent→tool hop, and
  traced agent runs as **OTel spans** (root `agent.run` → node spans, opt-in export to Langfuse) with a
  **Grafana agent panel** (run rate, tool-call rate, approval latency, failures).
- Bumped the repo to **Spring AI 1.1.8 / Spring Boot 3.5** (for the MCP server stack) **without** a Boot-4
  migration, re-greening all frozen P1/P3 unit/IT + eval gates.

**Evidence:** full suite green — **mcp-tools 12 unit + 21 IT** (OAuth 2.1 resource server: missing/expired/
forged/wrong-aud → 401; per-call DENY → no write; append-only denied for app role *and* owner; tamper detected;
transactional rollback; MCP `tools/list`+`tools/call` round-trip), **agents 60 tests** (+3 live-gated agent-path
invariant checks) covering graph structure, HITL approve/reject/single-use, ambiguous→clarify, act-retry
(no duplicate write), resume-after-restart, MCP client, E2E forcing story, observability; **agent eval
12/12 (all rates 1.0)**; and the frozen **rag-engine 90 unit + 40 IT** + **gateway 66 unit + 14 IT** + both
RAG eval gates still green after the Spring AI bump. ADR-0041–0050 (+0024/0030 notes).

**Quantified:** 10 ADRs (0041–0050) · 1 governed write tool · **3 independent authorization checks**
(Gateway RBAC · P1 retrieval filter · MCP per-call re-check) · **2 append-only guards** (grant + trigger) ·
SHA-256 hash chain · **0 unapproved writes / 0 unauthorized writes / 0 orphan drafts** · single-use
replay-protected approval · durable resume-after-restart · 12-scenario merge gate · OWASP Agentic
**ASI01/02/03/06/07/09/10** mapped · MCP `2025-11-25` / Streamable HTTP / RFC 8707 · deterministic (GPU-free).

## P5 — React UI, containerization & production deploy (complete · 2026-06-27)

**One-liner:** Shipped the **clickable product** — a permission-aware React chat + read-only admin UI that
makes the whole forcing story visible (cited streamed answer → human-approved draft SAR → execution trace →
audit row), hardened at the render boundary (OWASP **LLM05** sanitizer **+** strict proxy CSP) and behind a
single-origin **Caddy TLS reverse proxy**, packaged as a **multi-arch (arm64) image** with one-command deploy
automation and a green **local-TLS smoke** — all P1/P3/P4 contracts **frozen**, the UI a pure consumer.

**Resume bullets (draft):**
- Built a production **React 19 + TypeScript (Vite, Tailwind v4)** SPA over the **frozen** Java/Python HTTP
  contracts — sim-IdP login, streamed cited answers, the agent **human-in-the-loop approval** surface, an
  execution-trace view, and a read-only admin area — as a thin **presentation client** with **no secrets, no
  authorization logic, and no model calls in the browser** (clearance always re-enforced server-side).
- Hardened model output as **untrusted interpreter input (OWASP LLM05)** with **defense-in-depth**: a
  client-side **DOMPurify allowlist** (markdown→safe HTML; `javascript:`/`data:`/event-handlers stripped,
  links forced `rel=noopener`) **plus** a strict **Caddy Content-Security-Policy** (`script-src`/`style-src
  'self'`, **no `unsafe-inline`**, `object-src 'none'`, `frame-ancestors 'self'`) — proving an XSS-laden
  answer/citation renders **inert** in both a jsdom unit gate and a live-browser Playwright check.
- Added a single-origin **Caddy reverse proxy** (D-P5-2) that serves the static UI and path-routes
  `/v1/*`→Gateway, `/v1/agent/*`→Agents, `/v1/audit`→mcp-tools under **one TLS origin** — killing CORS,
  hiding backend topology, and emitting `X-Content-Type-Options`/`Referrer-Policy`/`HSTS`/`X-Frame-Options`.
- Surfaced the **human-in-the-loop** safety story in the UI without weakening it: the Approve/Reject control
  only **forwards the human decision** to the agent's `resume` endpoint — the UI **never constructs a write** —
  proven by a "never-fabricate-write" test (reject → no `draftRef`, and the UI makes **no** tool/MCP call).
- Extended `mcp-tools` with a **read-only, compliance-gated** `GET /v1/audit` (the first HTTP controller in the
  module): paginated, **SELECT-only** (no new write path), backed by the OAuth 2.1 resource server (refuses
  `< compliance` → 403) and a **global hash-chain-verified** flag, surfacing **digests/refs, not raw PII**
  (LLM02) — 6 Testcontainers ITs.
- Containerized the UI as a **multi-stage, multi-arch (amd64 + arm64) image** (Node build → Caddy serving the
  bundle + Caddyfile, digest-pinned bases) and **verified the arm64 build under QEMU** for the Oracle Ampere A1
  target; a prod compose overlay flips to in-compose upstreams + `restart: always` + real domain/ACME TLS.
- Wrote **one-command deploy automation + a local-TLS smoke test** that asserts the proxy serves the UI over
  TLS with the full CSP/security headers, SPA fallback, and **no secret in the served bundle** — green
  (GPU-free) — with the **live Oracle Ampere A1 (arm64) deploy** documented as a dry-run runbook (DNS, ACME,
  GPU via `OLLAMA_BASE_URL`) plus Hetzner & Cloudflare-Tunnel fallbacks.
- Added **EU AI Act / NIST AI RMF transparency** as a design constraint: a session-start AI-system disclosure,
  per-message **AI-generated** labels, and an **"AI-assisted draft — requires human review"** stamp on the SAR.
- Made the UI **non-regressably tested**: **41 Vitest/RTL** unit/component tests + a **5-spec Playwright E2E**
  acceptance gate (the forcing story, negative-access UX, the live LLM05-inert check, and an **axe-core a11y**
  smoke), run **deterministically** via network mocking (no live-model variance), wired into CI.

**Evidence:** `ui` green — **41 Vitest** (auth/sanitize/answer/citation/chat/agent/admin) + **5 Playwright**
(forcing-story, negative-access, LLM05-inert, a11y chat+admin) + lint/typecheck/format/build + a no-secret
bundle scan; **mcp-tools** `mvn verify` green incl. **`AuditControllerIT` 6/6** (401/403/200, pagination,
filters, no-PII, SELECT-only) with the frozen P4 ITs still green; **inherited eval gates** (RAG RAGAS +
eval-through-Gateway + agent 12/12) still **PASS**; `caddy validate` + `docker compose config` clean; the
**arm64** multi-arch image builds under QEMU; `make -C infra deploy-smoke` → **PASS** over local TLS.
ADR-0051–0059.

**Quantified:** 9 ADRs (0051–0059) · **41 unit + 5 E2E** UI tests · **6** audit-endpoint ITs · **2** independent
LLM05 walls (DOMPurify sanitizer + proxy CSP) · single-origin proxy (3 path routes, **0 CORS**) · **multi-arch
amd64+arm64** image (arm64 build verified) · read-only admin (**0** mutable actions) · in-memory token (no
`localStorage`) · **0 secrets** in the served bundle (CI-asserted) · all **P1/P3/P4 contracts frozen** (no
regression) · OWASP **LLM02/LLM05/LLM06/LLM09** + **EU AI Act transparency** surfaced.

**30-second demo:** login as **Priya** → toggle **Investigate as governed action** (Northwind / 2026-Q2) → ask
→ see the **cited, AI-generated answer** + the proposed **draft SAR** → **Approve** (the human-in-the-loop
checkpoint) → see the **`SAR-2026-…` ref + execution trace** → **Admin ▸ Audit** shows the new **SUCCESS** row
(chain verified) and **Admin ▸ Cost** the cost-reduction panel. GPU-free walkthrough: `cd ui && npm run e2e`.
**Demo recording:** _TODO — link a screen capture of the click path above (run `make -C infra deploy-up` then
the steps, or `npm run e2e:ui`)._

---

## P6 — Production hardening & operability (complete · 2026-06-27)

- **Authored the operator runbook for production** — an **in-prod architecture diagram** (Mermaid topology of
  the single arm64 VM: Caddy → 5 services → Postgres+pgvector/Redis → Langfuse/Prometheus/Grafana, with the
  GPU and the disabled frontier tier as the only off-box deps), a **consolidated env-var & secrets reference**
  (≈40 variables grouped by subsystem, each flagged secret/public with source + rotation policy), and a
  **cost-ceiling + cloud-frontier budget-fallback procedure** that turns a one-line note into an operational
  control with a documented eyes-open enable path.
- **Set and documented a hard ≈$10/month cost ceiling** for the only paid dependencies (rented GPU + frontier
  API), enforced by GPU pause discipline + the gateway daily budget guard + (P6) a Prometheus cost alert — and
  made the **cloud-frontier tier ship disabled by default** so overspend is opt-in, preserving honest
  fail-fast `503` degradation over silent expensive model substitution.

**Evidence (Task 1):** `docs/RUNBOOK.md` §9.0 (in-prod Mermaid topology + trust boundaries), §10 (env/secrets
table + secrets-management model), §11 (cost ceiling, frontier-off rationale, enable path); ADR-0060 in
`docs/DECISIONS.md`. Env names cross-checked against `.env.example` (no invented vars).

**Quantified (Task 1):** 1 ADR (0060) · 3 new RUNBOOK sections · 1 architecture diagram · **~40** env vars
documented with secret/public classification · **$10/mo** hard ceiling wired to budget guard + alert · frontier
fallback **off-by-default** (0 billable keys in repo).

- **Hardened every container for an unattended single box.** Rewrote the `agents` image to a **true multi-stage,
  non-root (uid 10001), digest-pinned** build (was the lone single-stage/root/tag-pinned outlier); added a
  **Dockerfile `HEALTHCHECK` to all 5 services** — solving the distroless "no shell/curl" constraint with a
  ~30-line **JRE health probe compiled to architecture-independent bytecode** in a `$BUILDPLATFORM` stage (real
  HTTP health *without* abandoning distroless or reintroducing QEMU), and a host-agnostic Caddy `:9180/healthz`
  for the UI. Hardened the **prod compose overlay** with memory limits, **json-file log rotation (10m×5)**, and
  **health-gated `depends_on` ordering**, and added the previously-missing **`rag-engine` service** to compose.

**Evidence (Task 2):** `agents` image **built and run as uid 10001** with `uvicorn` on the venv path +
`app.api` import OK; BuildKit `docker build --check` clean on the rewritten Dockerfiles; the `healthprobe`
stage builds and `javac` compiles against the **real `.dockerignore`** (re-include verified); merged
`docker compose -f … -f docker-compose.prod.yml config` valid with limits, log rotation, and `service_healthy`
ordering. ADR-0061.

**Quantified (Task 2):** **5/5** services with a container HEALTHCHECK · agents image **root → non-root** +
single-stage → **multi-stage** + tag → **digest-pinned** · **1** portable probe class reused across 3 distroless
images (0 extra runtime tools, 0 QEMU) · prod overlay: **5** services with mem limits + **log rotation** +
**health-ordered** startup · **1** missing service (`rag-engine`) added to compose.

- **Closed the biggest cross-cutting prod gap: observability-grade logging.** Added **structured JSON logging
  to all four services** — native Spring Boot 3.5 ECS (no logstash dependency) for the three Java services and
  a stdlib JSON logger for the Python agents service (which previously had **zero** application logging) —
  env-toggled so dev stays human-readable. Threaded a single **`X-Request-Id` correlation id** through a Spring
  `RequestIdFilter` + a FastAPI middleware that mint/echo/validate the id and **propagate it downstream**
  (gateway→rag-engine, agents→gateway/MCP), with rag-engine reusing it as its trace id — so one request is now
  followable across every hop in both logs and traces. Hardened the id against **log-injection** (strict
  allow-list on the untrusted client header). Brought **gateway tracing** online (Micrometer→OTLP bridge) so
  Langfuse finally covers the front door, not just rag-engine/agents.

**Evidence (Task 3):** new `RequestIdFilterTest` ×3 (mint / reuse-propagated / anti-injection) green;
**gateway 69 · rag-engine 93 · mcp-tools 15** unit tests pass incl. full Spring context-load with the new
tracing deps + logging config; booting with `ATLAS_LOG_FORMAT=ecs` emits valid **ECS JSON**; agents **65
passed / 3 skipped** + **5** new logging/correlation tests (formatter, middleware echo, downstream forward),
ruff clean; merged `docker compose config` applies `ecs`/`json` per service. Frontier kept **off**
(`ATLAS_ROUTER_FRONTIER_ENABLED=false`) per owner decision. ADR-0062.

**Quantified (Task 3):** **4/4** services now emit structured JSON logs (was **0/4**; agents went from
**no logging at all**) · **1** correlation id propagated across **4** hops · **3** Spring `RequestIdFilter`s +
**1** FastAPI middleware · **+8** tests (3 Java + 5 Python) · **0** new Java logging dependencies (native ECS) ·
gateway tracing **on** (export opt-in) · **0** log-injection vectors (allow-list validated).

- **Wired end-to-end alerting on the cost + reliability + quality signals.** Added **5 Prometheus alert rules**
  — a **cost tripwire** tied to the $10/mo ceiling (24h cost-units >80% of the daily cap), gateway **5xx
  error-rate >5%**, **circuit-breaker-open**, **service-down**, and **eval-gate-failing** — routed through a
  new **Alertmanager** (digest-pinned, config seeded Snap-Docker-safe into a named volume, with routing +
  inhibition and documented Slack/email stubs). Added a **p50** latency series next to the existing p95 on the
  cost dashboard. Everything is declarative and lint-checked.

**Evidence (Task 4):** `promtool check rules` → **5 rules** OK; `promtool check config` → valid (1 rule file);
`amtool check-config` → valid (route + 1 inhibit + 1 receiver); cost dashboard JSON parses (11 panels) with
the p50/p95 panel; base `docker compose config` shows the `alertmanager` service + `atlas-alertmanager-config`
/`-data` volumes. ADR-0063.

**Quantified (Task 4):** **5** alert rules across **3** domains (cost / reliability / quality) · **1**
Alertmanager (routing + inhibit + critical fast-path) · cost alert fires at **80%** of the $10/mo cap ·
latency panel now **p50 + p95** · **0** lint errors (promtool + amtool) · **0** paid dependencies.

- **Closed the CI gate loop: block deploy on cost regression, not just hallucination.** Added a
  **cost-regression gate** (`atlas_evals.cost_gate`) that validates the committed gateway cost evidence still
  meets its reduction target, wired into the CI eval-gate job — so a merge is blocked on **quality OR cost**.
  Flipped **Trivy** from report-only to **gating on fixable CRITICAL/HIGH** (with an auditable, dated `.trivyignore.yaml` (incl. a justified MCP-SDK CVE exception)).
  Added a **manual gated deploy workflow** (`deploy.yml`): a `gate` job (RAGAS + gateway-path + agent + cost)
  that the `deploy` job `needs`, pulling SHA-pinned multi-arch GHCR images via `compose pull/up` + `smoke.sh`,
  with a one-input **rollback** (re-run with a previous SHA) — a documented dry-run until the box exists.

**Evidence (Task 5):** `cost_gate` unit tests (**7** — below-target / absolute-ceiling / missing-field / the
real committed baseline passing) + **evals suite 70 passed**; `atlas_evals.gate` **PASS** & `cost_gate`
**PASS** offline; `ci.yml` (8 jobs) + `deploy.yml` (gate→deploy) parse; rollback path documented (RUNBOOK
§9.3). ADR-0064.

**Quantified (Task 5):** CI now blocks on **quality + cost** (was quality only) · Trivy **report-only →
blocking** on CRITICAL/HIGH · **+1** gated deploy pipeline (deploy `needs` the gate) · **+7** cost-gate tests ·
rollback = **1** workflow input (previous SHA) · **0** GPU needed (gate stays offline).

- **Shipped the 3-minute demo as a passing test.** Wrote `docs/DEMO.md` — the exact timed click-through (Priya
  login → RBAC cited answer → execution trace → HITL approve `open_draft_sar` → audit SUCCESS → **Cost** panel
  → **Evals** gate) — and its automated form `ui/e2e-demo/forcing-story.demo.spec.ts` (a dedicated Playwright
  config + `npm run e2e:demo`), the first walkthrough to assert the **cost dashboard + eval/trace view**
  together. Added `infra/deploy/seed-demo.sh` to load the deterministic RBAC corpus + list the four demo users.
  Closed the P5 gap where `ui/e2e-demo/` was empty and no single demo covered cost + evals.

**Evidence (Task 6):** `npm run e2e:demo` → **1 passed** against the production `vite preview` build (cited
answer, trace steps, HITL approve, `SAR-2026-000123` audit SUCCESS chain-verified, **100%** cost-reduction
panel, **2** green gate badges); UI lint (0 errors) / typecheck / prettier clean; `seed-demo.sh` `bash -n` OK.
ADR-0065.

**Quantified (Task 6):** **1** automated 3-min demo asserting **4** capabilities (RBAC RAG · agent+MCP · cost
· eval/trace) · **9** asserted steps · **<3 min** target with per-step timings · **1** deterministic seed
script (24-doc RBAC corpus + 4 users) · **0** GPU needed for the automated run (the live fallback).

- **Finalized the top-level README as the front door.** A **hero Mermaid architecture diagram** (request flow
  + the cross-cutting evals/observability plane), a **live-demo link** (the on-demand Oracle A1 target, with
  the GPU-free `npm run e2e:demo` as the reliable proof), a curated **"Technical decisions"** digest (8 themed
  call-outs linking the key ADRs across RAG / cost / agents / evals / ops), and a **fresh-clone setup that
  actually works** — replacing the stale P0-era commented Quickstart with a verified offline path (eval +
  cost gate + UI demo, no GPU) and the live-stack path.

**Evidence (Task 7):** README Mermaid balanced (2 subgraphs / 2 ends); all 7 doc links + LICENSE resolve;
the offline setup commands are the same ones verified green this phase (`atlas_evals.gate`,
`atlas_evals.cost_gate`, `npm run e2e:demo`); status/phase/ADR-count (65) updated from the stale P0 copy.

**Quantified (Task 7):** **1** hero architecture diagram (was a markdown table) · **8** curated technical-
decision call-outs · fresh-clone setup **P0-commented → working** · live-demo link added · **65** ADRs
referenced · README **~3 KB → ~9 KB** of accurate, current content.

**P6 net:** **6** ADRs (0060–0065) · **+15** tests (3 Java filter + 5 Python logging + 7 cost-gate) all green
on top of the inherited gates · **5/5** containers hardened (health/non-root/limits) · **4/4** services with
structured JSON logs + correlation · **5** Prometheus alerts + Alertmanager · CI blocks on **quality + cost** ·
**1** gated, rollback-able deploy pipeline · **1** automated 3-min demo · a finalized README.

**Pre-merge verification (local):** full `mvn -B verify` **BUILD SUCCESS** across all modules incl. the
Testcontainers ITs (gateway 69 unit + 14 IT · rag-engine · mcp-tools 15 unit + 27 IT) — confirming the P6
logging/tracing/correlation changes don't regress the integration suite; **Trivy** (now-blocking settings)
**exit 0** after adding explicit `USER 65532` to the three distroless Java images and a **dated, justified
`.trivyignore.yaml`** for the Caddy edge-proxy `USER` misconfig + the transitive MCP-SDK DNS-rebinding CVE
(not exploitable: `/mcp` is never browser-routed — agent-only, OAuth2.1 aud-scoped). The only item that
**cannot** be completed off-box remains the live Oracle A1 deploy (a documented dry-run, RUNBOOK §9.4).
