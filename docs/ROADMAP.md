# Atlas — Engineering Roadmap

> Status: **DRAFT — awaiting approval.** No application code is written until this roadmap is approved.
> Companion docs: `CLAUDE.md` (operating agreement), `docs/DECISIONS.md`, `docs/RUNBOOK.md`, `docs/PORTFOLIO.md`.

---

## 0. Decisions locked from review

These were resolved with the project owner and supersede the open questions at the bottom:

1. **Dataset (two-layer corpus + fixtures).** No single off-the-shelf set serves both the RAG story *and*
   the AML/SAR action, so Atlas uses a deliberate **two-layer corpus** plus small authored **fixture sets**:
   - **Layer 1 — RAG document substrate:** a **Hugging Face** finance corpus — SEC 10-K/EDGAR filings and/or
     `PatronusAI/financebench`. Proves chunking / embeddings / hybrid search / citations. FinanceBench's 150
     annotated `(question, answer, evidence, doc)` tuples double as a **ready-made golden eval set** for P2.
     *License note:* FinanceBench is **CC-BY-NC-4.0** (non-commercial) — fine for this portfolio; pull raw
     **EDGAR** (public domain) if a commercial-clean corpus is ever needed.
   - **Layer 2 — compliance/AML demo layer (synthetic, authored by us):** ~10–20 narrative docs — account
     memos, AML exception summaries, an AML policy, a SAR template — each tagged `public` / `analyst` /
     `compliance` / `restricted`. This is what Priya's story, the negative-access tests, and the draft-SAR
     action operate on (the "Northwind account" lives here). No public finance corpus ships RBAC labels, so
     this overlay is necessarily synthetic.
   - **Fixture sets (not a corpus, but core data artifacts):** identity fixtures (users→clearance, P3),
     negative-access golden cases (P1), an adversarial/red-team set (prompt-injection, jailbreak,
     access-bypass, system-prompt-leakage, P2), poisoned-document fixtures (P1), and PII-bearing samples
     baked into Layer 2 (P3 redaction). Full inventory in `DECISIONS.md` ADR-0004.

   Exact corpus subset finalized at P1 start. **AML *transaction* CSVs (e.g. IBM AMLSim/SAML-D,
   `VynFi/vynfi-aml-100k`) are deliberately excluded** — they are detector training data, off-thesis for a
   retrieval-with-citations system.
2. **Auth** — A **simulated identity/clearance provider** is sufficient (no real OIDC IdP). It must still
   produce a verifiable clearance claim the RAG Engine and MCP tools enforce.
3. **Deployment (low INR budget)** —
   - **Prod app stack** (all CPU services): **Oracle Cloud Always Free — Ampere A1 ARM, 4 vCPU / 24 GB RAM, ₹0/mo.**
     Fallback: **Hetzner Cloud** (~₹350–700/mo) if free ARM capacity is unavailable.
     → Implication: build **multi-arch Docker images** (anticipated in P0, not deferred to P5).
   - **Cloud Ollama GPU** (LLM endpoint): **JarvisLabs.ai** (~₹41/hr, **per-minute billing, pause/resume with
     persistent storage**, INR/UPI), **paused when idle**; **E2E Networks** (Indian, INR) as fallback. A modest
     GPU (L4 / A5000 class) suffices for the small dev model. `OLLAMA_BASE_URL` makes the endpoint swappable so
     the app stack is indifferent to which GPU is live.
4. **Cadence** — ~**8–12 focused hrs/week** part-time (calendar estimates in §5 assume this).

---

## 1. Product vision & the forcing user story

**Vision.** Atlas is a production-grade enterprise AI operations copilot for a financial/compliance
domain. An employee asks a question in natural language; Atlas retrieves **only** the documents that
employee is cleared to see, answers **with citations**, and — on explicit request — **executes governed
actions** through agents behind a human-in-the-loop checkpoint. Every model call is **cost-routed,
evaluated, and traced**. The deliverable is not a notebook demo but a deployed, clickable system that
proves the discipline of taking AI from prototype to reliable production: permission-aware RAG, agentic
tool use over MCP, automated evals as a CI gate, cost-aware infrastructure, and full observability.

**The single end-to-end user story that forces every subsystem.**

