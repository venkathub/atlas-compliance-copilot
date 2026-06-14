# Atlas — Portfolio Highlights

Resume-ready, quantified outcomes per phase. Atlas is a permission-aware, cost-routed, evaluated enterprise
AI copilot for a financial/compliance domain (**Spring AI + LangGraph + MCP**).
Repo: <https://github.com/venkathub/atlas-compliance-copilot>

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
## P3 — Cost-aware gateway (pending)
## P4 — Agent orchestrator + MCP (pending)
## P5 — UI + production deploy (pending)
_Each populated as the phase lands, per the CLAUDE.md Definition of Done._
