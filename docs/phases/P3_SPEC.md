# P3 — Cost-aware Gateway, Model Router & Dashboards — SPEC

> Status: **APPROVED — 2026-06-14.** Owner-approved; ready for implementation. All §3 decisions are
> owner-confirmed and logged as **ADR-0033–0040** in `docs/DECISIONS.md` (ADR-0034 supersedes ADR-0016).
> **Updated 2026-06-14 with §8 — a web-validated (June 2026) P3 gap analysis** (8 refinements folded into the
> sections below). The one decision it re-opened — **G-P3-1 / D-P3-1**, Gateway framework — was **resolved:
> owner switched reactive → `gateway-server-webmvc`** (§8.1). Next: implement per the §5 task breakdown.
> Phase owner doc set: `CLAUDE.md` · `docs/ROADMAP.md` (§2 P3, §6 G1/G4, §7 LLM02/LLM05/LLM10) ·
> `docs/DECISIONS.md` (ADR-0003 IdP, ADR-0005 models, ADR-0006 GPU, ADR-0016 clearance shim **superseded here**) ·
> `docs/RUNBOOK.md`. Date drafted: 2026-06-14.

This phase puts a **single front door** in front of the RAG Engine: it **authenticates** (simulated IdP,
ADR-0003), **routes** each request to the cheapest adequate model, **caches** semantically, **rate-limits**,
**caps spend**, **detects and redacts PII at egress**, **sanitizes model output (LLM05)**, and makes the
**cost story visible** on a Grafana dashboard. Cost discipline becomes an enforced, demonstrable feature — not
a footnote. It is the first phase where the P2 eval gate is run **through the Gateway path** to prove routing
never trades quality below the eval floor (R2).

It does **not** change RAG retrieval/RBAC behaviour (P1 stays frozen), and it ships **no agents, MCP, or UI**.

---

## 1. Scope

### In scope
1. **API Gateway service (`/gateway`, Spring Boot):** a new module that fronts `rag-engine`'s `POST /v1/query`.
   All client traffic enters here; the RAG Engine is no longer called directly except in tests.
2. **Simulated identity / clearance provider (ADR-0003):** a token endpoint that mints a **cryptographically
   verifiable signed clearance claim** (JWT) for a dev user; the Gateway validates it on every request and is
   the **trust boundary** that resolves caller clearance. This **supersedes the P1 `X-Atlas-Clearance` header
   shim (ADR-0016)** — downstream `rag-engine` now receives a Gateway-asserted, verified clearance, never a
   client-supplied header.
3. **Cost-aware model router:** selects a **model tier** per request on cost / latency / quality policy,
   defaulting to the small/quantized model (ADR-0005) and escalating **only by policy**. The tier is passed to
   `rag-engine`, which owns model serving (Spring AI). Routing rules logged in `DECISIONS.md`.
4. **Semantic cache (Redis):** embedding-similarity cache (not exact-match), **clearance-partitioned** so a
   cached answer is never served across clearance boundaries (R1 reinforcement). TTL + invalidation on corpus
   re-ingest.
5. **Rate limiting:** per-user and per-route limits backed by Redis.
6. **Resource controls + circuit breaker (LLM10 Unbounded Consumption):** per-user/route token-cost budgets
   in Redis (pre-request check + post-request accounting); **per-request input-size validation + max-output-token
   caps + timeouts**; a Resilience4j circuit breaker on model/RAG failure or timeout with a defined fallback;
   and a **cost-spike anomaly alert** on the dashboard (G-P3-6).
7. **PII detection + egress redaction (G1, LLM02):** prompts **and** responses scanned; PII redacted before it
   leaves the Gateway; **redaction events traced** (count/types, never the PII itself).
8. **Output handling / sanitization (G-§7 LLM05):** model output is sanitized/encoded at egress (no
   executable/unsafe/markup-injected content passes through) before reaching downstream consumers.
9. **Metering + dashboards:** Micrometer → Prometheus → Grafana exposing **tokens, cost, latency per
   route / model-tier / user**, plus cache hit-rate, rate-limit/budget rejections, redaction counts, and
   circuit-breaker state.
