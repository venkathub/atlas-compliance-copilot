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

## P6 — Production hardening & operability (in progress · 2026-06-27)

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