> *Priya, a compliance analyst with `role=compliance` clearance, logs into Atlas and asks:
> "Summarize the open AML exceptions for the Northwind account this quarter, and if any breach the
> reporting threshold, open a draft Suspicious Activity Report for my review."*
>
> Atlas must:
> 1. **Authenticate** Priya and resolve her clearance — *(UI + Gateway auth, simulated IdP)*.
> 2. **Route** the request to a cost-appropriate model and cache/rate-limit it — *(Gateway: cost-aware router)*.
> 3. **Retrieve only documents Priya is cleared to see**, ranked and reranked — *(RAG Engine + pgvector RBAC filtering)*.
> 4. **Answer with inline citations** and resist prompt-injection in the source docs — *(RAG Engine guardrails)*.
> 5. **Plan and execute the conditional action** ("if breach → open draft SAR") as a multi-step agent — *(Agent Orchestrator / LangGraph)*.
> 6. **Call a governed enterprise tool** to create the draft SAR, **pausing for Priya's approval** before any write — *(MCP Tool Server + human-in-the-loop)*.
> 7. **Show citations and the execution trace** back in the UI — *(UI)*.
> 8. Have **every retrieval and model call scored and traced**, with the whole interaction visible on a dashboard — *(Evals & Observability, cross-cutting)*.

No subsystem is optional: drop any one and this story breaks. That is the design intent — the story is
the integration test for the entire portfolio.

---

## 2. Phase plan (P0 → P5, dependency order)

Each phase obeys the **CLAUDE.md Definition of Done** (tests + evals in CI, README + DECISIONS updated,
clean-from-scratch run, 30-second demo path, resume bullet). The per-phase **Exit Criteria** below are
the *phase-specific* additions on top of that baseline.

### P0 — Foundations: repo, infra, env, CI skeleton, model connectivity
- **Goal.** A reproducible skeleton anyone can clone and run, with a proven, swappable connection to the
  remote Ollama GPU endpoint. Prove the plumbing before any intelligence.
- **Subsystems touched.** `/infra` (Docker Compose, CI), env config across all modules, a thin
  connectivity probe (no real Gateway logic yet).
- **Key skills demonstrated.** Polyglot monorepo hygiene, 12-factor env config, containerized local
  dev on a low-spec laptop, **multi-arch image builds** (for ARM prod), CI pipeline design,
  OpenAI-compatible LLM integration against remote Ollama.
- **Entry criteria.** Empty repo; this roadmap approved; `OLLAMA_BASE_URL` available.
- **Exit criteria (DoD).**
  - [ ] Monorepo layout per CLAUDE.md conventions; `.env.example` with every required var, **no secrets in code**.
  - [ ] `docker compose up` brings up Postgres+pgvector and Redis locally; healthchecks pass.
  - [ ] Image builds are **multi-arch (amd64 + arm64)** so they run on the Oracle Ampere A1 prod target.
  - [ ] CI skeleton (GitHub Actions) runs lint + build + a placeholder test on every PR; branch protection on `main`.
  - [ ] **Supply-chain security (OWASP LLM03):** CI runs dependency + secret scanning; container images and model tags are pinned by digest; an SBOM/AIBOM is generated.
  - [ ] **Smoke test**: an automated check that calls the cloud Ollama endpoint via env config and asserts a completion + an embedding come back; model is swappable by env, never hardcoded.
  - [ ] `docs/RUNBOOK.md` started (incl. "how to pause/resume the JarvisLabs GPU"); `docs/DECISIONS.md` records stack/baseline-model/deploy-target choices.

### P1 — Permission-aware RAG engine + pgvector store
- **Goal.** Given a user + clearance, retrieve only authorized documents and answer with citations.
  This is the system's core and its hardest correctness/safety problem.
- **Subsystems touched.** RAG Engine (Spring AI), Vector Store (pgvector with role-tagged metadata).
- **Key skills demonstrated.** Chunking strategy, embedding selection, hybrid (vector + keyword) search,
  reranking, **RBAC filtering at retrieval time**, citation/source attribution, prompt-injection guardrails.