10. **Eval-through-Gateway validation (R2):** the P2 harness is pointed at the Gateway path; the eval gate
    (floors + no-regression) must **still pass**, and a **cost-delta report** ("X% cheaper at equal eval
    score") is produced for the portfolio.
11. **CI + RUNBOOK + DECISIONS (ADR-0033…) + PORTFOLIO** updates; `.env.example` extended with all P3 vars.

### Non-goals (explicit — prevent scope creep)
- **No agents, LangGraph, MCP, or tool servers.** All **P4**. The Gateway routes *queries*, not *actions*.
- **No React UI / admin console.** Grafana is the only dashboard surface in P3; the UI is **P5**.
- **No real OIDC/Keycloak IdP.** ADR-0003 stands: the IdP is **simulated** (signed claims), not a federated
  identity provider. No user database, password reset, MFA, or refresh-token rotation beyond what proves the
  enforcement path.
- **No change to RAG retrieval, RBAC, chunking, embeddings, or guardrails.** P1 behaviour is frozen; the
  Gateway only *fronts* it. Any regression in the P1 D4/D7 hard gates blocks this phase.
- **No new embedding/chat model *selection*.** ADR-0005 models stand. P3 adds an **escalation tier** and a
  **reserved frontier tier** (both env-swappable, off by default) — a *routing* concern, not a re-selection of
  the default model. The cache/PII embedder reuses `nomic-embed-text`.
- **No fine-tuning, no training a router/classifier model.** Routing is policy/heuristic-driven; any learned
  router is explicitly out of scope (noted as future work).
- **No production deploy.** Local Docker Compose + CI only (deploy is **P5**).
- **No multi-tenant org model, billing integration, or real currency settlement.** "Cost" is a configured
  cost-units table (synthetic for self-hosted Ollama, real for the frontier tier) used to tell the story.

---

## 2. Design

### 2.1 Language split (Java vs Python) — and why
P3 is a **Java-core phase** — it is the portfolio's "Spring Boot API Gateway" centrepiece and deliberately
keeps the hot request path single-runtime for latency and operability.

- **Java / Spring Boot (`/gateway`) — the entire front door.** Auth (simulated IdP + JWT validation), the
  cost-aware router, semantic cache orchestration, rate limiting, budget caps, circuit breaker, the
  deterministic PII redactor, output sanitization, and Micrometer metering all live here. Rationale: this is
  the **moat** (CLAUDE.md) — "auth & API gateway design" + "cost-aware routing" are exactly the Java/Spring
  skills the project exists to evidence, and putting them on the hot path in one runtime is the honest
  production shape.
- **Java (`rag-engine`) — additive only.** Accepts a Gateway-asserted verified clearance + a selected
  **model-tier** parameter; maps tier → Spring AI `ChatModel`. No retrieval/RBAC change.
- **Python — reused, not extended on the hot path.** The **P2 `/evals` harness** (Python) is pointed at the
  Gateway to produce the eval-through-Gateway gate and the cost-delta report. **PII deep-scan (optional,
  off the hot path):** Microsoft **Presidio** is Python-native; if adopted (see D-P3-4) it runs as a
  **periodic/audit sidecar**, mirroring the P2 "deterministic gate + periodic framework sweep" split — it is
  **not** on the per-request critical path.

**Boundary contract:** clients → Gateway (HTTP/JSON + Bearer JWT) → `rag-engine` (HTTP/JSON + verified
internal clearance + model-tier). Neither imports the other. Same clean seam P4 agents will sit behind.

### 2.2 Component breakdown
```
gateway/                              # Java / Spring Boot — the front door (NEW module)
  auth/
    SimIdpController        # POST /v1/auth/token → signed JWT clearance claim (ADR-0003, sim only)
    JwtClearanceFilter      # validates Bearer JWT, resolves caller clearance = the trust boundary
    DownstreamClearance     # asserts verified clearance to rag-engine (supersedes ADR-0016 shim)
  router/
    ModelRouter             # policy: pick model tier (cost/latency/quality) — default = small (ADR-0005)
    RoutingPolicy           # declarative rules + thresholds (env/config-driven, logged in DECISIONS)
    CostTable               # model → cost-units/1k tokens (synthetic self-hosted + real frontier)
  cache/
    SemanticCache           # embed query → Redis vector lookup; clearance-partitioned; TTL + invalidate
  resilience/
    RateLimiter             # per-user/route (Redis-backed)
    BudgetGuard             # per-user/route spend-cap (Redis counters; pre-check + post-accounting)
    ModelCircuitBreaker     # Resilience4j around rag-engine/model call + fallback
  safety/
    PiiRedactor             # deterministic finance-PII detect+redact at egress (LLM02); traced events
    OutputSanitizer         # encode/strip unsafe output at egress (LLM05)
  metering/
    CostMeter               # Micrometer meters: tokens, cost, latency per route/tier/user; cache/redaction
  GatewayQueryController    # POST /v1/query (public) → orchestrates the pipeline → rag-engine

rag-engine/ (Java — additive only)
  ModelTierResolver         # maps Gateway-supplied tier → Spring AI ChatModel (tiered models)
  DownstreamClearanceFilter # trusts ONLY the Gateway-asserted verified clearance (shim retired in prod path)

evals/ (Python — reused, no hot-path change)
  cost_report.py            # run P2 gate THROUGH the gateway; emit cost-delta ("X% cheaper @ equal score")

infra/
  docker-compose.yml        # + gateway service; Redis already present (P0); Prometheus scrape of gateway
  grafana/                  # NEW cost dashboard: tokens/cost/latency per route/tier/user + cache/budget/cb
  presidio/                 # (conditional, D-P3-4) Presidio sidecar for periodic PII deep-scan
```

### 2.3 Data models / schemas

**Signed clearance claim (simulated IdP JWT, ADR-0003).** Minted by `POST /v1/auth/token`, validated on every
request. Cryptographically verifiable (signature), short-lived:
```jsonc
// JWT payload (claims)
{ "sub": "priya",              // dev user id
  "clearance": "compliance",   // public | analyst | compliance | restricted (P1 hierarchy)
  "iss": "atlas-sim-idp",
  "iat": 1750000000, "exp": 1750003600,
  "jti": "…" }                 // unique id for trace correlation
```
> The signing key is an env-managed secret (`ATLAS_IDP_SIGNING_KEY`/keypair), never in code. The Gateway
> verifies signature + `exp` + `iss`; an invalid/expired/forged token → `401`. This is the verifiable claim
> ADR-0003 requires; the P1 `X-Atlas-Clearance` shim is **disabled on the Gateway-fronted path**.

**Gateway `POST /v1/query` request/response (client-facing).**
```jsonc
// request  (Authorization: Bearer <jwt>)
{ "query": "Summarize open AML exceptions for Northwind this quarter", "topK": 6 }
// response
{ "answer": "…redacted, sanitized, cited…",
  "citations": [ { "n": 1, "documentId": "l2-northwind-amlexc-q2", "clearance": "compliance", "snippet": "…" } ],
  "routing":  { "modelTier": "tier1-small", "model": "qwen2.5:3b-instruct", "escalated": false },
  "cache":    { "hit": true, "similarity": 0.94 },
  "redaction":{ "applied": false, "counts": {} },
  "cost":     { "promptTokens": 812, "completionTokens": 143, "costUnits": 0.0041, "latencyMs": 2810 } }
```

**Routing policy (config / `RoutingPolicy`, env-overridable).**
```jsonc
{ "default_tier": "tier1-small",
  "tiers": {
    "tier1-small":   { "model": "qwen2.5:3b-instruct",  "cost_units_per_1k": 0.30 },
    "tier2-mid":     { "model": "qwen2.5:7b-instruct",  "cost_units_per_1k": 0.70 },
    "tier3-frontier":{ "model": "gpt-4o",  "cost_units_per_1k": 5.00, "enabled": false } },  // budget-gated
  "escalation_rules": [
    { "when": "query_tokens > 1200",            "to": "tier2-mid" },
    { "when": "retrieved_context_tokens > 4000","to": "tier2-mid" },
    { "when": "header X-Atlas-Quality = high",  "to": "tier2-mid" } ],
  "never_below_eval_floor": true }   // R2: routing may never select a tier that fails the P2 gate
```

**Semantic cache entry (Redis).** Key namespace embeds clearance so cross-clearance hits are impossible:
```jsonc
// key:   atlas:cache:<clearance>:<vector-id>     (clearance-partitioned)
{ "embedding": [768-dim],          // nomic-embed-text of the query
  "clearance": "compliance",       // MUST equal caller clearance to be eligible
  "answer": "…", "citations": [...], "model": "qwen2.5:3b-instruct",
  "created_at": "…", "corpus_version": "…" }   // invalidated on re-ingest
// hit iff cosine_sim(query, entry) >= ATLAS_CACHE_SIM_THRESHOLD  AND  entry.clearance == caller.clearance
```

**Budget counter (Redis).** `atlas:budget:<user>:<yyyymmdd>` → accumulated cost-units; `429`/`402` when a
pre-request estimate would exceed `ATLAS_BUDGET_DAILY_CAP`.

**PII redaction event (traced — metadata only, never the PII).**
```jsonc
{ "request_id": "…", "stage": "egress-response", "counts": { "ACCOUNT_NUMBER": 2, "DOB": 1, "PASSPORT": 1 } }
```

### 2.4 Key interfaces & contracts

**Trust-boundary contract (supersedes ADR-0016).** The Gateway is the **only** component that resolves
clearance from a client. It validates the JWT, then forwards to `rag-engine` a clearance the engine can trust
**because it came from the Gateway, not the client**. Mechanism is **D-P3-5** (signed internal header vs JWT
passthrough vs network-only trust). The `rag-engine` rejects client-set `X-Atlas-Clearance` on this path.

**Router → rag-engine contract.** Gateway forwards `POST /v1/query` plus `X-Atlas-Model-Tier: tier1-small`
(or the request body field `modelTier`). `rag-engine`'s `ModelTierResolver` maps it to the Spring AI
`ChatModel`. Default tier = small (ADR-0005). The router never selects a tier marked `enabled:false`
(frontier is budget/policy-gated). **`never_below_eval_floor`**: any tier the router can select must have a
recorded P2 eval pass — proven by the eval-through-Gateway run (R2).

**Semantic-cache contract (clearance-safe + poison-resistant — R1, G-P3-4).** A cache hit requires **both**
cosine-similarity ≥ threshold **and** `entry.clearance == caller.clearance`. Answers are a function of
RBAC-filtered context; serving a higher-clearance answer to a lower-clearance caller would be a permission
leak, so the cache is **partitioned by clearance** and a cross-clearance hit is structurally impossible. Cache
is invalidated on corpus re-ingest (`corpus_version` mismatch → miss). Additional 2026-hardening against
**semantic-cache poisoning / collisions** (NDSS 2026; multi-tenant RAG "response-cache cross-talk"):
- **Trusted-write only:** an entry is cached **only after** its answer passed RBAC + the P1 injection guardrail
  + grounding — the cache can never hold an answer the live path would have refused.
- **Conservative, eval-calibrated threshold:** the similarity threshold is calibrated from the golden set
  (G-P3-8), erring tight to avoid wrong-but-similar collisions; recorded in `gateway-baseline.json`.
- **Optional re-grounding on hit:** a cheap inline `FactCheckingEvaluator` re-check (reused from P2) can gate
  high-stakes hits; a failed re-check → treat as a miss and regenerate.
- **Poisoning/collision test** is a §4.2 hard gate.

**PII / output egress contract (LLM02 + LLM05).** Before any answer leaves the Gateway: (1) `PiiRedactor`
masks finance-PII (account numbers, SSN/TIN, passport, DOB, names tied to restricted docs) on prompt-in and
response-out; (2) `OutputSanitizer` encodes/strips unsafe output (no executable scripts/markup-injection
reaches the consumer). Both emit **metadata-only** traces (counts/types) — the redaction plane must not itself
leak PII (consistent with P2 D-P2-10 content-capture policy).

**Metering contract (Micrometer → Prometheus + OTel GenAI, G-P3-7).** Token usage reuses the **standard
OTel `gen_ai.client.token.usage`** metric wired in P2 (semconv version-pinned via
`OTEL_SEMCONV_STABILITY_OPT_IN`) rather than inventing parallel token meters; **cost** has no OTel-standard
metric yet, so it is emitted as a derived, namespaced **`atlas.gateway.cost.units`** counter. Each request
also emits Gateway-specific meters: `atlas.gateway.request.duration` (timer, tags `route`,`tier`,`user`,
`cache_hit`), `atlas.gateway.cache.hit`/`miss`, `atlas.gateway.ratelimit.rejected`,
`atlas.gateway.budget.rejected`, `atlas.gateway.redaction.count` (tag `entity_type`),
`atlas.gateway.circuitbreaker.state`. Spans on the model hop carry the P2 `gen_ai.*` attributes so the
Gateway trace stitches into the existing Langfuse view.

### 2.5 Request / data flow

**Happy path (`POST /v1/query` through the Gateway):**
1. **AuthN/Z:** `JwtClearanceFilter` validates the Bearer JWT → resolves `clearance` (else `401`).
2. **Rate limit:** `RateLimiter` checks per-user/route quota (else `429`).
3. **Budget pre-check:** `BudgetGuard` estimates cost; rejects if over the daily cap (else `402`/`429`).
4. **PII (ingress):** `PiiRedactor` scans the prompt; redacts before it goes further.
5. **Semantic cache:** embed query (`nomic-embed-text`) → Redis vector lookup **within the caller's clearance
   partition**; on hit (sim ≥ threshold) → jump to step 9 with the cached answer (no model call, near-zero cost).
6. **Route:** `ModelRouter` selects a tier (default small; escalate only by policy). Tier never below the eval
   floor.
7. **Downstream call:** Gateway calls `rag-engine /v1/query` with the **verified clearance** + selected tier,
   wrapped in the `ModelCircuitBreaker` (timeout/failure → fallback: cached/degraded response + clear error).
8. `rag-engine` does the **unchanged** P1 RBAC retrieval + grounded, cited answer using the tier's model.
9. **PII (egress) + sanitize:** redact PII in the answer; `OutputSanitizer` encodes/strips unsafe content.
10. **Meter + cache write:** record tokens/cost/latency (Micrometer); write the answer into the
    clearance-partitioned cache (TTL); **budget post-accounting** (increment actual cost).
11. Return the client response (§2.3); Grafana panels update from Prometheus.

**The hard problems this phase must answer:**
- **Cost vs quality (R2/R3):** escalation must be *evidence-based* — the router can only choose tiers proven by
  the P2 gate, and the phase ships a **cost-delta report** quantifying savings *at equal eval score*.
- **Cache correctness vs RBAC (R1):** the semantic cache is the most dangerous new component — a naïve
  similarity cache would leak across clearances. Clearance-partitioning + the `entry.clearance == caller`
  invariant is a **hard gate** (negative-cache test).
- **PII on the hot path vs latency (G1):** deterministic Java redaction keeps the per-request path fast and
  cassette-friendly; Presidio (if adopted) runs as a periodic deep-scan, not inline (D-P3-4).

**Security mapping touched in P3 (ROADMAP §7):** LLM02 (PII egress redaction + clearance-scoped cache),
LLM05 (output sanitization at egress), LLM10 (rate limit + budget caps + circuit breaker). The simulated IdP
(ADR-0003) realizes the verifiable-clearance enforcement the whole stack depends on.

### 2.6 Model inventory (full names, env-swappable)
P3 adds **no new default model**; it adds routing *tiers* (all env-swappable; CLAUDE.md: never hardcoded).

| Role | Full model (pinned) | Env var | Served on | Status |
|---|---|---|---|---|
| Default RAG chat (**tier1-small**) | `qwen2.5:3b-instruct` | `OLLAMA_CHAT_MODEL` | Cloud Ollama GPU | locked, ADR-0005 |
| Escalation (**tier2-mid**) | `qwen2.5:7b-instruct` *(swappable; `llama3.1:8b` already pulled in P2)* | `ATLAS_ROUTER_TIER2_MODEL` | Cloud Ollama GPU | **new P3 (D-P3-3)** |
| Frontier (**tier3**, budget-gated, **off by default**) | `gpt-4o` *(recommended; swappable)* | `ATLAS_ROUTER_FRONTIER_MODEL` (+ `_BASE_URL`,`_API_KEY`) | Cloud frontier API | new P3, reserved |
| Cache + PII embedding | `nomic-embed-text` (768-dim) | `OLLAMA_EMBED_MODEL` | Cloud Ollama GPU | **reused**, ADR-0005 |

- **GPU footprint:** co-hosting `qwen2.5:3b` (~2–3 GB) + `nomic-embed-text` (~0.5 GB) + `qwen2.5:7b` (~5 GB q4)
  ≈ **~8 GB VRAM** — within the L4/A5000-class GPU (ADR-0006). The frontier tier is API-only (no local VRAM).
- **Does the Cloud Ollama LLM need to be live?** Same pattern as P2: **CI gate runs on P2 cassettes (GPU OFF)**;
  **dev + the live cost-delta calibration run need the GPU ON** (then auto-paused via the P2 `infra/gpu` helper).
  Cache/router/rate-limit/budget/PII unit + integration tests are **model-free** (stubbed rag-engine).

---

## 3. Decisions to make now

> Locked and **not** re-opened: ADR-0003 (simulated IdP — *direction*), ADR-0005 (models/dim), ADR-0006 (GPU),
> ADR-0002 (pgvector), and all P1/P2 retrieval/RBAC/eval ADRs. Below are the **open P3 choices.** On your
> confirmation each is logged as a new ADR (**0033…**) in `docs/DECISIONS.md`. The four starred (★) are the
> most consequential and are surfaced as focused questions after this spec.
>
> **Owner-confirmed 2026-06-14 (all matched the recommendation):**
> **D-P3-1 → (a) revised to WebMVC** (`gateway-server-webmvc`, owner-confirmed 2026-06-14 after §8.1) ·
> **D-P3-3 → (a)** declarative rules + escalation ·
> **D-P3-4 → (a)** hybrid Java hot-path redactor + Presidio periodic deep-scan · **D-P3-2 → (a)** Redis Stack
> vector search. Unstarred **D-P3-5 → (a)**, **D-P3-6 → (a)**, **D-P3-7 → (a)**, **D-P3-8 → (a)** proceed as
> recommended unless objected. ADRs **0033–0040** to be logged on final spec approval.

**★ D-P3-1 — Gateway framework** *(owner-confirmed 2026-06-14 → (a) WebMVC, after §8.1 research)*
- (a) **Spring Cloud Gateway Server — `gateway-server-webmvc`** *(CONFIRMED)* — the non-reactive (Servlet,
  blocking) Spring Cloud Gateway on Spring Boot 4; purpose-built routes/filters with Redis `RequestRateLimiter`
  and Resilience4j, **matching the blocking `rag-engine`/Spring AI idiom** and a solo Java engineer's footing.
  Still the canonical "Spring Cloud Gateway" portfolio artifact. *Trade-off: not reactive — fine, since the
  Gateway proxies rather than streams model tokens.*
- (b) **Spring Cloud Gateway Server — reactive / WebFlux** — idiomatic reactive gateway; the right call **only**
  if the Gateway must itself stream model tokens later (a P5/UX concern). Adds Mono/Flux complexity in front of
  a blocking stack now. *(Originally recommended; superseded by §8.1.)*
- (c) Plain reverse proxy (Nginx/Envoy) + a thin Spring policy service — least Java, but the *cost router* logic
  is the whole point, so pushing it out of Spring defeats the portfolio purpose.
- **Recommendation/decision: (a) WebMVC** — lower-risk, idiom-matched, still demonstrates the skill; reactive
  reconsidered only if/when token-streaming pass-through is needed (P5).

**★ D-P3-3 — Model router strategy**
- (a) **Declarative rules + policy escalation** *(recommended)* — small/quantized by default; escalate only on
  explicit signals (query/context size, an explicit `quality=high` hint, eval-floor guard). Transparent,
  testable, cheap, and easy to put on a dashboard. *Trade-off: heuristics, not learned.*
- (b) **Heuristic complexity classifier** (length/keyword/entropy score → tier) — slightly smarter routing, but
  another thing to tune/justify and harder to make deterministic for tests.
- (c) **LLM-as-router** (a small model classifies difficulty) — flexible, but adds a model call + cost +
  latency + non-determinism to *every* request, fighting the cost thesis.
- **Recommendation: (a)** — rules + eval-floor guard is the honest "cost-aware routing" story, fully
  deterministic for CI, and the cost-delta report proves it. **Refined by G-P3-3:** add a **model-cascade**
  escalation — try tier-1, and escalate when the cheap inline `FactCheckingEvaluator`/low-confidence check
  fails — a deterministic middle ground stronger than pure static rules. Cost-delta anchored to RouteLLM's
  45–85% learned-router band (§8.3); a learned router (RouteLLM/`semantic-router`) is explicit future work.

**★ D-P3-4 — PII detection engine (G1 / LLM02)**
- (a) **Hybrid: deterministic Java redactor on the hot path + Presidio (Python) as a periodic deep-scan**
  *(recommended)* — finance-PII (account #s, SSN/TIN, passport, DOB, restricted-doc names) is a *known,
  bounded* set, so regex/dictionary redaction is fast, deterministic, cassette-friendly, and single-runtime on
  the request path; Microsoft **Presidio** runs off-path (periodic/audit) for broad NER recall, new findings
  distilled into the deterministic rules. Mirrors the P2 fixture-gate + Promptfoo-sweep split. *Trade-off: a
  second (off-path) service if/when Presidio is enabled.*
- (b) **Presidio sidecar inline on every request** — best NER recall, but a Python hop on the hot path adds
  latency + a container on the 24 GB ARM box + non-determinism; heavy for a known PII set.
- (c) **Java-only deterministic** (no Presidio at all) — simplest/fastest, but narrower recall; under-sells the
  "PII detection" skill and may miss free-text PII.
- **Recommendation: (a)** — deterministic gate keeps the hot path fast and the CI gate stable; Presidio adds
  real breadth as a renewable source of redaction rules without taxing every request.

**★ D-P3-2 — Semantic cache store**
- (a) **Redis (vector search) — Redis Stack / RediSearch** *(recommended)* — keeps all cache concerns (vector
  similarity, TTL, eviction, clearance-partitioned keys) in the store P0 already runs; native TTL fits a cache.
  *Trade-off: Redis Stack image (ARM-supported) replaces vanilla Redis.*
- (b) **Reuse pgvector** for cache vectors — no new image, one vector engine, but mixes cache (ephemeral,
  TTL-driven) with the system-of-record DB and you hand-roll expiry.
- (c) **In-process (Caffeine) + exact-match only** — simplest, but it's not *semantic* (the DoD requires
  embedding-similarity), so it fails the phase intent.
- **Recommendation: (a)** — semantic caching with native TTL in the existing cache tier; clearance-partitioned
  keys make the RBAC invariant structural.

**D-P3-5 — How the Gateway conveys verified clearance to `rag-engine`** *(trust boundary; supersedes ADR-0016)*
- (a) **Gateway-signed internal header / short-lived internal token** *(recommended)* — Gateway re-asserts the
  verified clearance as a value `rag-engine` validates (HMAC/shared-secret or the same JWT re-issued for the
  internal hop). Defense-in-depth, explicit, testable. *Trade-off: a shared internal secret to manage.*
- (b) **JWT passthrough** — forward the client JWT; `rag-engine` validates it directly. Less to build, but
  spreads IdP-verification responsibility into a second service and couples it to token format.
- (c) **Network-trust only** — `rag-engine` trusts a plain header because only the Gateway can reach it
  (compose network). Simplest, but a single misconfig re-opens the LLM08 leak; weak for a compliance story.
- **Recommendation: (a)** — keeps the Gateway the single trust boundary while letting `rag-engine`
  independently verify (matches the P4 "tools re-check clearance" defense-in-depth ethos).

**D-P3-6 — Rate-limit + budget algorithm**
- (a) **Token-bucket (Spring Cloud Gateway `RequestRateLimiter` / Bucket4j) on Redis for rate; Redis daily
  counters for budget** *(recommended)* — idiomatic, distributed, survives restarts. *Trade-off: Redis Lua/
  atomic-op care for correctness.*
- (b) Fixed-window counters — trivial, but bursty at window edges.
- (c) In-memory limits — simplest, but wrong the moment there's >1 instance; not production-shaped.
- **Recommendation: (a)**.

**D-P3-7 — Circuit-breaker scope & fallback**
- (a) **Resilience4j breaker around the `rag-engine`/model call; fallback = serve a fresh cache hit if any,
  else a clear typed error (`503` + retry-after)** *(recommended)* — bounds blast radius, honest UX.
- (b) Breaker + automatic tier-downgrade on trip — cheaper degraded answers, but risks silently dropping below
  the eval floor; only acceptable if the downgrade target is still eval-passing.
- (c) No breaker, rely on timeouts — simplest, but a stalled GPU cascades into the Gateway (R5).
- **Recommendation: (a)** (with (b) considered only for eval-passing downgrade targets).

**D-P3-8 — Cost-units model (self-hosted has no per-token $)**
- (a) **Configured cost-units table** (synthetic per-1k for self-hosted tiers derived from GPU ₹/hr ÷ throughput;
  real $ for the frontier tier) *(recommended)* — makes the dashboard tell a true relative story and a real one
  for frontier spend. *Trade-off: the self-hosted numbers are an estimate, documented as such.*
- (b) Track tokens/latency only, no cost — honest but misses the headline "cost as a feature" deliverable.
- (c) Real $ only on the frontier tier, tokens elsewhere — partial story.
- **Recommendation: (a)** — a documented cost-units table (ADR) backs the cost-delta report.

---

## 4. Test strategy

> Three things get verified: (i) the **Gateway code** (unit/integration), (ii) the **RBAC/cost invariants**
> (hard gates), and (iii) the **RAG quality through the Gateway** (the reused P2 eval gate). Most Gateway tests
> are **model-free** (stubbed `rag-engine`) so they run in CI with the GPU off.

### 4.1 Gateway unit/integration tests (JUnit, model-free where possible)
- **AuthN/Z:** valid JWT → `clearance` resolved; expired/forged/missing → `401`; client-set
  `X-Atlas-Clearance` is **ignored** on the Gateway path (shim retired).
- **Router:** default selects tier1-small; each escalation rule fires correctly; a tier marked `enabled:false`
  (frontier) is **never** selected; `never_below_eval_floor` honoured.
- **Semantic cache — hit/miss math:** sim ≥ threshold → hit; below → miss; corpus-version mismatch → miss; TTL
  expiry → miss. (Stubbed embeddings.)
- **Rate limit / budget:** over-quota → `429`; over daily cap → `402`/`429`; counters increment by actual cost.
- **Circuit breaker:** downstream timeout/error trips the breaker; fallback returns the typed response.
- **PII redactor:** account #, SSN/TIN, passport, DOB, restricted-doc names masked on ingress + egress;
  redaction event carries **counts only, no PII**.
- **Output sanitizer:** script/markup-injection payloads in a model answer are encoded/stripped (LLM05).
- **Metering:** the expected Micrometer meters are emitted with correct tags (in-memory registry).

### 4.2 Hard gates (must pass — block the phase)
- **★ Semantic-cache RBAC gate (R1, new):** a negative-cache suite proves a cached answer generated at a higher
  clearance is **never** served to a lower-clearance caller (cross-partition hit is structurally impossible) —
  the cache analogue of P1's D4 negative-access test. **0 cross-clearance cache hits.**
- **★ Semantic-cache poisoning/collision gate (G-P3-4, new):** prove (a) **trusted-write only** — an answer
  that fails RBAC/guardrail/grounding is never cached; (b) a crafted **near-miss query** below the calibrated
  similarity threshold does **not** return a colliding entry; (c) an injection-poisoned candidate cannot enter
  the cache. **0 poisoned/colliding hits served.**
- **P1 D4/D7 stay green through the Gateway:** negative-access (0 cross-clearance leaks) and prompt-injection
  (LLM01) re-run end-to-end via the Gateway path — fronting must not weaken them.
- **PII egress gate (LLM02):** the restricted-doc PII strings (reused from P1 `poisoned/expectations.json`)
  **never** appear in a Gateway response; redaction is mandatory, not best-effort.
- **Output-handling gate (LLM05):** no executable/unsafe content passes egress.

### 4.3 Eval-through-Gateway (the headline R2/R3 deliverable)
- **Quality gate (reused P2 harness, cassette-replay):** the P2 RAGAS floors + no-regression must **still pass
  when queries flow through the Gateway** (auth + route + cache + redact). Routing/caching must not drop quality.
- **Cost-delta report (live calibration job, GPU on, not the PR gate):** run the golden set through the Gateway
  with caching+routing **on vs off**; record **% cost reduction at equal eval score** ("X% cheaper, same
  faithfulness/relevancy") → `docs/PORTFOLIO.md`. Uses the P2 `infra/gpu` fail-safe helper (auto-pause).
- **Cache-quality check:** semantic-cache hits must return an answer that *still passes* faithfulness (a stale/
  mismatched cache hit that degrades the answer is a regression) — validated on the golden set.

### 4.4 Thresholds (gate numbers)
| Check | Type | Gate |
|---|---|---|
| RAGAS floors + no-regression **through Gateway** | reused P2 gate | unchanged P2 floors must hold |
| Semantic-cache cross-clearance hits | binary, **hard gate** | **0** |
| Semantic-cache poisoning / collision (G-P3-4) | binary, **hard gate** | **0** poisoned/colliding hits served |
| Negative-access (D4) via Gateway | binary, **hard gate** | **0** cross-clearance leaks |
| Prompt-injection (D7 / LLM01) via Gateway | binary, **hard gate** | **100%** pass |
| PII egress leakage (LLM02) | binary, **hard gate** | **0** PII strings in any response |
| Output sanitization (LLM05) | binary, **hard gate** | **0** unsafe payloads pass |
| Rate-limit / budget enforcement | functional | over-limit rejected deterministically |
| Cost reduction at equal eval score | report (portfolio) | quantified % (target set from first calibration) |

---

## 5. Task breakdown (ordered, independently committable)

1. **Gateway module skeleton + compose:** new `/gateway` Spring Boot module (framework per D-P3-1), wired into
   `infra/docker-compose.yml`, Prometheus scrape of `/actuator/prometheus`; health check; `.env.example` P3
   vars. *(commit: `feat(gateway): module skeleton + compose + actuator`)*
2. **Simulated IdP + JWT trust boundary (ADR-0003, supersedes 0016):** `POST /v1/auth/token` mints a signed
   clearance claim; `JwtClearanceFilter` validates it; `rag-engine` `DownstreamClearanceFilter` trusts only the
   Gateway-asserted clearance (D-P3-5); client `X-Atlas-Clearance` ignored on this path; auth tests.
   *(commit: `feat(gateway): simulated IdP + verified clearance trust boundary`)*
3. **Pass-through query path:** `GatewayQueryController` proxies `POST /v1/query` → `rag-engine` with verified
   clearance (no router/cache yet); end-to-end IT (stubbed + live-tagged). *(commit: `feat(gateway): query passthrough to rag-engine`)*
4. **Model router + tiering:** `ModelRouter`/`RoutingPolicy`/`CostTable` (D-P3-3, D-P3-8); `rag-engine`
   `ModelTierResolver` maps tier → Spring AI `ChatModel`; default-small + escalation-rule tests; eval-floor
   guard. *(commit: `feat(gateway): cost-aware model router + tiering`)*
5. **Semantic cache (clearance-partitioned):** `SemanticCache` over Redis vector (D-P3-2); embed via
   `nomic-embed-text`; TTL + corpus-version invalidation; **the cross-clearance negative-cache hard gate**.
   *(commit: `feat(gateway): clearance-safe semantic cache`)*
6. **Rate limiting + budget caps + circuit breaker:** `RateLimiter`/`BudgetGuard`/`ModelCircuitBreaker`
   (D-P3-6, D-P3-7); Redis counters; Resilience4j; enforcement ITs. *(commit: `feat(gateway): rate limit, budget caps, circuit breaker (LLM10)`)*
7. **PII redaction + output sanitization (egress):** `PiiRedactor` (D-P3-4 deterministic hot path) +
   `OutputSanitizer` (LLM05); metadata-only redaction traces; PII-egress + sanitization hard-gate tests.
   *(commit: `feat(gateway): PII egress redaction (LLM02) + output sanitization (LLM05)`)*
8. **Metering + Grafana cost dashboard:** `CostMeter` Micrometer meters; provisioned Grafana dashboard
   (tokens/cost/latency per route/tier/user + cache hit-rate, rejections, redaction counts, breaker state).
   *(commit: `feat(gateway): cost/token/latency metering + Grafana dashboard`)*
9. **(Conditional, D-P3-4) Presidio periodic deep-scan:** `infra/presidio` sidecar + off-path audit job that
   feeds new redaction rules back into the deterministic redactor. *(commit: `feat(gateway): Presidio periodic PII deep-scan`)*
10. **Eval-through-Gateway + cost-delta:** point the P2 harness at the Gateway; reused RAGAS gate must pass;
    `evals/cost_report.py` produces the cost-delta; CI gate runs the Gateway-path quality + RBAC/PII hard gates.
    *(commit: `ci: eval-through-gateway gate + cost-delta report`)*
11. **Docs + portfolio:** `gateway/README.md`, `rag-engine/README.md` (tier note), `docs/RUNBOOK.md` (auth +
    dashboards bring-up), `docs/DECISIONS.md` (ADR-0033…), quantified `docs/PORTFOLIO.md` cost bullet.
    *(commit: `docs(gateway): P3 dashboards, README, RUNBOOK, ADRs`)*

---

## 6. Definition of Done (P3 — generic DoD from CLAUDE.md, instantiated)

- [ ] **Code complete & matches this spec.** `/gateway` fronts `rag-engine`: simulated-IdP auth, cost-aware
      routing, semantic cache, rate limiting, budget caps, circuit breaker, PII egress redaction, output
      sanitization, metering — all config env-swappable (no hardcoded models/keys/URLs/secrets).
- [ ] **Unit + integration tests pass in CI.** Gateway model-free unit/ITs (auth, router, cache math, rate/
      budget, breaker, redactor, sanitizer, metering) green; **the P1 D4/D7 hard gates remain green through the
      Gateway path.**
- [ ] **Hard gates met & recorded:** **0** cross-clearance semantic-cache hits; **0** negative-access leaks via
      Gateway; **100%** prompt-injection pass; **0** PII strings in any response (LLM02); **0** unsafe payloads
      at egress (LLM05).
- [ ] **Eval thresholds still met *through the Gateway*** (reused P2 RAGAS floors + no-regression) — routing/
      caching proven not to degrade quality (R2); the eval gate blocks merge on the Gateway path.
- [ ] **Cost story demonstrated & quantified:** Micrometer→Prometheus→Grafana dashboard shows tokens/cost/
      latency per route/tier/user; a **cost-delta** ("X% cheaper at equal eval score") is recorded.
- [ ] **Roadmap P3 exit criteria met** (§2 P3): semantic cache (not exact-match), PII detection+redaction with
      traced events, LLM05 output handling, budget spend-caps + circuit breaker, small-by-default escalation
      policy, cache+rate-limit ITs, eval thresholds hold through the Gateway, cost delta captured.
- [ ] **Module README + `docs/DECISIONS.md` updated** (ADR-0033…; ADR-0016 marked superseded by the IdP path;
      ADR-0003 realized). Routing rules + cost-units table logged.
- [ ] **Runs cleanly from a fresh clone** via `infra` compose + documented `.env` (`make ... up` brings up
      Gateway + Redis + rag-engine + Grafana/Prometheus); RUNBOOK updated (auth token mint, dashboard URLs).
- [ ] **30-second demo path:** mint a token for `priya` → ask the Northwind question through the Gateway → see
      a cited, redacted, sanitized answer + the routing/cache/cost fields → watch the cost dashboard update;
      repeat the query → semantic-cache hit at ~zero cost; ask the same as `guest-public` → no cross-clearance
      cache hit, RBAC-correct answer.
- [ ] **Resume-ready, quantified bullet** drafted in `docs/PORTFOLIO.md` (e.g. "Cut LLM serving cost N% at
      equal eval score via a cost-aware Spring Cloud Gateway router + clearance-safe semantic cache, with
      per-route token/cost/latency dashboards").

### 6.1 Deviations / partials
*(to be filled honestly at implementation, in the P2 spec's §6.1 style.)*

- **P3 task 4 — model-cascade + `retrieved_context_tokens` rule deferred (owner-confirmed 2026-06-17).**
  The cost-aware router (ADR-0035) shipped its **pre-call deterministic rules** (default tier1-small; escalate
  to tier2-mid on `X-Atlas-Quality: high` or estimated `query_tokens > threshold`; frontier reserved/never
  auto-selected; eval-floor guard) plus the `rag-engine` `ModelTierResolver` (tier → portable
  `ChatOptions.model(...)`). The **model-cascade** (escalate when the tier-1 answer fails the inline
  `FactCheckingEvaluator`) and the **`retrieved_context_tokens > 4000`** rule are **not yet wired**: both are
  *post-retrieval / post-generation* signals the Gateway cannot see before calling `rag-engine`, so they need
  `rag-engine` to surface a confidence/context signal in the response — a cross-cutting change scheduled with
  the eval-through-Gateway work (task 10) or a dedicated follow-up. `ATLAS_ROUTER_CASCADE_ENABLED` is bound but
  inert until then. No eval-floor risk: escalation only moves *up* to an eval-passing tier.

---

## 7. Open questions for the owner (focused — blocking spec sign-off)
The four starred decisions in §3 most shape the build and are surfaced as focused questions: **D-P3-1**
(Gateway framework), **D-P3-3** (router strategy), **D-P3-4** (PII engine), **D-P3-2** (semantic-cache store).
The unstarred D-P3-5/6/7/8 proceed as recommended unless objected. On confirmation, ADRs **0033…** are logged
in `docs/DECISIONS.md`. **No code is written until then.**

> See **§8** for the web-validated (June 2026) gap analysis: it re-opened one decision — **G-P3-1**, Gateway
> framework — now **resolved to WebMVC** (§8.1) — plus several refinements folded into the sections above.

---

## 8. Research-driven refinements (web-validated, June 2026) — P3 gap analysis

Following the ROADMAP §6 method, this section audits the P3 plan against the **current** state of the
ecosystem (searched June 2026) and folds each gap back into the spec. The vision is unchanged; these sharpen
the *how*. Sources are listed at the end.

| # | Gap found vs. vision/plan | Why it matters for Atlas | Resolution → where |
|---|---|---|---|
| **G-P3-1** | **Spring Cloud Gateway now ships a first-class non-reactive `gateway-server-webmvc`** (on Spring Framework 7 / Spring Boot 4) — not just the reactive WebFlux server. The owner-confirmed choice was *reactive*. | The rest of the Java core (`rag-engine`, Spring AI `ChatModel` calls) is **blocking**, and this is a **solo Java engineer** project on a low-spec laptop. A reactive gateway in front of a blocking stack adds cognitive load (Mono/Flux) for little gain, since the Gateway only *proxies* to `rag-engine` (it doesn't stream model tokens itself). The WebMVC gateway still provides routes, filters, Redis rate-limiting, and Resilience4j circuit breakers. | **RESOLVED → D-P3-1 = `spring-cloud-starter-gateway-server-webmvc`** (owner-confirmed 2026-06-14; matches the blocking idiom; reactive only if token-streaming pass-through is later needed). See §8.1. |
| **G-P3-2** | The **"AI Gateway" is a mature 2026 product category** (LiteLLM, Portkey, Kong AI Gateway, Cloudflare AI Gateway, TrueFoundry) with a converged feature taxonomy: multi-model routing, **semantic cache, failover, spend caps, rate limits, guardrails, PII redaction, observability**. | Validates the P3 feature set as **table-stakes**, and gives a reference taxonomy + a **build-vs-buy** justification the portfolio should state explicitly (the moat is a *self-built, permission-aware* gateway; buying one would offshore the RBAC/compliance core and break the self-hosted/cost thesis). | Added **§8.2 build-vs-buy note** + the taxonomy adopted as the §1 scope checklist; spend-caps/token-budgets reconfirmed as required (D-P3-6/8). |
| **G-P3-3** | **Model routing has a proven reference + quantified ceiling:** RouteLLM reports **45–85% cost reduction at ~95% frontier quality**; the **model-cascade** pattern (cheap-first, escalate on low confidence) is the deterministic middle ground between static rules and a learned router. | Anchors the P3 **cost-delta** deliverable to a published band instead of an arbitrary number, and offers a stronger-yet-still-deterministic escalation mechanism than pure static rules. | **Refines D-P3-3:** keep declarative rules **and add a model-cascade escalation** (escalate when the tier-1 answer fails the cheap inline `FactCheckingEvaluator`/low-confidence check). Cost-delta target band set in §8.3; learned routers (RouteLLM/`semantic-router`) logged as explicit **future work**, not P3. |
| **G-P3-4** | **Semantic-cache poisoning & cross-talk are named 2026 attack vectors** (NDSS 2026 "When Cache Poisoning Meets LLM Systems"; multi-tenant RAG isolation lists "response-cache cross-talk", "semantic-cache collisions"). The spec handled **cross-clearance leakage** but **not poisoning** (fuzzy match exploited to serve a malicious/wrong cached answer) or **collisions** (too-loose threshold serving a wrong-but-similar answer). | This is the single most dangerous new component in P3 in a compliance domain — a poisoned/colliding cache entry bypasses the very RBAC + guardrail + grounding controls P1 built. | **Hardened §2.4 cache contract + new §4.2 hard gate.** Cache is **trusted-write only** (only answers that *passed* RBAC + guardrail + grounding are cached), **conservative calibrated similarity threshold**, optional **cheap re-grounding/faithfulness re-check on hit**, and a **cache-poisoning/collision test** added to the hard gates. |
| **G-P3-5** | The **canonical open-source egress stack is Presidio (PII) + LLM Guard (input/output scanners)**; LiteLLM's reference pattern runs **Presidio NER containers in-VPC**. The spec invented bespoke `PiiRedactor`/`OutputSanitizer`. | Confirms D-P3-4 (Presidio off-path) and gives **LLM Guard** as the idiomatic, self-hostable output-scanner reference for LLM05 — consistent with the self-hosted ethos and a stronger portfolio signal than a hand-rolled sanitizer. | **Refines D-P3-4/§2.2:** keep the deterministic Java redactor on the hot path; name **Presidio + LLM Guard** as the periodic off-path deep-scan stack (LLM02 + LLM05); distil findings back into the hot-path rules. |
| **G-P3-6** | **OWASP LLM10 (Unbounded Consumption) mitigation taxonomy is broader** than the spec: it also requires **input-size validation, per-request max-output-token caps, timeouts/throttling, recursion limits, and cost-spike anomaly detection** — not just rate-limit + budget + breaker. | LLM10 is a named P3 control (ROADMAP §7); a partial implementation under-sells it and leaves real DoS/cost-drain vectors open. | **Expanded §1 scope item 6 + dashboards:** add **per-request input-size + max-output-token caps** and a **budget/cost-spike anomaly alert** on the Grafana board. |
| **G-P3-7** | **The GenAI token metric is standardized** (`gen_ai.client.token.usage` + the required `gen_ai.client.operation.duration`); P2 already emits `gen_ai.*`. The P3 spec invented parallel custom `gateway.tokens` meters. | Emitting parallel custom token meters fragments the Langfuse/Grafana story and diverges from the P2 OTel-semconv decision (D-P2). **Cost** has *no* OTel-standard metric yet, so it stays custom-but-namespaced. | **Aligned §2.4 metering:** emit the **standard `gen_ai.client.token.usage`** (reuse P2 wiring) + a derived, namespaced **`atlas.gateway.cost.units`**; keep semconv version-pinned (P2 `OTEL_SEMCONV_STABILITY_OPT_IN`). |
| **G-P3-8** | Routing/caching literature is emphatic that the **router cost-threshold and the cache similarity-threshold must be eval-calibrated, not guessed** — a too-loose cache or too-aggressive router silently degrades quality. | Reinforces R2: these thresholds are correctness knobs, not tuning preferences; they belong in the recorded baseline like the P2 metric floors. | **Refines §2.6/§4.3:** the cache similarity threshold + router escalation thresholds are **calibrated from the P2 golden set during the live calibration run and recorded** (a `gateway-baseline.json`, mirroring P2's `baseline.json`), never hardcoded. |

### 8.1 G-P3-1 — Gateway framework: reactive vs WebMVC — RESOLVED → WebMVC (owner-confirmed 2026-06-14)
New evidence (Spring Cloud Gateway on Spring Boot 4 ships **both** a reactive server *and* a `gateway-server-webmvc`
server; 2026 migration guides show teams moving reactive→MVC for blocking stacks) shifted the recommendation.
For Atlas — a blocking Spring AI/`rag-engine` core, one Java engineer, a proxy-not-streamer gateway — **WebMVC
is the lower-risk, better-fit choice** and still demonstrates the "Spring Cloud Gateway" skill (routes, filters,
`RequestRateLimiter`, Resilience4j). Reactive remains the right call **only** if the Gateway must itself stream
model tokens (a P5/UX concern, not P3). **Owner reversed the earlier reactive confirmation → `gateway-server-webmvc`
is adopted** (D-P3-1). All other §3 confirmations stand.

### 8.2 Build vs. buy (why Atlas builds its own gateway)
The mature AI-gateway products (LiteLLM/Portkey/Kong/Cloudflare/TrueFoundry) prove the feature set is
table-stakes — but Atlas **builds its own** because: (1) the moat is a **permission-aware, clearance-scoped**
gateway whose cache/router/redaction enforce the *same RBAC* as P1 retrieval — an off-the-shelf gateway has no
notion of Atlas clearances; (2) **self-hosted / no-egress** compliance (CLAUDE.md) rules out SaaS gateways that
ship prompts off-box; (3) the build *is the portfolio artifact* ("auth & API gateway design", "cost-aware
routing"). The products are used as a **feature checklist and reference**, not a dependency. (If ever needed,
**LiteLLM self-hosted** is the closest self-hostable fallback — noted, not adopted.)

### 8.3 Cost-delta target band (anchored to RouteLLM)
RouteLLM's published **45–85% cost reduction at ~95% quality** is the *learned-router ceiling*. Atlas uses
**rules + model-cascade** (deterministic, no trained router), so P3 sets a conservative, honest target:
**demonstrate ≥30% serving-cost reduction at equal eval score** (faithfulness/relevancy within the P2
no-regression band), counting semantic-cache hits (near-zero cost) + small-model-default. The exact figure is
whatever the calibration run measures; the band keeps the portfolio claim credible, with learned routing named
as future upside.

### 8.4 Sources (June 2026)
- Spring Cloud Gateway (Spring Boot 4 / Framework 7; reactive **and** `gateway-server-webmvc`):
  docs.spring.io/spring-cloud-gateway, GitHub issue #4031, att-israel "SCG MVC migration".
- Semantic caching (Redis LangCache / RedisVL `SemanticCache` / GPTCache; 30–70% cost cut; threshold tuning):
  redis.io LangCache tutorial, docs.redisvl.com llmcache, github.com/zilliztech/gptcache, spheron.network.
- Semantic-cache **security** (poisoning/collision/cross-talk/isolation): NDSS 2026 "When Cache Poisoning Meets
  LLM Systems", appscale.blog "Multi-Tenant RAG Isolation 2026: 7 Attack Vectors", tianpan.co cross-tenant
  leakage, Nature s41598-026-36721-w (adversarial-resilient semantic caching).
- Model routing (RouteLLM 45–85% @ ~95% quality; cascades): github.com/lm-sys/RouteLLM, lmsys.org RouteLLM
  blog, tianpan.co "LLM Routing and Model Cascades", burnwise.io routing guide.
- AI-gateway category (routing/cache/spend-caps/guardrails/PII): truefoundry.com guardrails, particula.tech
  decision framework, slashllm.com comparison, agileleadershipdayindia.org token-budget limits.
- PII / output handling (Presidio in-VPC + LLM Guard scanners): truefoundry.com guardrail, infrabase.ai
  Presidio alternatives, futureagi.com AI gateways for PII.
- OWASP **LLM10 Unbounded Consumption** (input/output caps, throttling, anomaly detection):
  genai.owasp.org/llmrisk/llm102025-unbounded-consumption, stackhawk.com, f5 LLM10 guide.
- OTel **GenAI metrics** (`gen_ai.client.token.usage`, required `operation.duration`; semconv still Development):
  opentelemetry.io gen-ai-metrics, github.com/open-telemetry/semantic-conventions-genai, oneuptime.com.
- Spring AI 1.0 observability (ChatClient/ChatModel/EmbeddingModel/VectorStore metrics+tracing; **no** native
  router/semantic-cache → build it): docs.spring.io/spring-ai/observability, infoq.com Spring AI 1.0.