- **Entry criteria.** P0 exit met (DB up, model reachable, CI green).
- **Exit criteria (DoD).**
  - [ ] Dataset finalized: HF financial corpus + synthetic clearance overlay ingested.
  - [ ] Ingestion pipeline: chunk → embed → store with `role`/clearance metadata in pgvector.
  - [ ] **Ingestion integrity (OWASP LLM04):** documents validated + source-provenance recorded at ingest; only trusted corpus admitted, guarding against data/embedding poisoning.
  - [ ] Retrieval enforces RBAC: a user can **never** receive a chunk above their clearance (proven by a negative-access test set).
  - [ ] Hybrid search (pgvector **HNSW** dense + Postgres full-text/`tsvector` sparse) + reranking returns grounded context; answers carry inline citations to source chunks.
  - [ ] Stack pinned: **pgvector ≥ 0.7 on PostgreSQL ≥ 16**; retrieval implemented via **Spring AI Advisors** (`RetrievalAugmentationAdvisor` / `QuestionAnswerAdvisor`); index choice (HNSW vs IVFFlat) logged in `docs/DECISIONS.md`.
  - [ ] Prompt-injection guardrail tests pass against a poisoned-document fixture.
  - [ ] All model config swappable by env; decisions (dataset, chunk size, embedding model, hybrid weights) logged in `docs/DECISIONS.md`.
  - *Note:* formal eval thresholds are gated in P2 — P1 ships a manual quality baseline that P2 automates.

### P2 — Evaluation & observability harness (CI-gated)
- **Goal.** Make quality measurable and non-regressable **before** building agents. Per CLAUDE.md: *evals before agents.*
- **Subsystems touched.** `/evals` (Python: RAGAS/DeepEval), Langfuse tracing wired into the RAG Engine, Grafana/Prometheus dashboards.
- **Key skills demonstrated.** RAG evaluation (faithfulness, answer relevancy, context precision/recall),
  golden datasets, LLM-as-judge, **adversarial/red-team safety evals** (prompt-injection, jailbreak,
  access-bypass), Spring AI **in-pipeline evaluators** (`RelevancyEvaluator` / `FactCheckingEvaluator`),
  distributed tracing, turning evals into a **merge gate**.
- **Entry criteria.** P1 exit met (a working RAG path to evaluate and trace).
- **Exit criteria (DoD).**
  - [ ] Golden eval dataset (questions + ground truth + expected sources, incl. negative-access cases) committed and versioned.
  - [ ] RAGAS/DeepEval metrics computed in CI; **defined thresholds block merge** on regression.
  - [ ] **Adversarial/red-team eval set** (prompt-injection, jailbreak, access-bypass, **system-prompt-leakage — OWASP LLM07**) runs in CI; failures block merge.
  - [ ] Langfuse-managed eval **datasets** drive regression runs; Spring AI `RelevancyEvaluator`/`FactCheckingEvaluator` run inline as a cheap pre-filter.
  - [ ] Every retrieval + model call traced in Langfuse using **OpenTelemetry GenAI semantic conventions** (`gen_ai.*` spans/metrics); traces link to the originating request.
  - [ ] Grafana dashboard shows eval scores, latency, and trace volume over time.
  - [ ] P1's manual baseline is now an automated, recorded threshold; bullet in `docs/PORTFOLIO.md` quantifies it.

### P3 — Cost-aware gateway, model router & dashboards
- **Goal.** A single front door that authenticates, routes each request to the cheapest adequate model,
  caches, rate-limits, and makes the **cost story visible**. Cost discipline as a first-class feature.
- **Subsystems touched.** API Gateway (Spring Boot + Micrometer), Redis cache, Prometheus/Grafana, simulated IdP.
- **Key skills demonstrated.** Auth, model routing on cost/latency/quality thresholds, **semantic caching**,
  rate limiting, **PII detection/egress redaction**, **budget spend-caps**, circuit breakers,
  token/cost/latency metering and dashboards.
- **Entry criteria.** P2 exit met (so routing decisions can be evaluated, not guessed).
- **Exit criteria (DoD).**
  - [ ] Gateway fronts the RAG Engine: simulated-IdP auth, routing, caching, rate limiting all functional.
  - [ ] Caching is **semantic** (embedding-similarity), not just exact-match response cache.
  - [ ] **PII detection + egress redaction** on prompts/responses (compliance-critical), with redaction events traced.
  - [ ] **Output handling (OWASP LLM05):** model output is sanitized/encoded at egress (no executable/unsafe content passes through) before reaching downstream consumers.
  - [ ] Per-user/route **budget spend-caps** + **circuit breaker** on model failure/timeout.
  - [ ] Router selects small/quantized models by default, escalates only by policy; routing rules in `docs/DECISIONS.md`.
  - [ ] Micrometer → Prometheus → Grafana dashboard exposes **tokens, cost, latency per route/model/user**.
  - [ ] Cache + rate-limit behavior covered by integration tests; eval thresholds (from P2) still pass through the Gateway path.
  - [ ] Demonstrated cost delta (e.g., "X% cheaper at equal eval score") captured for the portfolio.

### P4 — Agent orchestrator (LangGraph) + MCP tool servers
- **Goal.** Turn answers into **governed actions**: plan, call enterprise tools over MCP, and require
  human approval before any state-changing operation.
- **Subsystems touched.** Agent Orchestrator (Python/LangGraph), MCP Tool Servers (Spring Boot),
  consuming Gateway + RAG + Evals from prior phases.
- **Key skills demonstrated.** Planner–executor agents, **durable agent memory (Postgres checkpointer)**,
  **human-in-the-loop checkpoints**, MCP tool design over **Streamable HTTP** secured as an **OAuth 2.1
  resource server**, **MCP elicitation** for mid-task human input, governed/audited actions, agent-level evaluation.
- **Entry criteria.** P3 exit met (cost-aware, observable RAG behind a gateway to build agents on).
- **Exit criteria (DoD).**
  - [ ] LangGraph planner–executor completes the user story's conditional action end-to-end.
  - [ ] At least one MCP tool server exposes a governed write action (draft SAR) over **Streamable HTTP**, secured as an **OAuth 2.1 resource server** (RFC 8707 resource indicators), with audit logging.
  - [ ] **No state change occurs without an explicit human-in-the-loop approval step** (implemented via MCP **elicitation** / LangGraph `interrupt` → `Command(resume)`).
  - [ ] Agent state is **durably checkpointed in Postgres** (reuses the P0 DB), enabling resume after interrupt/restart.
  - [ ] Tools re-check the caller's clearance before acting (defense-in-depth with P1 RBAC).
  - [ ] Tool-call **audit log is append-only/immutable** and queryable for compliance review.
  - [ ] Agent runs are traced (Langfuse) and evaluated (task success / tool-call correctness) as a CI gate.
  - [ ] Tool contracts + safety boundaries documented; decisions logged.

### P5 — React UI, containerization & production deployment
- **Goal.** Ship the clickable product: chat + admin, visible citations and traces, deployed.
- **Subsystems touched.** React UI, full containerization of all services, production deploy to
  **Oracle Cloud Always Free (Ampere A1 ARM)**, with the cloud-frontier budget reserved for the final multimodal demo.
- **Key skills demonstrated.** Streaming chat UX, citation/trace surfacing, admin views, multi-service
  ARM containerization, production deployment, end-to-end demo polish.
- **Entry criteria.** P4 exit met (a complete backend behind the Gateway).
- **Exit criteria (DoD).**
  - [ ] React chat UI renders streamed answers, inline citations, and the agent execution trace.
  - [ ] **Safe rendering (OWASP LLM05):** model/markdown output is sanitized before display (no XSS via citations/HTML); production secrets injected via env/secret store, never bundled.
  - [ ] Admin view shows eval scores, cost dashboards, and audit logs.
  - [ ] All services containerized (multi-arch); one documented command deploys the stack to the Oracle ARM box (Hetzner fallback documented).
  - [ ] The full forcing user story (Priya → cited answer → approved draft SAR) is demonstrable on the deployed system.
  - [ ] Final portfolio writeup + demo recording; `docs/PORTFOLIO.md` complete.

---

## 3. Risk register (top 5) & how phases de-risk

| # | Risk | Impact | Primary de-risk | Reinforced by |
|---|------|--------|-----------------|---------------|
| R1 | **Permission leakage** — a user receives a chunk above their clearance | Catastrophic in a compliance domain; kills credibility | **P1** builds RBAC filtering into retrieval with a negative-access test set as a hard gate | **P2** evals include access-control cases; **P4** tools re-check authorization before any action |
| R2 | **Hallucination / ungrounded answers** — confident but wrong, or uncited | Erodes trust; unusable for compliance | **P1** citation attribution + grounding; **P2** RAGAS faithfulness/context-recall thresholds **block merge** | **P3** routing never trades below the eval floor; **P4** agent decisions read from grounded context |
| R3 | **Cost/latency blowup** — naive model use makes the system uneconomic | Fails the "cost as a feature" thesis | **P3** cost-aware router + caching + per-route metering; small models by default | **P0** env-swappable models + stop-when-idle GPU; **P2** dashboards make cost/latency continuously visible |
| R4 | **Unsafe / unreliable agent actions** — wrong or unauthorized writes | Real-world damage; the scariest failure | **P4** mandatory human-in-the-loop before writes; MCP tools are governed + audited | **P2** harness extends to agent/tool-call evals as a gate; R1 authz re-check |
| R5 | **Infra / model-connectivity fragility** — remote Ollama or env config breaks reproducibility | Blocks all downstream work; "works on my machine" | **P0** connectivity smoke test + strict env config + multi-arch Docker Compose, all in CI | **P5** full ARM containerization + one-command deploy; RUNBOOK kept current every phase |

---

## 4. Skills proof map

Every in-demand AI-engineering skill is tied to the exact phase/subsystem where it is *demonstrated and
evidenced* (tests/evals/dashboards), so nothing is left as an unproven claim.

| In-demand skill | Where it's proven (phase · subsystem) | Evidence artifact |
|---|---|---|
| LLM integration (OpenAI-compatible, self-hosted) | P0 · Infra/connectivity | Smoke test hitting remote Ollama in CI |
| Env-driven, swappable model config | P0 · all modules | `.env.example`, no hardcoded models |
| Multi-arch containerization for ARM | P0 → P5 · Infra | amd64+arm64 images running on Oracle A1 |
| CI/CD for ML-adjacent systems | P0 → P5 · CI | GitHub Actions with eval gates |
| Supply-chain security (dep/secret scan, SBOM/AIBOM) | P0 · CI | Scan jobs + pinned digests |
| Document chunking & embedding strategy | P1 · RAG Engine | Ingestion pipeline + DECISIONS entry |
| Vector search (pgvector) | P1 · Vector Store | pgvector schema + queries |
| Hybrid search + reranking | P1 · RAG Engine | Retrieval tests + benchmark |
| **RBAC / permission-aware retrieval** | P1 · RAG + pgvector | Negative-access test suite |
| Citation / source attribution | P1 · RAG Engine | Cited answers in tests/UI |
| Prompt-injection guardrails | P1 · RAG Engine | Poisoned-doc fixture tests |
| RAG evaluation (RAGAS/DeepEval) | P2 · Evals | Golden dataset + CI thresholds |
| LLM-as-judge / eval gating | P2 · Evals | Merge-blocking eval job |
| Distributed tracing / observability | P2 · Langfuse + Grafana | Linked traces + dashboards |
| OTel GenAI semantic conventions | P2 · Observability | `gen_ai.*` spans/metrics |
| OWASP LLM Top 10 alignment (security map) | P0–P5 · cross-cutting | §7 control map + CI gates |
| Auth & API gateway design | P3 · Gateway | Auth + integration tests (simulated IdP) |
| **Cost-aware model routing** | P3 · Gateway router | Routing policy + cost delta report |
| Caching (semantic) & rate limiting | P3 · Gateway + Redis | Semantic-cache + rate-limit tests |
| PII detection & egress redaction | P3 · Gateway | Redaction tests + traced events |
| Adversarial / red-team safety evals | P2 · Evals | Prompt-injection/jailbreak CI gate |
| Metrics & cost dashboards (Micrometer) | P3 · Gateway | Token/cost/latency Grafana board |
| Agent orchestration (planner–executor) | P4 · Agents/LangGraph | End-to-end agent run |
| Agent memory & human-in-the-loop | P4 · Agents | Approval checkpoint in trace |
| **MCP tool server design (governed actions)** | P4 · MCP Tools | Audited write tool + contract |
| MCP transport/auth (Streamable HTTP, OAuth 2.1) | P4 · MCP Tools | Resource-server-secured tool |
| Durable agent state (Postgres checkpointer) | P4 · Agents | Resume-after-interrupt test |
| Agent evaluation | P4 · Evals | Task-success/tool-call eval gate |
| Streaming chat & citation/trace UX | P5 · UI | Deployed UI with traces visible |
| Multi-service deploy on free-tier cloud | P5 · Infra/UI | One-command deploy + recording |
| Multimodal (reserved, budgeted) | P5 · UI/Gateway | Final frontier-model demo |

---

## 5. Rough effort estimate (part-time)

Assumes ~**8–12 focused hrs/week**, one subsystem per session, plan-before-code, tests + evals included.
Ranges reflect learning-curve uncertainty on the AI-engineering pieces (this is a deliberate upskilling
project, not a known-quantity build).

| Phase | Scope summary | Calendar (part-time) | Focused-hours band |
|---|---|---|---|
| **P0** | Repo, infra, env, CI, connectivity smoke | 1–1.5 weeks | 10–18 h |
| **P1** | Permission-aware RAG + pgvector | 3–4 weeks | 35–55 h |
| **P2** | Eval + observability harness, CI-gated | 2–3 weeks | 25–40 h |
| **P3** | Cost-aware gateway + router + dashboards | 2–3 weeks | 25–40 h |
| **P4** | Agent orchestrator + MCP tool servers | 3–4 weeks | 40–60 h |
| **P5** | React UI + containerization + deploy | 2.5–3.5 weeks | 30–50 h |
| **Total** | End-to-end forcing story shipped | **~14–19 weeks** | **~165–260 h** |

**Notes / sequencing risks to budget for.**
- P1 and P4 are the long poles (correctness/safety-heavy). Expect the widest variance there.
- P2 is intentionally *before* P3/P4: a few hours invested in the eval gate repays itself by catching
  regressions in every later phase.
- Estimates exclude the cloud-frontier multimodal demo polish in P5, which is budget-gated, not time-gated.

**Running cost outlook (INR).** Prod app stack ≈ **₹0/mo** (Oracle Always Free). GPU ≈ pay-per-minute on
**JarvisLabs.ai** (~₹41/hr), only while a dev/demo session is live and **paused when idle** (storage persists);
a disciplined cadence keeps this to a few hundred ₹/month.
Final multimodal demo draws on the reserved frontier-model budget only.

---

## 6. Research-driven refinements (web-validated, June 2026)

Gaps identified by checking the current state of the ecosystem against the Atlas vision, and where each
is now addressed. These are folded into the phase criteria above; this table is the audit trail.

| # | Gap found vs. vision | Why it matters for Atlas | Resolution → phase |
|---|---|---|---|
| G1 | **PII detection/egress redaction** was absent | Financial/compliance data cannot leak through prompts/responses; a portfolio-grade compliance copilot must show this | Added to **P3** Gateway egress path (redaction + traced events) |
| G2 | MCP transport/auth had drifted from the current spec (Streamable HTTP, **OAuth 2.1 resource server**, RFC 8707 resource indicators) | Demonstrating the *current* MCP security model is exactly the in-demand skill | Updated **P4** MCP tool servers to Streamable HTTP + OAuth 2.1 resource server |
| G3 | Human-in-the-loop lacked a protocol mechanism | MCP **elicitation** is now the native way a server requests user input mid-task — cleaner than a bespoke pause | **P4** HITL implemented via MCP elicitation / LangGraph `interrupt`→`Command(resume)` |
| G4 | Caching was generic; no spend-caps/circuit breaker | Cost-aware gateway is the portfolio's "cost story"; semantic cache + budget caps are now table-stakes | **P3** semantic caching, per-user/route budget spend-caps, circuit breaker |
| G5 | pgvector index strategy + version unpinned | HNSW vs IVFFlat and pgvector ≥0.7/PG16 materially affect recall/latency | **P1** pins HNSW + pgvector ≥0.7 / PG≥16; decision logged |
| G6 | Eval harness was quality-only | Compliance needs **adversarial/red-team** (prompt-injection, jailbreak, access-bypass) as a hard gate, not just faithfulness | **P2** adds adversarial eval set as a merge gate |
| G7 | Spring AI native capabilities underused | `RetrievalAugmentationAdvisor`/`QuestionAnswerAdvisor` (RAG) and `RelevancyEvaluator`/`FactCheckingEvaluator` (eval) reduce custom code and are idiomatic | **P1** uses Advisors; **P2** uses native evaluators as a cheap inline pre-filter |
| G8 | Agent memory durability unspecified | Production agents must resume after interrupt/restart; reusing our Postgres avoids new infra | **P4** durable Postgres checkpointer for agent state |
| G9 | Audit logging not explicitly immutable | Compliance review needs a tamper-evident trail of governed actions | **P4** append-only/immutable, queryable tool-call audit log |

**Framework currency confirmed:** Spring AI **1.0 GA** (early 2026) provides first-class RAG, pgvector,
function-calling, Advisors, native evaluators, and MCP client/server — validating the Java-core thesis in
CLAUDE.md. RAGAS + DeepEval + Langfuse remain the standard eval/observability triad. LangGraph (1.x/2.0)
remains the production agent-orchestration choice with durable checkpointing and interrupt/resume HITL.

---

## 7. Security & governance baseline (CRITICAL — woven into every phase)

Because Atlas is a financial/compliance copilot, security is mapped **explicitly** to the **OWASP Top 10 for
LLM Applications (2025)** and the **OWASP Top 10 for Agentic Applications (2026)**, observability is
standardized on **OpenTelemetry GenAI semantic conventions**, and design is informed by **NIST AI RMF** and
the **EU AI Act** (high-risk obligations effective 2026-08-02). Security work is folded into each phase's DoD
— there is **no separate security phase** — and the per-phase effort uplift is absorbed in the §5 upper ranges.

### 7.1 OWASP LLM Top 10 (2025) → Atlas control map
| OWASP risk | Atlas control | Phase | Status |
|---|---|---|---|
| LLM01 Prompt Injection | Input guardrails + poisoned-doc fixture tests | P1 | In plan |
| LLM02 Sensitive Information Disclosure | PII detection + egress redaction; clearance-scoped retrieval | P3 / P1 | Added §6 (G1) |
| **LLM03 Supply Chain** | CI dependency + secret scanning; digest-pinned images/models; SBOM/AIBOM | P0 | **Added now** |
| **LLM04 Data & Model Poisoning** | Ingestion validation + source provenance; trusted-corpus-only admission | P1 | **Added now** |
| **LLM05 Improper Output Handling** | Output sanitization/encoding at gateway egress + safe UI rendering | P3 / P5 | **Added now** |
| LLM06 Excessive Agency | Least-privilege MCP tools; HITL approval; per-call clearance re-check | P4 | In plan |
| **LLM07 System Prompt Leakage** | No secrets in prompts; system-prompt-leakage red-team tests | P2 | **Added now** |
| LLM08 Vector & Embedding Weaknesses | RBAC filtering at retrieval; no cross-clearance leakage (negative-access tests) | P1 | In plan (explicit) |
| LLM09 Misinformation | Grounded citations + RAGAS faithfulness merge-gate | P1 / P2 | In plan |
| LLM10 Unbounded Consumption | Rate limiting + budget spend-caps + circuit breaker | P3 | Added §6 (G4) |

### 7.2 Agentic (2026) extensions → covered in P4
Tool/action **least-privilege**, mandatory **human-in-the-loop**, **immutable audit trail**, identity &
excessive-autonomy controls (per-call clearance re-check), and **memory-poisoning** resistance (validated,
durable Postgres checkpoints) — all land in **P4**.

### 7.3 Observability & governance standards
- **OpenTelemetry GenAI semantic conventions** (`gen_ai.*` spans/metrics, incl. MCP) — OTel graduated CNCF in
  2026; Langfuse ingests OTel. Atlas standardizes tracing on these rather than proprietary-only schemas → **P2**.
- **NIST AI RMF + EU AI Act** high-risk principles (human oversight, traceability, record-keeping) inform the
  audit-trail, HITL, and trace requirements. Treated as **design constraints**, not a compliance certification;
  recorded in `DECISIONS.md` (ADR-0007).

---

## Open questions — RESOLVED

1. ~~Domain data source~~ → **Resolved:** HF financial corpus (SEC filings / FinanceBench) + synthetic clearance overlay + golden eval set. *(§0.1)*
2. ~~Auth scope~~ → **Resolved:** simulated identity/clearance provider. *(§0.2)*
3. ~~Deploy target~~ → **Resolved:** Oracle Cloud Always Free ARM for app stack (Hetzner fallback); **JarvisLabs.ai** (Indian, INR/UPI, per-minute, pause/resume) GPU for Ollama, E2E Networks fallback. *(§0.3, ADR-0006)*
4. ~~Effort cadence~~ → **Resolved:** 8–12 hrs/week. *(§0.4)*
