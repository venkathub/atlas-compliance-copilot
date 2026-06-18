# Atlas — Architectural Decision Log

> Every non-trivial architectural choice gets a dated entry here: **context, options considered, decision,
> rationale, consequences**. This is also interview prep — be thorough on the *why*.
> Companion docs: `CLAUDE.md`, `docs/ROADMAP.md`, `docs/RUNBOOK.md`.
>
> **Status legend:** `Accepted` · `Proposed` · `Superseded by ADR-NNN` · `Deprecated`
> Add new entries at the top of §2 (reverse-chronological). Use the template in §3.

---

## 1. Decision index

| ADR | Date | Title | Status | Phase |
|-----|------|-------|--------|-------|
| 0040 | 2026-06-14 | Cost-units model & cost-delta reporting | Accepted | P3 |
| 0039 | 2026-06-14 | Circuit-breaker scope & fallback | Accepted | P3 |
| 0038 | 2026-06-14 | Gateway resource controls (rate-limit, budget caps, LLM10) | Accepted | P3 |
| 0037 | 2026-06-14 | PII egress redaction + output handling (LLM02/LLM05) | Accepted | P3 |
| 0036 | 2026-06-14 | Clearance-partitioned, poison-resistant semantic cache (Redis Stack) | Accepted | P3 |
| 0035 | 2026-06-14 | Cost-aware model router (declarative rules + model-cascade) | Accepted | P3 |
| 0034 | 2026-06-14 | Simulated-IdP verified-clearance trust boundary | Accepted | P3 |
| 0033 | 2026-06-14 | API Gateway framework (Spring Cloud Gateway WebMVC) | Accepted | P3 |
| 0032 | 2026-06-14 | Katzilla external primary-source data (post-P5 backlog) | Proposed | P6 |
| 0031 | 2026-06-14 | Adversarial breadth: fixtures gate + Promptfoo OWASP sweep | Accepted | P2 |
| 0030 | 2026-06-14 | Trace content-capture & redaction policy (LLM02/LLM07) | Accepted | P2 |
| 0029 | 2026-06-14 | Automated fail-safe GPU lifecycle (pause/resume) | Accepted | P2 |
| 0028 | 2026-06-14 | Golden eval set size & composition | Accepted | P2 |
| 0027 | 2026-06-14 | Cross-encoder reranker (eval-gated A/B) | Accepted | P2 |
| 0026 | 2026-06-14 | Spring AI inline evaluators as cheap pre-filter | Accepted | P2 |
| 0025 | 2026-06-14 | Self-hosted Langfuse (observability) | Accepted | P2 |
| 0024 | 2026-06-14 | Eval metric set & gating thresholds | Accepted | P2 |
| 0023 | 2026-06-14 | Eval-context exposure on /v1/query (includeContexts) | Accepted | P2 |
| 0022 | 2026-06-14 | LLM-as-judge model (cross-family llama3.1:8b) | Accepted | P2 |
| 0021 | 2026-06-14 | Eval LLM in CI: cassette-replay gate + live calibration | Accepted | P2 |
| 0020 | 2026-06-13 | Layer-1 ingestion form: committed FinanceBench evidence snippets | Accepted | P1 |
| 0019 | 2026-06-13 | Testcontainers ITs: docker-java API pin + exec-classifier jar | Accepted | P1 |
| 0018 | 2026-06-13 | Answer generation scope & citation granularity | Accepted | P1 |
| 0017 | 2026-06-13 | Final Layer-1 corpus subset (FinanceBench) | Accepted | P1 |
| 0016 | 2026-06-13 | Clearance transport in P1 (pre-IdP shim) | Superseded by ADR-0034 | P1 |
| 0015 | 2026-06-13 | Prompt-injection guardrail approach (LLM01) | Accepted | P1 |
| 0014 | 2026-06-13 | Reranking approach (seam now, cross-encoder in P2) | Accepted | P1 |
| 0013 | 2026-06-13 | Hybrid search fusion method (RRF) | Accepted | P1 |
| 0012 | 2026-06-13 | RBAC model & enforcement mechanism | Accepted | P1 |
| 0011 | 2026-06-13 | Chunking strategy & chunk size | Accepted | P1 |
| 0010 | 2026-06-13 | CI pipeline, supply-chain controls & multi-arch image | Accepted | P0 |
| 0009 | 2026-06-13 | Local infra under snap-Docker confinement | Accepted | P0 |
| 0008 | 2026-06-13 | Monorepo build topology & framework version pins | Accepted | P0 |
| 0007 | 2026-06-13 | Security & governance baseline (OWASP/OTel/AI gov) | Accepted | P0–P5 |
| 0006 | 2026-06-13 | Production deploy target & GPU host | Accepted | P0/P5 |
| 0005 | 2026-06-13 | Dev models & embedding dimension | Accepted | P0/P1 |
| 0004 | 2026-06-13 | Dataset & RBAC clearance overlay | Accepted | P1 |
| 0003 | 2026-06-13 | Identity / clearance provider (simulated) | Accepted | P3 |
| 0002 | 2026-06-13 | Vector store: Postgres + pgvector | Accepted | P1 |
| 0001 | 2026-06-13 | Core language/runtime split (Java + Python) | Accepted | P0 |

> ADR-0001–0007 were pre-recorded from roadmap planning (CLAUDE.md + `ROADMAP.md` §0); **ADR-0008–0010 capture
> decisions made while implementing P0.** **ADR-0011–0020 are the P1 grooming + implementation decisions**
> (`docs/phases/P1_SPEC.md` §3). **ADR-0021–0031 are the P2 grooming decisions** (`docs/phases/P2_SPEC.md` §3),
> owner-confirmed 2026-06-14 before P2 implementation begins; **ADR-0032 is a Proposed post-P5 backlog item**
> (`ROADMAP.md` §8). **ADR-0033–0040 are the P3 grooming decisions** (`docs/phases/P3_SPEC.md` §3 + §8
> web-validated gap analysis), owner-confirmed 2026-06-14 before P3 implementation begins; **ADR-0034 supersedes
> ADR-0016** by replacing the P1 clearance-header shim with the simulated-IdP verified-clearance trust boundary.
> Each remains open to revision with a new superseding ADR if a later phase surfaces evidence against it.

---

## 2. Decisions

### ADR-0040 — Cost-units model & cost-delta reporting
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P3 · **Spec:** `P3_SPEC.md` §3 (D-P3-8), §8.3
- **Context:** Self-hosted Ollama tiers have no per-token $ price, yet the portfolio thesis is "cost as a
  feature" and needs a credible cost story plus a headline cost-delta ("X% cheaper at equal eval score").
- **Options considered:** (a) a configured **cost-units table** — synthetic per-1k for self-hosted tiers
  (derived from GPU ₹/hr ÷ throughput), real $ for the frontier tier; (b) tokens/latency only, no cost;
  (c) real $ on the frontier tier only, tokens elsewhere.
- **Decision:** **(a)** — a documented cost-units table backs the Micrometer cost meters and a cost-delta
  report; target band **≥30% cheaper at equal eval score**, anchored to RouteLLM's 45–85% learned-router band
  (§8.3) as future upside.
- **Rationale:** makes the Grafana dashboard tell a true *relative* story for self-hosted tiers and a real one
  for frontier spend; the target is honest and eval-gated rather than an arbitrary claim.
- **Consequences:** self-hosted numbers are an estimate (documented as such); the measured cost-delta is
  recorded in `gateway-baseline.json` from the live calibration run, not hardcoded.
- **Implementation note (2026-06-17, P3 task 8):** `CostMeter` (Micrometer → Prometheus at the gateway's
  `/actuator/prometheus`) emits a derived, namespaced **`atlas.gateway.cost.units`** counter (tags
  `route`/`tier`/`user`) plus `atlas.gateway.request.duration` (timer, tag `cache_hit`),
  `atlas.gateway.cache.hit`/`.miss`, `atlas.gateway.ratelimit.rejected`, `atlas.gateway.budget.rejected`, and
  `atlas.gateway.redaction.count` (tag `entity_type`). **Token usage reuses the OTel-standard
  `gen_ai.client.token.usage`** already emitted by rag-engine (no parallel token meter, per G-P3-7). Cost is
  computed from **real token usage** now surfaced in the rag-engine `QueryResponse.usage` (from `ChatResponse`
  metadata) — this **replaces the task-6 budget estimate** for both budget accounting and the §2.3 `cost`
  section `{promptTokens, completionTokens, costUnits, latencyMs}`; a deterministic estimate is the fallback
  when a model doesn't report usage. A cache hit reports ~zero serving cost. Grafana dashboard
  `infra/grafana/dashboards/atlas-cost.json` (auto-provisioned) renders cost/tokens/latency per route/tier/user
  + cache hit-rate, rejections, redaction counts, and circuit-breaker state. **Pragmatic calls:** the
  **cost-spike anomaly alert** is a threshold-marked Grafana panel (not a full alerting rule); the
  circuit-breaker-state panel is **best-effort** (depends on the Resilience4j Micrometer binder); the `user`
  tag is acceptable-cardinality for the dev/demo only.

### ADR-0039 — Circuit-breaker scope & fallback
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P3 · **Spec:** `P3_SPEC.md` §3 (D-P3-7)
- **Context:** A stalled/paused GPU (ADR-0006) or a model error must not cascade into the Gateway and take the
  whole front door down (R5).
- **Options considered:** (a) **Resilience4j breaker around the rag-engine/model call; fallback = a fresh cache
  hit if any, else a typed `503` + retry-after**; (b) breaker + automatic tier-downgrade on trip (cheaper
  degraded answers, but risks dropping below the eval floor); (c) timeouts only, no breaker.
- **Decision:** **(a)**, with **(b)** considered only when the downgrade target is itself eval-passing.
- **Rationale:** bounds the blast radius with honest UX, and never silently drops below the P2 eval floor (R2).
- **Consequences:** breaker thresholds tuned + covered by ITs; the fallback path is explicitly tested.
- **Implementation note (2026-06-17, P3 task 6):** Resilience4j via **`spring-cloud-starter-circuitbreaker-resilience4j`**
  (BOM-managed). `ModelCircuitBreaker` wraps the rag-engine call (`CircuitBreakerFactory.create("rag-engine")`,
  thresholds from `ATLAS_CB_*`); the fallback throws a typed `DownstreamUnavailableException` → mapped by
  `GatewayExceptionHandler` to **`503` + `Retry-After`**. The per-request **timeout is the `RestClient` read
  timeout** (`ATLAS_REQUEST_TIMEOUT_MS`): a stalled/slow GPU trips it, surfacing as an exception the breaker
  records as a failure. The "fresh cache hit" fallback of option (a) is moot on this path (the cache was
  already checked pre-call and missed), so the fallback is the typed `503`. Proven by `GatewayQueryIT`
  (downstream 500 → `503` + `Retry-After`) + a controller unit test.

### ADR-0038 — Gateway resource controls (rate-limit, budget caps, LLM10)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P3 · **Spec:** `P3_SPEC.md` §3 (D-P3-6), §8 (G-P3-6)
- **Context:** OWASP **LLM10 Unbounded Consumption** is a named P3 control; naive model use can drain the
  budget or DoS the system. June-2026 research (G-P3-6) shows the LLM10 taxonomy is broader than rate-limit +
  budget alone.
- **Options considered:** (a) **token-bucket (Spring Cloud Gateway `RequestRateLimiter` / Bucket4j on Redis)
  for rate + Redis daily counters for budget**, plus **per-request input-size validation + max-output-token
  caps + timeouts + a cost-spike anomaly alert**; (b) fixed-window counters (bursty at edges); (c) in-memory
  limits (wrong with >1 instance).
- **Decision:** **(a)** — distributed, restart-safe, with the full LLM10 surface (input/output caps, throttling,
  anomaly detection) folded in.
- **Rationale:** idiomatic and production-shaped; covers the whole LLM10 surface, not just rate + budget.
- **Consequences:** Redis atomic-op care for correctness; budget = pre-request estimate + post-request
  accounting; the anomaly alert surfaces on the Grafana dashboard.
- **Implementation note (2026-06-17, P3 task 6):** rate limit = a hand-rolled **atomic Lua token-bucket**
  on the shared `JedisPooled` (`RedisRateLimiter`, key `atlas:ratelimit:<user>`, capacity = `requests-per-min`,
  refill-on-read) → over-quota `429`. Budget = `RedisBudgetGuard` daily counter `atlas:budget:<user>:<yyyymmdd>`
  (UTC, ~2-day TTL), pre-check `wouldExceed` → `402`, post-`record` increment. Input-size cap (`RequestLimits`,
  deterministic ~4-chars/token estimate) → `413`; max-output-token cap forwarded as `X-Atlas-Max-Output-Tokens`
  and applied in rag-engine via `ChatOptions.maxTokens`. Rate-limit + budget are independently toggleable
  (`ATLAS_RATELIMIT_ENABLED`/`ATLAS_BUDGET_ENABLED`) so the gateway runs Redis-free when off. **Token-source
  note:** budget cost is computed from a **gateway-side token estimate** (query length + worst-case output for
  the pre-check; answer length for accounting) — **task 8 swaps in real token usage** surfaced from rag-engine
  `ChatResponse` metadata, where the cost dashboard needs it. The **cost-spike anomaly alert** is a Grafana
  panel → **deferred to task 8** (metering/dashboard). Enforcement proven by `RedisRateLimiterIT` /
  `RedisBudgetGuardIT` (real Redis) + controller tests (429/402/413).

### ADR-0037 — PII egress redaction + output handling (LLM02/LLM05)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P3 · **Spec:** `P3_SPEC.md` §3 (D-P3-4), §8 (G-P3-5)
- **Context:** Financial/compliance data must not leak through prompts/responses (**LLM02**), and model output
  must be sanitized at egress (**LLM05**). Finance-PII (account #s, SSN/TIN, passport, DOB, restricted-doc
  names) is a known, bounded set.
- **Options considered:** (a) **hybrid** — a deterministic Java redactor + output sanitizer on the hot path,
  with **Microsoft Presidio + LLM Guard** as a periodic off-path deep-scan; (b) Presidio sidecar **inline** on
  every request (best recall, but a Python hop + latency + non-determinism on the hot path); (c) Java-only
  deterministic (fastest, narrower recall).
- **Decision:** **(a)** — deterministic Java redaction + sanitization inline; Presidio + LLM Guard off-path
  periodic deep-scan, with findings distilled back into the hot-path rules.
- **Rationale:** keeps the hot path fast and the CI gate deterministic/cassette-friendly while gaining NER
  breadth off-path; mirrors the P2 fixture-gate + Promptfoo-sweep split (ADR-0031).
- **Consequences:** redaction events traced **metadata-only** (counts/types, never the PII — consistent with
  ADR-0030); a second off-path service when Presidio/LLM Guard is enabled; PII-egress + output-handling are
  P3 hard gates.
- **Implementation note (2026-06-17, P3 task 7):** deterministic `PiiRedactor` masks structured finance-PII
  by regex (**SSN/TIN** `\d{3}-\d{2}-\d{4}`, **passport** `[A-Z]\d{7}`, **account #** `\d{8,}`, **DOB** dates)
  + a configurable literal **name-denylist** (`ATLAS_PII_NAME_DENYLIST`) for restricted entities/names, masking
  each as `[REDACTED:TYPE]` with metadata-only counts. `OutputSanitizer` (LLM05) strips
  `<script>/<style>/<iframe>`-class markup + `javascript:` URIs + `on*` handlers, then HTML-escapes residual
  angle brackets. Both run inline at **egress** on the `answer` + citation `snippet`s of **both** the fresh and
  cache-hit paths (the cache stores the RAW answer; redaction is applied per-read), and `PiiRedactor` also runs
  at **ingress** on the prompt. Response gains the §2.3 `redaction` section `{applied, counts}`. **Hard gates
  proven:** `PiiEgressGateTest` (the P1 `answerMustNotContain` strings never survive) + the output-handling
  test (0 unsafe payloads). **Denylist note:** deterministic name redaction needs a configured denylist
  (default empty; seeded in tests with the restricted entities from P1's `expectations.json`); NER breadth for
  *unknown* free-text names is the **off-path Presidio + LLM Guard deep-scan (task 9, deferred)** — the honest
  hybrid of this ADR.
- **Task 9 status (2026-06-17): deferred, Option B (owner-confirmed).** The off-path Presidio/LLM Guard NER
  deep-scan is **not implemented** in this P3 pass — it is optional (§5 task 9 "conditional"), off the hot path,
  and gates nothing. Env-gated/off by default (`ATLAS_PII_DEEPSCAN_ENABLED=false`); the hot-path
  `ATLAS_PII_NAME_DENYLIST` is the manual channel for distilled findings. See P3_SPEC §6.1.

### ADR-0036 — Clearance-partitioned, poison-resistant semantic cache (Redis Stack)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P3 · **Spec:** `P3_SPEC.md` §3 (D-P3-2), §8 (G-P3-4)
- **Context:** Semantic caching cuts cost/latency (30–70% in 2026 literature), but a naive cache **leaks across
  clearances** (R1) and is vulnerable to **semantic-cache poisoning / collision** attacks (NDSS 2026;
  multi-tenant RAG "response-cache cross-talk").
- **Options considered:** (a) **Redis Stack vector search**; (b) reuse pgvector (one vector engine, but mixes
  ephemeral TTL cache with the system-of-record DB + hand-rolled expiry); (c) Caffeine exact-match (not
  *semantic* — fails the phase intent).
- **Decision:** **(a)** Redis Stack vector search with **clearance-partitioned keys**, **trusted-write only**
  (cache only answers that passed RBAC + the P1 guardrail + grounding), an **eval-calibrated conservative
  similarity threshold**, **optional re-grounding on hit**, and **corpus-version invalidation**.
- **Rationale:** native TTL fits a cache; partitioning makes cross-clearance hits structurally impossible;
  trusted-write + a calibrated threshold resist poisoning/collision — the cache can never hold an answer the
  live path would have refused.
- **Consequences:** Redis Stack image (ARM-supported) replaces vanilla Redis; **cross-clearance** and
  **poisoning/collision** are P3 hard gates; the similarity threshold is recorded in `gateway-baseline.json`.
- **Implementation note (2026-06-17, P3 task 5):** hand-rolled on **Jedis + RediSearch** (`RedisSemanticCache`)
  for full control over the structural invariant, native TTL, and trusted-write. Keys are
  `atlas:cache:<clearance>:<corpusVersion>:<uuid>`; every KNN query carries a **mandatory**
  `@clearance:{<caller>} @corpus_version:{<ver>}` pre-filter built from the *verified* clearance, plus a
  read-time `entry.clearance == caller` assertion — so a cross-clearance hit is impossible by construction
  (proven by `RedisSemanticCacheIT` against real Redis Stack: **0 cross-clearance hits**). HNSW/COSINE index
  (`similarity = 1 − distance`), conservative threshold `ATLAS_CACHE_SIM_THRESHOLD=0.95` (calibrated in task
  10 → `gateway-baseline.json`), **native per-key EXPIRE** TTL, query embedding via Spring AI Ollama
  `nomic-embed-text` on the hot path (abstracted behind `QueryEmbedder` so gate ITs are model-free). The
  cache lookup is **before routing** (a hit skips the model call); writes happen only after a 2xx rag-engine
  answer (**trusted-write**: the Gateway only caches RBAC+guardrail+grounding-passed answers). Redis image
  swapped to `redis/redis-stack-server:7.4.0-v3` (multi-arch, digest-pinned); when `atlas.cache.enabled=false`
  a `NoOpSemanticCache` is wired and the gateway boots without Redis. **Partial:** `corpus_version` is a
  configurable `ATLAS_CACHE_CORPUS_VERSION` bumped manually on re-ingest; auto-deriving it from rag-engine is
  a follow-up. `reground-on-hit` is bound but inert (reserved).

### ADR-0035 — Cost-aware model router (declarative rules + model-cascade)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P3 · **Spec:** `P3_SPEC.md` §3 (D-P3-3), §8 (G-P3-3)
- **Context:** Route each request to the cheapest adequate model — small/quantized by default (ADR-0005),
  escalate only by policy, and **never below the P2 eval floor** (R2).
- **Options considered:** (a) **declarative rules + model-cascade** (escalate when the tier-1 answer fails the
  cheap inline `FactCheckingEvaluator`/low-confidence check); (b) heuristic complexity classifier; (c)
  LLM-as-router (adds a model call + cost + non-determinism to every request).
- **Decision:** **(a)** — deterministic rules + cascade; selectable tiers are limited to **eval-passing**
  models; the frontier tier is budget-gated and off by default. Learned routers (RouteLLM / `semantic-router`)
  are explicit future work.
- **Rationale:** transparent, CI-deterministic, and dashboard-friendly; the cascade is a stronger-yet-still
  deterministic middle ground than pure static rules; the cost-delta report (ADR-0040) proves it.
- **Consequences:** router escalation thresholds are eval-calibrated and recorded; `never_below_eval_floor` is
  enforced and tested; learned routing deferred.
- **Implementation note (2026-06-17, P3 task 4):** the router lives in the Gateway (`ModelRouter` /
  `RoutingPolicy`-via-`RoutingProperties` / `CostTable`); `rag-engine`'s `ModelTierResolver` maps the
  forwarded `X-Atlas-Model-Tier` → a per-request **portable `ChatOptions.model(...)`** override (`tier1-small`
  = the default ChatModel, no override; unknown/disabled-frontier → fail-safe to default). Implemented now:
  the **pre-call deterministic rules** the Gateway can evaluate before calling rag-engine — default = tier1-small,
  escalate to tier2-mid on `X-Atlas-Quality: high` or an estimated `query_tokens > ATLAS_ROUTER_ESCALATE_QUERY_TOKENS`
  (deterministic ~4-chars/token estimate); frontier is reserved and **never auto-selected**; the eval-floor
  guard restricts selection to the approved/selectable set. **Deferred to a follow-up (owner-confirmed
  2026-06-17; tracked in P3_SPEC §6.1):** the **model-cascade** (escalate when the tier-1 answer fails the inline
  `FactCheckingEvaluator`) and the **`retrieved_context_tokens > N`** rule — both are *post-generation/retrieval*
  signals that require `rag-engine` to return a confidence/context signal in the response (a cross-cutting change
  best coordinated with the eval-through-Gateway work, task 10). `ATLAS_ROUTER_CASCADE_ENABLED` is bound but not
  yet acted on.

### ADR-0034 — Simulated-IdP verified-clearance trust boundary (supersedes ADR-0016)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P3 · **Spec:** `P3_SPEC.md` §3 (D-P3-5) · **Realizes:** ADR-0003 · **Supersedes:** ADR-0016
- **Context:** P3 stands up the simulated IdP (ADR-0003). The Gateway becomes the **single trust boundary** and
  must convey a **cryptographically verifiable** clearance to `rag-engine`, retiring the P1 client-trusted
  `X-Atlas-Clearance` shim (ADR-0016).
- **Options considered:** (a) **Gateway-signed internal header / short-lived internal token** that `rag-engine`
  independently validates; (b) **JWT passthrough** (forward the client JWT; `rag-engine` validates it directly —
  spreads IdP-verification into a second service); (c) **network-trust only** (a single misconfig re-opens the
  LLM08 leak).
- **Decision:** **(a)** — the simulated IdP (`POST /v1/auth/token`) mints a signed JWT clearance claim; the
  Gateway validates signature/`exp`/`iss`, resolves clearance, and **re-asserts a verified clearance to
  `rag-engine` as a signed internal value the engine independently validates**; client-set `X-Atlas-Clearance`
  is **ignored** on the Gateway path.
- **Rationale:** keeps the Gateway the single trust boundary while letting `rag-engine` independently verify
  (defense-in-depth; matches the P4 "tools re-check clearance" ethos) and realizes the verifiable claim ADR-0003
  requires.
- **Consequences:** **supersedes ADR-0016** (the shim is retired on the Gateway path; permitted only for
  `local`/test direct-to-`rag-engine` calls); a signing key + an internal shared secret are env-managed (no
  secrets in code, LLM03); auth failure → `401`. The P1 abstract `Clearance` seam means the swap touches only
  the resolver.
- **Implementation note (2026-06-17, P3 task 2):** both hops are **HS256 JWTs via Nimbus JOSE+JWT** (used
  directly — no Spring Security OAuth2 starter — so the trust boundary is an explicit, unit-tested `OncePerRequestFilter`).
  (1) **Client token:** signed with `ATLAS_IDP_SIGNING_KEY`, claims `{sub, clearance, iss, iat, exp, jti}`,
  TTL `ATLAS_IDP_TOKEN_TTL_SECONDS`; validated by the Gateway's `JwtClearanceFilter` on every route except
  `/v1/auth/**` + `/actuator/**`. (2) **Internal hop:** the Gateway's `DownstreamClearanceSigner` mints a
  **short-lived (~60 s)** JWT signed with the *separate* `ATLAS_GATEWAY_INTERNAL_SECRET`, issuer `atlas-gateway`,
  carried in header **`X-Atlas-Internal-Clearance`**; `rag-engine`'s `DownstreamClearanceVerifier` +
  `DownstreamClearanceFilter` re-verify signature/`exp`/`iss` and, when valid, the `QueryController` uses that
  clearance and **ignores** the `X-Atlas-Clearance` shim (proven by `QueryControllerTest`; P1 D4
  `RbacNegativeAccessIT` 24/24 still green). **Key derivation:** HS256 needs ≥256-bit keys, so both modules
  derive the MAC key as **`SHA-256(secret)`** (identical `SecurityKeys.deriveHs256` logic on each side) — any
  operator secret length works, incl. the `.env.example` placeholder and a real `openssl rand -base64 32` key.
  Nimbus is **not** managed by the Boot 3.4 BOM, so it is pinned in the parent (`nimbus-jose-jwt 9.48`). The
  signer is wired now; it is attached to the proxied request in P3 task 3.

### ADR-0033 — API Gateway framework (Spring Cloud Gateway Server WebMVC)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P3 · **Spec:** `P3_SPEC.md` §3 (D-P3-1), §8.1 (G-P3-1)
- **Context:** P3 needs a single front door (routing, filters, rate-limit, circuit breaker). Spring Cloud
  Gateway on **Spring Boot 4 / Framework 7** ships **both** a reactive server *and* a non-reactive
  `gateway-server-webmvc` server.
- **Options considered:** (a) **`gateway-server-webmvc`** (blocking, Servlet — matches the `rag-engine`/Spring AI
  idiom); (b) reactive WebFlux server (idiomatic reactive, but Mono/Flux in front of a blocking stack); (c)
  Nginx/Envoy + a thin Spring policy service (pushes the cost-router logic — the whole point — out of Spring).
- **Decision:** **(a) `spring-cloud-starter-gateway-server-webmvc`.** Reactive (b) was first confirmed, then
  **reversed after June-2026 research (§8.1)**: the Gateway proxies rather than streams model tokens, so
  reactive's benefit is marginal while its complexity cost is real for a blocking stack + a solo Java engineer.
- **Rationale:** lower-risk and idiom-matched, while still demonstrating the "Spring Cloud Gateway" skill
  (routes, filters, `RequestRateLimiter`, Resilience4j).
- **Consequences:** reactive is reconsidered only if/when the Gateway must itself stream model tokens (a P5/UX
  concern, not P3).
- **Implementation note (2026-06-17, P3 task 1):** the repo is on **Spring Boot 3.4.7 / Spring AI 1.0.0**, not
  Boot 4, so the WebMVC gateway ships in the **Spring Cloud 2024.0.x** train where the starter artifact is
  **`spring-cloud-starter-gateway-mvc`** (the `-gateway-server-webmvc` id is the Boot 4 / Spring Cloud 2025+
  rename the spec §8.1 refers to). Pinned **`spring-cloud.version=2024.0.1`** in the parent BOM (the 3.4.x
  compatibility verifier matches any `3.4.patch`, incl. 3.4.7 — build verified green). The decision (WebMVC,
  blocking, Servlet) is unchanged; only the coordinate name/version is train-specific. The compose `gateway`
  service is gated behind the **`app` Compose profile** (off by default) so `make up` still works from a fresh
  clone without a pre-built jar; in dev the gateway runs on the host (`mvn spring-boot:run`) and is scraped via
  `host.docker.internal:${GATEWAY_PORT}`, mirroring the established `rag-engine` pattern.

### ADR-0032 — Katzilla external primary-source data (post-P5 backlog)
- **Date:** 2026-06-14 · **Status:** Proposed · **Phase:** P6 (post-P5) · **Spec:** `ROADMAP.md` §8
- **Context:** Katzilla (katzilla.dev) is a hosted, **MCP-native** API wrapping 30+ US/intl government datasets
  (SEC, FDA, Federal Register, Congress, court opinions, clinical trials…) with a machine-readable **citation +
  provenance** (`source / license / retrieved_at / data_hash`) on every response. Evaluated for fit with the
  Atlas vision at the project owner's request.
- **Options considered:** (a) ignore; (b) adopt as a **core** data source; (c) adopt **post-P5 as an optional,
  env-gated third-party MCP tool the agent consumes** (public-data demo enrichment only).
- **Decision:** **(c) Proposed** — a post-P5 optional integration; explicitly **not** a P0–P5 dependency.
- **Rationale:** Aligns with Atlas's citation/provenance ethos and would demonstrate **MCP client multi-server
  composition** (consuming a third-party MCP server). But it is **public** data (no RBAC dimension — cannot
  touch the permission-aware moat), a **third-party SaaS** (conflicts with Atlas's self-hosted / no-egress /
  cost-discipline posture), and a young vendor; it must stay complementary and never displace the self-built
  core (permission-aware RBAC RAG + Atlas's own governed MCP tools).
- **Consequences:** If implemented, it is **env-gated** (`KATZILLA_API_KEY`, off by default) so the core system
  still runs fully self-hosted from a fresh clone with it absent; used only for the public-data side of a demo
  (e.g. cite a real Federal Register / FDA item alongside private AML findings). Revisit with a superseding
  **Accepted** ADR when a P6 lane is actually scoped.

### ADR-0031 — Adversarial breadth: fixtures gate + Promptfoo OWASP sweep
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §3 (D-P2-11), §8 (E4)
- **Context:** P2's hand-rolled adversarial scorer covered only the four P1 poisoned fixtures — narrow versus
  the breadth a compliance copilot's "red-team safety evals" claim implies. June-2026 research confirms
  **Promptfoo** as the standard CI red-team framework (OWASP LLM Top 10 plugins, 50+ vuln categories, Ollama
  targets); Garak/PyRIT/DeepTeam are alternatives.
- **Options considered:** (a) **both, split by lane** — fixtures as the deterministic 0-tolerance PR gate +
  a **Promptfoo OWASP sweep** on the periodic live lane; (b) fixtures only (deterministic but narrow); (c)
  Promptfoo as the gate (generative/non-deterministic + needs a live model → can't be the per-PR gate).
- **Decision:** **(a)** — keep the hand-authored fixtures (`poisoned/expectations.json` + `negative_access.json`)
  as the merge gate; add a Promptfoo sweep targeting `/v1/query` at low clearance in the live-calibration lane;
  distil new findings into committed fixtures.
- **Rationale:** Deterministic gate keeps `main` safe; the sweep gives real OWASP breadth + a renewable source
  of regression fixtures; mirrors the cassette/live split (ADR-0021).
- **Consequences:** Promptfoo runs only when the GPU is up (calibration lane), never the per-PR gate; findings
  become committed fixtures so coverage compounds over time.
- **Implementation note (Task 7, 2026-06-14):** The deterministic PR-gate scorer (`metrics/adversarial_scorer.py`)
  is shipped: binary `score_case`/`score_adversarial` over `/v1/query` responses with three checks —
  leaked-string (answer vs `must_not_contain`), above-clearance (contexts[] + citations[] vs `must_not_cite_above`),
  forbidden-doc (citations[].docId vs `negative_access` forbidden ids); **0-tolerance** (`passed` only at
  pass_rate 1.0; a missing response is a failure). 12 unit tests; the Promptfoo live sweep is wired in Task 9.
- **CI wiring (Task 9, 2026-06-14):** the deterministic scorer runs in the per-PR `evals-gate` (replay). The
  **Promptfoo OWASP sweep** (`evals/promptfoo/promptfooconfig.yaml`, plugins `owasp:llm`/`pii`/`rbac`/`bola`/
  `prompt-extraction` + jailbreak/injection strategies) targets `/v1/query` at `public` clearance and runs only
  in the manual `calibration.yml` lane (GPU up), report-only — findings distil into committed fixtures.

### ADR-0030 — Trace content-capture & redaction policy (LLM02/LLM07)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §2.4, §3 (D-P2-10), §8 (E1)
- **Context:** OTel GenAI conventions capture prompt/response **content as events**. In a clearance/PII domain
  that would push **above-clearance chunk text and PII into Langfuse traces** — the observability plane undoing
  the RBAC the rest of Atlas enforces (OWASP LLM02 sensitive-info disclosure, LLM07 system-prompt leakage).
  Surfaced by the P2 web-research pass.
- **Options considered:** (a) **metadata-only by default; full content opt-in + redaction-filtered, dev-only**;
  (b) capture full content by default (richest, but leaks); (c) never capture content (safest, least debuggable).
- **Decision:** **(a)** — `ATLAS_TRACE_CONTENT=off` by default (spans carry ids/clearance/model/token/latency +
  retrieved-chunk *ids*, never their text); `=full` enables **redacted** prompt/response events for **local dev
  only**, never a shared/prod stack.
- **Rationale:** The only option consistent with the compliance/RBAC vision; OTel deliberately models content as
  opt-in events for exactly this reason.
- **Consequences:** A redaction IT asserts no above-clearance text / PII (the `poisoned/expectations.json`
  strings) reaches traces; GenAI semconv is **`Development`-status in 2026**, so the emitted version is pinned
  via `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` (recorded in `baseline.json`).
- **Implementation note (Task 3, 2026-06-14):** Instrumented via the **Micrometer Observation API**
  (not hand-rolled OTel spans) so Spring AI's `ChatModel`/`EmbeddingModel` auto-emit `gen_ai.*` spans and nest
  under a root `atlas.query` span carrying `atlas.request_id`/`atlas.clearance`; child `retrieve` +
  `guardrail.scan` spans carry stage stats. `QueryTracer` records the required `gen_ai.client.operation.duration`
  Timer + `gen_ai.client.token.usage` summary. Content capture is OFF by default; `RedactionFilter` masks
  structured PII (SSN/passport/account/email) + a configurable deny-list when `=full`. Export to Langfuse is
  **opt-in** (`OTEL_TRACES_EXPORT_ENABLED`, Micrometer→OTel bridge + OTLP) so tests/CI never reach Langfuse;
  spans are asserted offline via an in-memory observation recorder. Verified: 3 tracing/redaction tests +
  full rag-engine `verify` green (incl. P1 D4/D7 hard gates).

### ADR-0029 — Automated fail-safe GPU lifecycle (pause/resume)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §2.6, §3 (D-P2-9)
- **Context:** The eval/calibration lanes need the Cloud Ollama GPU live, then paused (ADR-0006 cost
  discipline). Manual pause/resume is fail-safe-*off* (forget → silent burn).
- **Options considered:** (a) **automated, fail-safe `infra/gpu` helper** (provider driver: JarvisLabs default,
  E2E fallback) — resume → health-poll `/api/tags` → discover the fresh `OLLAMA_BASE_URL` → run → **guaranteed
  pause (`finally`/trap) + idle-timeout watchdog**; (b) manual only; (c) defer to P3.
- **Decision:** **(a)**, with **guaranteed-pause as a hard condition** (automation that can resume must never be
  able to leave the GPU running). Manual remains the documented fallback (RUNBOOK §2.4).
- **Rationale:** Turns cost discipline into enforced behaviour, not a thing you remember; a tangible "cost as a
  feature" artifact. It is **off the eval-gate critical path** (the gate is offline/cassette), so it never risks
  the merge gate.
- **Consequences:** `GPU_API_KEY` is a managed secret (OWASP LLM03) behind the driver; `make gpu-up/gpu-down`;
  wired into the live-calibration job; provider coupling abstracted by the driver (E2E fallback).
- **Implementation note (Task 2, 2026-06-14):** stdlib-only Python package `infra/gpu/atlas_gpu` (no runtime
  deps, so the pause guarantee never hangs on a fragile CI env). `GpuSession` pauses in `__exit__` **and** in
  `__enter__` on a failed resume/health-poll (TDD + the live run caught that `__enter__` raising would otherwise
  leak a running GPU). `Watchdog` is the detached second net. 24 unit tests assert the guaranteed-pause invariant
  via an injectable transport.
- **Live verification (Task 2, 2026-06-14):** the JarvisLabs driver was implemented against the **real backend
  API** (not a placeholder seam) and a **full resume→health-poll→discover→run→guaranteed-pause cycle was run
  against a live instance** (confirmed Paused afterwards = billing stopped). The live run caught three bugs that
  wrong-assumption unit tests had hidden: (1) the `users/fetch/{id}` route 404s — use the list route; (2)
  `resume()` was outside the pause-guard; (3) **`machine_id` changes on every resume** — the driver now adopts
  the new id from the resume response and falls back to the sole instance if the configured id has drifted.
  Region-aware base URL (`backendprod`/`backendn`/`backendeu`); pause = `misc/pause?machine_id=` (success is the
  string `"True"`); resume = `templates/{framework}/resume`. The `E2EProvider` generic seam keeps its
  calibration-time TODO; JarvisLabs is the verified default.

### ADR-0028 — Golden eval set size & composition
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §3 (D-P2-8)
- **Context:** The golden set must give meaningful signal yet stay cheap/fast on the dev GPU, and stay coherent
  with the committed corpus (12 FinanceBench snippets + Layer-2 overlay).
- **Options considered:** (a) **~25–40 tuples** (~15 FinanceBench-seeded Layer-1 + ~10–15 authored Layer-2
  Northwind/AML + the 6 negative-access cases); (b) 100+ FinanceBench tuples (stronger stats, but most
  reference filings outside our 12-snippet subset → corpus expansion / ADR-0020 change); (c) minimal (~10).
- **Decision:** **(a)**, sized to the **committed corpus** (only FinanceBench rows whose evidence maps to our 12
  snippets qualify).
- **Rationale:** Meaningful coverage of both layers + the Priya story, cheap to run, keeps P1↔P2 coherent;
  ground truth is authoritative (FinanceBench tuples) or authored (Layer-2).
- **Consequences:** `evals/data/golden.jsonl` committed/versioned; growing beyond the subset requires expanding
  Layer-1 (new ADR superseding 0020).
- **Implementation note (Task 5, 2026-06-14):** Shipped **22 golden tuples** = 12 Layer-1 (authoritative
  FinanceBench `question`/`answer` pulled for each committed `financebench_id`, clearance per the manifest) +
  10 authored Layer-2 Northwind/AML tuples. The 6 negative-access cases are carried in **`adversarial.jsonl`**
  (10 cases: 4 injection/jailbreak/system-leak + 6 access-bypass) as the access-bypass lane, **referencing** the
  P1 fixtures (`poisoned/expectations.json`, `negative_access.json`) rather than duplicating them so P1↔P2 cannot
  drift. Loaders validate every `expected_source_docs`/fixture reference resolves to a real corpus doc; 12 pytest
  cases green. (Used the cheaper end of the ~25–40 band — 22+10 — sized to the 12-snippet corpus.)

### ADR-0027 — Cross-encoder reranker (eval-gated A/B)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §3 (D-P2-7) · **Refines:** ADR-0014
- **Context:** ADR-0014 shipped P1 with an RRF-pass-through `Reranker` seam and deferred a real reranker to P2
  "where evals can prove it earns its cost."
- **Options considered:** (a) **implement a cross-encoder reranker behind the existing seam, A/B via the
  harness, keep only if context-precision/relevancy lift justifies the latency/infra**; (b) keep deferring
  (RRF-only); (c) LLM-as-reranker via Ollama (latency/cost, less consistent).
- **Decision:** **(a)** — implement + eval-gate; if the A/B shows no gain, log an ADR re-deferring it (the
  harness becomes the evidence). Same eval-gated treatment for the `websearch_to_tsquery` sparse-semantics fix
  flagged in ADR-0018.
- **Rationale:** P2 is exactly where the reranker's value can be measured rather than asserted.
- **Consequences:** Additive behind the `Reranker` seam; the **P1 D4/D7 hard gates must stay green** if
  retrieval changes; keep/re-defer is recorded either way.
- **Outcome (Task 10, 2026-06-14) — RE-DEFERRED on the evidence.** Implemented `LlmReranker` (LLM-as-reranker
  via Ollama, option c — a true cross-encoder would need a new GPU sidecar; out of proportion for a 24-chunk
  corpus) + `websearch_to_tsquery`, both flag-gated (`atlas.retrieval.reranker`, `…sparse-query`, default OFF).
  Live A/B (qwen2.5:3b + llama3.1:8b judge, 22 tuples) RRF+plainto **vs** LLM-rerank+websearch:

  | metric | baseline | variant | Δ |
  |---|---|---|---|
  | faithfulness *(gating)* | 0.799 | 0.770 | **−0.029** |
  | answer_relevancy *(gating)* | 0.698 | 0.772 | +0.074 |
  | context_precision *(report)* | 0.834 | 0.905 | +0.071 |
  | context_recall *(gating)* | 0.781 | 0.737 | **−0.044** |

  Mixed: precision/relevancy up, but **two of the three gating metrics (faithfulness, recall) regress**, plus a
  per-query LLM call. Not the "clear, broad lift" the keep-criterion requires. **Decision: keep RRF + plainto as
  the defaults; ship the reranker/websearch capability flag-gated OFF (unit-tested), re-evaluate when the corpus
  grows (the A/B is one `atlas_evals.ab` run away).** The committed baseline/cassettes are unchanged. This is the
  spec's anticipated evidence-based re-deferral — the harness, not opinion, made the call.

### ADR-0026 — Spring AI inline evaluators as a cheap pre-filter
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §3 (D-P2-6)
- **Context:** Spring AI ships `RelevancyEvaluator` / `FactCheckingEvaluator`; using them is idiomatic (ROADMAP
  §6 G7), but they run on the small dev model and shouldn't be the authority.
- **Options considered:** (a) **inline pre-filter / trace annotation, NOT the gate**; (b) make them the gate
  (ties the merge gate to the small model, weakly duplicates RAGAS); (c) skip them.
- **Decision:** **(a)** — run inline as a free per-request signal annotated onto the trace; the **Python RAGAS
  run remains the authoritative gate**.
- **Rationale:** Demonstrates idiomatic Spring AI + gives a cheap "smoke" signal without the full RAGAS cost,
  while keeping the gate in the dedicated harness.
- **Consequences:** Informational only; never blocks merge on its own.
- **Implementation note (Task 11, 2026-06-14):** `eval/InlineEvaluators` wraps Spring AI
  `RelevancyEvaluator` + `FactCheckingEvaluator` (`org.springframework.ai.chat.evaluation`), invoked per
  `/v1/query` in `QueryService` to **annotate the root `atlas.query` span** (`eval.relevancy.pass/score`,
  `eval.factcheck.pass/score`). **OFF by default** (`atlas.eval.inline-enabled`, env
  `ATLAS_EVAL_INLINE_ENABLED`) because each is an extra LLM call — a deliberate cost-discipline choice (the
  spec framed them as "free", but on a metered GPU they are not). **Fail-soft**: any evaluator error is logged
  and the query proceeds. 2 unit tests; full context boots with the evaluators wired.

### ADR-0025 — Self-hosted Langfuse (observability)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §3 (D-P2-5)
- **Context:** P2 needs an LLM-observability surface that ingests OTel `gen_ai.*` and manages eval datasets.
- **Options considered:** (a) **self-hosted Langfuse via Docker Compose**; (b) Langfuse Cloud free tier (less
  infra, but ships trace data off-box + needs an account/key).
- **Decision:** **(a)** — self-hosted, ingesting OTel over OTLP at `/api/public/otel`.
- **Rationale:** Keeps the all-local "runs from a fresh clone" promise and the compliance/no-egress story clean;
  Langfuse remains the 2026 OSS default and natively supports the GenAI conventions.
- **Consequences:** Heavier `make -C infra up` (Langfuse + its Postgres/ClickHouse); part of the local stack.
- **Implementation note (Task 1, 2026-06-14):** Langfuse v3 requires Postgres + Redis + ClickHouse + S3.
  Footprint sub-decision (owner-confirmed): **reuse `atlas-postgres` (separate `langfuse` db) + `atlas-redis`,
  add only ClickHouse + MinIO** — vs a fully isolated 4-container stack or EOL-track Langfuse v2. Langfuse is
  **headless-bootstrapped** (`LANGFUSE_INIT_*`) so the `.env` API keys are pre-wired on a fresh clone. Prometheus
  + Grafana provisioning is **seeded into named volumes** (Snap-Docker: no `/data` bind mounts).

### ADR-0024 — Eval metric set & gating thresholds
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §3 (D-P2-4), §4.4, §8 (E3)
- **Context:** P1's manual quality baseline must become a merge gate without a flaky gate before the baseline is
  calibrated on a (small) self-hosted judge.
- **Options considered:** (a) **gate faithfulness + answer_relevancy + context_recall (floors) + a no-regression
  band on all four; precision/correctness report-only**; (b) hard floors on all four day one (flaky risk); (c)
  gate only adversarial + faithfulness.
- **Decision:** **(a)**. Add **context entity recall** (finance/AML entity grounding), **citation correctness**
  (vision's "answers with citations"), and **noise sensitivity** as **report-only** signals to phase in. The
  **adversarial/red-team set is always a 100%-pass hard gate** regardless.
- **Rationale:** Gate the metrics that most directly encode R1/R2 (grounding, recall, no-cross-clearance-leak);
  phase in precision/entity/citation once the baseline is stable; floors set from the first calibrated run
  **minus a margin**, with `max_regression` catching slow slides.
- **Consequences:** Thresholds written into `evals/data/baseline.json` from the first calibrated run; judge runs
  at **temperature 0**, pinned, recorded; entity-recall/citation must be calibrated before any promotion to a gate.
- **Implementation note (Task 8, 2026-06-14):** First calibrated `baseline.json` from a live run (qwen2.5:3b RAG
  + llama3.1:8b judge @ temp 0, RAGAS 0.2.15, 22 golden tuples): **faithfulness 0.799 (floor 0.749), answer_relevancy
  0.698 (floor 0.648), context_recall 0.781 (floor 0.711)** gating; context_precision 0.834, context_entity_recall
  0.074, citation_correctness 1.0 report-only. Floors = recorded − margin (0.05/0.05/0.07). **Adversarial gate:
  pass-rate 1.000 (0 violations)** across the 10 red-team cases. `noise_sensitivity` dropped this run (RAGAS
  per-metric timeouts — report-only; raise the run-config timeout next calibration). Gate verified green in pure
  replay with RAGAS **not** installed.

### ADR-0023 — Eval-context exposure on /v1/query (`includeContexts`)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §2.4, §3 (D-P2-3)
- **Context:** RAGAS faithfulness/context-precision/recall need the **actual retrieved context text**; the P1
  `/v1/query` response only returns truncated citation snippets (non-cited-but-retrieved context is invisible).
- **Options considered:** (a) **opt-in `includeContexts` field** returning the full reranked, RBAC-filtered
  context set; (b) reconstruct from Langfuse trace payloads (brittle, couples evals to trace internals); (c) a
  separate `/v1/eval/retrieve` endpoint (duplicates the retrieval path).
- **Decision:** **(a)** — default-off `includeContexts=true` returns `contexts[]` of full chunk text, still
  **RBAC-filtered** (`<= caller clearance`).
- **Rationale:** One small, RBAC-safe field; evals exercise the **single** retrieval path exactly as prod does.
- **Consequences:** The negative-access hard gate is **extended to `contexts[]`** (closing the
  "leaked-into-context-but-not-cited" hole); default false leaves normal callers/UI unaffected.
- **Implementation note (Task 4, 2026-06-14):** `contexts[]` exposes the **post-guardrail safe sources**
  (exactly what the model saw), as `{chunkId, documentId, clearance, text}`; omitted from the response unless
  `includeContexts=true` (`@JsonInclude(NON_NULL)`), so the default contract is byte-for-byte unchanged. The D4
  `RbacNegativeAccessIT` now runs a `:: contexts` case per golden tuple through `QueryService.answer()` (18→24
  cases); full `mvn verify` green incl. D4/D7.

### ADR-0022 — LLM-as-judge model (cross-family `llama3.1:8b-instruct`)
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §2.6, §3 (D-P2-2)
- **Context:** RAGAS metrics are LLM-judge-dependent; the judge must be reliable, cheap enough to run routinely,
  and **independent** of the subject under test. The RAG subject is `qwen2.5:3b-instruct` (ADR-0005).
- **Options considered:** (a) **`llama3.1:8b-instruct` — a cross-family judge** (reduces self-enhancement/family
  bias); (b) `qwen2.5:7b-instruct` (same family → self-preference bias risk); (c) reserved cloud-frontier judge
  (`gpt-4o`, swappable) for **periodic** calibration; (d) reuse the 3B dev model (noisy *and* same-family).
- **Decision:** **(a) routine + (c) periodic.** Routine judge `llama3.1:8b-instruct` on the same Ollama GPU at
  **temperature 0**, **pinned + recorded in `baseline.json`**; frontier judge for occasional authoritative
  calibration only.
- **Rationale:** A cross-family 8B judge is the sweet spot of independence, reliability, and self-hosted cost;
  pinning the judge means a metric move attributes to **the RAG**, not the judge; RAGAS 2026 guidance (temp 0,
  pin the judge, prefer a stronger judge than the subject) validates this.
- **Consequences:** ~+5 GB VRAM during eval runs (fits the L4/A5000, co-resident ≈ 8 GB); env
  `ATLAS_EVAL_JUDGE_MODEL`; swapping the judge requires a recalibration + a new ADR.
- **Implementation note (Task 6, 2026-06-14):** `RagasScorer` builds the judge as a
  `LangchainLLMWrapper(ChatOllama(..., temperature=0))` with `nomic-embed-text` embeddings, env-pinned
  (`ATLAS_EVAL_JUDGE_MODEL`, `ATLAS_EVAL_JUDGE_BASE_URL`→`OLLAMA_BASE_URL`); the judge model + RAGAS version are
  baked into each per-sample cassette key, so a judge change forces a re-record. RAGAS is a lazy dep (RECORD
  only); the actual judged numbers are produced in the Task 8 calibration session.
- **Tag correction (Task 8, 2026-06-14):** the published Ollama tag is **`llama3.1:8b`** (which *is* the instruct
  build); `llama3.1:8b-instruct` is **not** a real tag (`pull` 404s). `ATLAS_EVAL_JUDGE_MODEL` defaults to
  `llama3.1:8b` and the calibrated `baseline.json` pins it. Cross-family-judge rationale is unchanged.

### ADR-0021 — Eval LLM in CI: cassette-replay gate + live calibration
- **Date:** 2026-06-14 · **Status:** Accepted · **Phase:** P2 · **Spec:** P2_SPEC §2.5, §3 (D-P2-1)
- **Context:** The eval gate needs an LLM (RAG model **and** judge), but CI has **no GPU** and the remote Ollama
  is **paused-when-idle** (ADR-0006). A live call on every PR contradicts cost discipline and adds flakiness +
  a secret in CI.
- **Options considered:** (a) record/replay **cassettes** (deterministic, offline, free); (b) **live remote
  Ollama in CI** (realistic, but GPU-per-PR + secret); (c) **hybrid** — cassette-replay is the merge gate, a
  nightly/manual **live** job runs the full RAGAS and updates the baseline.
- **Decision:** **(c)** — cassette-replay PR gate + periodic live calibration.
- **Rationale:** The only option consistent with the laptop/GPU/cost constraints **and** a true CI merge gate:
  deterministic, cost-free PR gate; periodic live calibration keeps the numbers honest.
- **Consequences:** Cassette key = `hash(prompt + model + inputs)`; a **miss fails loudly** (never a silent live
  call); cassettes are refreshed whenever the prompt/model/corpus/golden set changes; the live lane uses the
  GPU helper (ADR-0029) and the Promptfoo sweep (ADR-0031).
- **Implementation note (Task 6, 2026-06-14):** `CassetteStore` (record/replay/off, sha256 keys, miss→
  `CassetteMiss`) cassettes **two boundaries**: the `/v1/query` RAG responses (`CassettingClient`, key includes a
  model/corpus fingerprint) and the RAGAS judge scores **per sample** (`RagasScorer`, key includes
  judge_model+ragas_version+answer+contexts+ground_truth). Per-sample score cassettes mean **REPLAY needs neither
  RAGAS nor a judge** — the merge gate just reads committed scores, keeping CI light; a changed RAG answer busts
  the key → loud re-record. The committed cassettes themselves are recorded live in Task 8.
- **CI wiring (Task 9, 2026-06-14):** `ci.yml` job **`evals-gate`** runs `python -m atlas_evals.gate` (cassette
  replay, no GPU, RAGAS not installed) and **blocks merge**. The live lane is a **manual-only**
  `workflow_dispatch` (`calibration.yml`, owner-confirmed — no cron): resume → pull judge → ingest → record →
  recalibrate → Promptfoo sweep → **guaranteed `gpu-down` in `if: always()`** → commit refreshed cassettes/baseline.
- **Hardening (post-merge, 2026-06-14):** (1) `main` **branch protection** now *requires* the eval-gate (+ Java/
  Python/secret/vuln/image) checks, so a red gate truly blocks merge (previously no protection existed). (2) The
  **RAG cassette key now includes a live hash of the rag-engine behaviour source** (`fingerprint.py`), so a
  prompt/retrieval change busts the cassette → loud miss → re-record, instead of the gate replaying stale
  answers. Both verified with negative tests (floor breach, injected leak, deleted cassette, behaviour-file edit).

### ADR-0020 — Layer-1 ingestion form: committed FinanceBench evidence snippets
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §5 (Task 2) ·
  **Refines:** ADR-0017 (FinanceBench subset), ADR-0004 (two-layer corpus)
- **Context:** ADR-0017 fixed the Layer-1 subset as "~10–15 FinanceBench docs pulled from HF at ingest."
  FinanceBench's source documents are **full 10-K/10-Q filings (100–200 pages each)**. Ingesting full
  filings means thousands of chunks, heavy embedding cost/time on the dev GPU, PDF parsing, and
  non-deterministic content for the Testcontainers ITs — at odds with the low-spec laptop + cost-discipline
  constraints (CLAUDE.md). The form of Layer-1 ("what is a document") was left open by the spec.
- **Options considered (owner-confirmed):** (a) **Commit FinanceBench `evidence_text` snippets** (~12 short
  docs tied to the 150 golden tuples) as the Layer-1 text — small, deterministic, version-controlled,
  eval-aligned, cheap to embed; (b) pull full filings from HF at ingest into a gitignored dir — most
  realistic chunking, but heavy/non-deterministic/PDF-parsing; (c) hybrid (snippets + 2–3 full filings).
- **Decision:** **(a)** Commit cleaned FinanceBench **evidence snippets** as Layer-1, pinned by
  `corpus/layer1/manifest.json`. A throwaway `scripts/fetch_layer1.py` documents provenance and can
  refresh/extend from the public HF datasets-server (no auth). Layer-1 clearance: `public` for
  financial-statement excerpts (real public filings), `analyst` for interpretive MD&A excerpts — giving
  Layer-1 a public↔analyst boundary while the full clearance gradient lives in the authored Layer-2 overlay.
- **Rationale:** Deterministic, offline ITs; minimal embedding cost; the snippets are exactly the evidence
  the P2 golden set scores, keeping P1 ingestion and P2 evals coherent. Realism of full-document chunking is
  deferred — if evals later need it, switch to option (b)/(c) via a new ADR. Distinctive snippet tokens
  (e.g. "Zwijndrecht", "Combat Arms Earplugs", "Amex Ventures", "MMM26") give the hybrid sparse-retrieval
  test real keywords dense search alone would miss.
- **Consequences:** Layer-1 lives in version control (CC-BY-NC-4.0 attribution in `corpus/README.md` +
  manifest). The ingestion loader (Task 3) reads `manifest.json` + snippet files; it does not parse PDFs in
  P1. Re-ingest is a full rebuild. Chunking (ADR-0011) still applies but produces far fewer chunks per doc.

### ADR-0019 — Testcontainers ITs: docker-java API pin + exec-classifier jar
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §4, §5 (Task 1)
- **Context:** P1 Task 1 introduced the first Testcontainers integration test (`SchemaMigrationIT`, pgvector
  pg16) and Flyway-managed schema. Two environment/build frictions surfaced that would otherwise make ITs
  flaky or unrunnable, and the resolution is non-obvious enough to record for reproducibility.
- **Problems & options:**
  1. **Modern Docker daemon rejects Testcontainers' default API version.** Daemons ≥28 (local dev runs 29.x)
     enforce a minimum Docker API of 1.40, but Testcontainers' bundled docker-java negotiates 1.32 →
     *"client version 1.32 is too old."* docker-java **ignores the `DOCKER_API_VERSION` env var**; the only
     levers are its `api.version` config property or a programmatic client. Options: (a) pin `api.version`
     via a forwarded system property (portable, overridable); (b) require each dev to hand-edit a docker-java
     props file (fragile); (c) downgrade Docker (unacceptable).
  2. **Spring Boot fat jar hides classpath resources from Failsafe ITs.** After `package`, the repackaged fat
     jar becomes the project artifact; Failsafe then resolves the project's classpath entry to that jar, where
     resources live under `BOOT-INF/classes/` — so `classpath:db/migration` (Flyway) and `@SpringBootTest`
     package-up config scanning silently find **nothing** (lifecycle `verify` failed while the direct
     `failsafe:` goal passed). Options: (a) classify the fat jar (`-exec`) so the **main** artifact stays a
     thin jar with resources at the root; (b) bind `repackage` after `integration-test` (non-standard, breaks
     `package`); (c) point Flyway at a `filesystem:` path (brittle, env-specific).
- **Decision:**
  1. Pin docker-java's **`api.version`** via a parent-pom property **`docker.api.version` (default `1.43`)**,
     forwarded to the Failsafe-forked JVM through `<systemPropertyVariables>`. Overridable per-machine with
     `-Ddocker.api.version=…`.
  2. Give the Spring Boot **repackage a `classifier=exec`** so the runnable jar is `*-exec.jar` and the main
     artifact is a thin jar (resources at classpath root). Dockerfile copies `*-exec.jar`.
  3. Write `SchemaMigrationIT` against **Flyway's Java API directly** (Testcontainers datasource), not
     `@SpringBootTest` — it tests the migration SQL in isolation, with no Spring context or Ollama beans. The
     "Flyway runs on boot" wiring is covered later by the ingestion IT (Task 3), which needs a context anyway.
- **Rationale:** All three keep the build portable (CI's older Docker also satisfies API 1.43; `verify` stays
  green in both lifecycle and direct invocation) and the ITs fast and hermetic. The frictions are
  environment-driven, so the fixes live in build config + RUNBOOK, not application code.
- **Consequences:** New deps in `rag-engine` (jdbc, postgresql, flyway-core, flyway-database-postgresql,
  testcontainers). `verify` now requires Docker (no GPU). Downstream modules adopting Testcontainers inherit
  `docker.api.version`; any that produce a runnable jar should reuse the `exec` classifier convention.

### ADR-0018 — Answer generation scope & citation granularity
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §3 (D-P1-8)
- **Context:** P1 must prove the forcing story's "answer with citations" — but we could stop at retrieval or
  go all the way to a generated answer; citations could be chunk- or sentence-level.
- **Options considered:** (a) **Full QA: grounded answer with inline `[n]` markers → chunk-level citations**;
  (b) retrieval-only (ranked chunks, no LLM answer) — smaller but doesn't prove the citation story.
- **Decision:** **(a)** Full grounded QA via Spring AI Advisors, **chunk-level** inline `[n]` citations.
- **Rationale:** Matches the roadmap ("answers carry inline citations") and the Priya story; chunk-level is
  the right granularity for 10-K prose + AML memos without the overhead of span attribution.
- **Consequences:** `CitationExtractor` must guarantee every marker resolves to a returned chunk and no
  citation exceeds caller clearance. Sentence-level attribution deferred to P2 tuning if evals warrant it.
- **Implementation note (P1 task 7):** the prompt is assembled **directly** (`ChatModel` + a `SystemMessage`
  carrying `SPOTLIGHT_INSTRUCTION` + numbered-`[n]` citation rules, and a `UserMessage` with numbered
  spotlighted sources) rather than via the stock `QuestionAnswerAdvisor` — the numbered-citation +
  spotlighting + guardrail contract is custom (consistent with the custom retriever). `CitationExtractor`
  parses `[n]`, ignores out-of-range/duplicate markers, and re-checks `isVisible` per citation (fail-closed).
  When no safe source survives, `QueryService` returns a grounded "no authorized information" refusal **without
  calling the model** (no hallucination, no cost). `POST /v1/query` returns `{answer, citations[], retrieval}`;
  `POST /v1/admin/ingest` is guarded to `RESTRICTED` callers via the shim. A fail-closed `ClearanceResolver`
  (`@ConditionalOnMissingBean`) keeps the context bootable outside `local`/`test` without trusting headers.
- **Live E2E validation (2026-06-13):** verified end-to-end against the real remote Ollama
  (`qwen2.5:3b-instruct` + `nomic-embed-text`); `QueryLiveIT` + a manual run green — Priya (compliance) received
  a 6-source cited answer (all ≤ compliance; restricted SAR/EDD/OFAC never cited), public/analyst callers
  correctly bounded, `POST /v1/query` p50 ≈ 5.5 s. Two findings: (1) the `live` Maven profile wasn't actually
  enabling the `@Tag("live")` ITs — an empty `<excludedGroups>` didn't override the base, so switched to a
  `failsafe.excluded.groups` property the profile blanks; (2) `plainto_tsquery` ANDs every lexeme, so long
  conversational questions return 0 sparse hits (dense carried retrieval) — move to `websearch_to_tsquery`/OR
  semantics in P2.

### ADR-0017 — Final Layer-1 corpus subset (FinanceBench)
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §3 (D-P1-7)
- **Context:** ADR-0004 fixed the two-layer corpus but left the exact Layer-1 subset to "P1 start". Layer 1 is
  the Hugging Face finance substrate that proves chunking/embeddings/hybrid/citations.
- **Options considered:** (a) **FinanceBench (`PatronusAI/financebench`) subset, ~10–15 docs**; (b) raw EDGAR
  10-K subset (public-domain, but no eval tuples); (c) both.
- **Decision:** **(a) FinanceBench, ~10–15 docs.** Pulled from HF at ingest time; Layer-1 docs carry a baseline
  clearance tag (`public`/`analyst`), with sensitive material in the authored Layer-2 overlay.
- **Rationale:** FinanceBench ships 150 `(question, answer, evidence, doc)` tuples that **seed the P2 golden
  eval set (D5)** — choosing it now keeps P1 ingestion and P2 evals coherent. License CC-BY-NC-4.0 is fine for
  a portfolio; raw EDGAR (public domain) remains the commercial-clean fallback. Small subset = cost discipline.
- **Consequences:** HF corpus is download-time data, never a runtime dependency (app talks only to pgvector +
  Ollama). If a commercial-clean corpus is ever needed, switch to EDGAR via a new ADR.

### ADR-0016 — Clearance transport in P1 (pre-IdP shim)
- **Date:** 2026-06-13 · **Status:** **Superseded by ADR-0034** (P3) · **Phase:** P1 · **Spec:** P1_SPEC §3 (D-P1-6)
- **Context:** RBAC retrieval needs a caller clearance now, but the simulated identity/clearance provider is
  scheduled for P3 (ADR-0003). P1 must not be blocked waiting on it.
- **Options considered:** (a) **Trusted request header `X-Atlas-Clearance` + a dev user→clearance map (D3),
  gated to the `local`/test profile**; (b) a minimal self-signed JWT stub now (closer to P3 shape, but
  throwaway crypto P3 replaces).
- **Decision:** **(a)** Trusted-header shim, profile-gated, documented loudly as P1-only. The admin ingest
  endpoint is guarded by the same shim (requires admin/`restricted`).
- **Rationale:** Unblocks all RBAC tests without building crypto plumbing P3 discards; keeps the P1 surface
  minimal and the trust boundary explicit.
- **Consequences:** **Must not ship to any shared/prod environment as-is** — P3's simulated IdP supersedes it
  with cryptographically verifiable claims. The retrieval/controller code reads an abstract `Clearance` so the
  P3 swap touches only the resolver.

### ADR-0015 — Prompt-injection guardrail approach (LLM01)
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §3 (D-P1-5)
- **Context:** Retrieved documents are untrusted content (the D7 poisoned-doc fixture); a compliance copilot
  must resist prompt injection (OWASP LLM01).
- **Options considered:** (a) **Defense-in-depth: delimiter/spotlighting of retrieved content + system-prompt
  hardening + a lightweight heuristic scanner that quarantines/flags suspicious chunks**; (b) a dedicated
  classifier model (e.g. prompt-guard) — stronger but new model/infra; (c) instruction-only hardening — weakest.
- **Decision:** **(a)** for P1; escalate to **(b)** in P2 alongside the adversarial/red-team eval set.
- **Rationale:** Pragmatic and testable against D7 without adding a model; layered controls beat any single
  mechanism. The classifier is better justified once P2 can measure its lift.
- **Consequences:** Guardrail effectiveness is gated by the D7 integration test in P1 (pass/fail), then by the
  P2 adversarial suite. Heuristic phrase list must be maintained; documented as a known limitation.
- **Implementation note (P1 task 6):** `InjectionGuardrail` runs after RBAC retrieval, before prompt assembly.
  The scanner normalizes content (lowercase, strip comment *markers* so payloads hidden in `<!-- … -->` are
  still seen, collapse whitespace) and **quarantines** any chunk matching an injection-imperative phrase
  (config `atlas.guardrail.*`, default list in code) — quarantined chunks never reach the model, and the
  matched phrases are surfaced for the trace. Survivors are **spotlighted** in `<atlas:doc …>` delimiters with
  provenance; forged delimiters in source are neutralized (U+2024) and HTML comments stripped from the prompt.
  `SPOTLIGHT_INSTRUCTION` is the system-prompt hardening the QA layer (task 7) prepends. The D7 IT ingests the
  poisoned fixtures through the real pipeline and asserts per-doc quarantine + that a PUBLIC (attacker) caller's
  spotlighted context leaks none of the restricted strings the payloads try to summon (combined RBAC+guardrail).

### ADR-0014 — Reranking approach (seam now, cross-encoder in P2)
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §3 (D-P1-4)
- **Context:** The default Ollama deployment ships no reranker. The roadmap lists reranking under P1 skills,
  but a real cross-encoder adds a model + infra surface.
- **Options considered:** (a) cross-encoder (ONNX/HF) reranker in P1 — best relevance, new dependency;
  (b) LLM-as-reranker via Ollama — no new infra, but added latency/cost and less consistent;
  (c) **no dedicated reranker in P1 — ship RRF-fused order as the rank, keep a `DocumentPostProcessor` seam.**
- **Decision:** **(c)** for the P1 MVP, with the post-processor seam in place; add the cross-encoder in **P2**
  where evals can prove it earns its cost.
- **Rationale:** Keeps P1 focused on the hard problem (RBAC correctness) and avoids unmeasured infra. The seam
  makes (a)/(b) a drop-in later. Honest trade-off: P1 "reranking" is fusion-ordering + interface, not a model.
- **Consequences:** Portfolio/README must state the reranker is RRF-based in P1, cross-encoder in P2. Revisit
  if the P1 manual baseline shows relevance gaps that fusion alone can't close.

### ADR-0013 — Hybrid search fusion method (RRF)
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §3 (D-P1-3)
- **Context:** ADR-0002 fixed hybrid retrieval = dense (pgvector HNSW) + sparse (`tsvector`); the two result
  lists must be combined into one ranking.
- **Options considered:** (a) **Reciprocal Rank Fusion (RRF), k=60** — score-scale-agnostic, robust, no weight
  tuning; (b) weighted linear combination of normalized scores (e.g. 0.6 dense / 0.4 sparse) — tunable but
  needs normalization + weight selection.
- **Decision:** **(a) RRF, k=60.**
- **Rationale:** RRF is the 2026 default for dense+sparse: it sidesteps the incomparable score scales of cosine
  similarity vs `ts_rank` and needs no tuning. Weighted fusion can't be tuned credibly until P2 can measure it.
- **Consequences:** If the P1 baseline reveals a systematic dense/sparse imbalance, switch to (b) in P2 with a
  logged weight set. Fusion is unit-tested for deterministic ordering.
- **Implementation note (P1 task 5):** dense = `embedding <=> ?::vector` (cosine) over the HNSW index, score
  `1 - distance`; sparse = `content_tsv @@ plainto_tsquery('english', ?)` ordered by `ts_rank_cd`. Both push
  the RBAC predicate into SQL (ADR-0012). `ReciprocalRankFusion` sums `1/(k+rank)` (k=60) with a deterministic
  id tie-break. The **D4 negative-access IT is a hard gate**: 6 golden cases × {dense, sparse, hybrid} = 18
  dynamic assertions of 0 cross-clearance leaks. The reranker (ADR-0014) is a pass-through over the fused
  order in P1 (`RrfPassThroughReranker`) behind a `Reranker` seam.

### ADR-0012 — RBAC model & enforcement mechanism
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §3 (D-P1-2)
- **Context:** The system's hardest correctness/safety requirement (R1): a user must **never** receive a chunk
  above their clearance. The four labels are `public`/`analyst`/`compliance`/`restricted`.
- **Options considered:** (a) **hierarchical levels (`public<analyst<compliance<restricted`) + a mandatory SQL
  predicate (`level <= caller`) pushed into both dense and sparse queries in a custom retriever**; (b) Postgres
  Row-Level Security policies — strongest DB guarantee, but session-role plumbing + pool complexity; (c)
  set-of-roles membership — more flexible for non-hierarchical orgs, overkill for four clean levels.
- **Decision:** **(a)** Hierarchical levels with the predicate centralized in `RbacFilterBuilder` so it can
  never be bypassed, plus a defense-in-depth controller assert that every returned citation `<= caller`.
- **Rationale:** Our labels are a genuine hierarchy, so levels + a single mandatory SQL predicate is the
  simplest correct design and uses the `atlas_chunk_clear` index. RLS is recorded as a future hardening option.
- **Consequences:** Proven by the D4 negative-access integration test as a **hard CI gate (0 leaks)** across
  dense/sparse/hybrid paths. If a non-hierarchical org model ever emerges, supersede with a new ADR (sets/RLS).
- **Implementation note (P1 task 4):** the mandatory predicate is encoded as **`clearance = ANY(?)`** bound to
  the caller's visible-label array (e.g. COMPLIANCE → `{public,analyst,compliance}`), not a literal
  `level <= N`. It is semantically identical but fully parameterized (no interpolation of caller input) and
  index-friendly on `atlas_chunk_clear`. `RbacFilterBuilder` returns a reusable `RbacPredicate(sqlFragment,
  params)` so the dense and sparse SQL (task 5) share one boundary, plus `isVisible(...)` for the
  defense-in-depth controller re-check (fails closed on unknown labels). `ClearanceLevel` is the ordered enum;
  unknown labels throw / deny rather than escalate.

### ADR-0011 — Chunking strategy & chunk size
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 · **Spec:** P1_SPEC §3 (D-P1-1)
- **Context:** Chunk shape drives retrieval recall and citation granularity for 10-K prose (Layer 1) and AML
  memos (Layer 2).
- **Options considered:** (a) **recursive/structural splitter, ~512 tokens, ~64 overlap** — respects
  paragraph/section boundaries, overlap preserves cross-boundary context; (b) fixed token windows (e.g. 256/0)
  — simplest but cuts mid-sentence; (c) sentence-window / small-to-big — best precision but more moving parts.
- **Decision:** **(a)** Recursive/structural, ~512-token chunks with ~64-token overlap.
- **Rationale:** A sane, well-understood default for the corpus mix that yields good citation granularity
  without the complexity of small-to-big; window size is cheap to revisit during the P1 manual baseline.
- **Consequences:** Window/overlap are config (env-swappable); re-chunking implies a full re-ingest (P1 has no
  incremental migration). Revisit sizes in P2 once RAGAS context-recall can measure the effect.
- **Implementation note (P1 task 3):** the `DocumentChunker` uses an **injectable token estimator**; the
  production default is a cheap character-based estimate (~4 chars/token) rather than a real tokenizer, since
  JTokkit is not on the Spring AI classpath and exact token counts aren't needed to *size* chunks. Tests inject
  a deterministic word counter for exact boundaries. If P2 evals show sizing drift, swap in a JTokkit/HF
  tokenizer behind the same `ToIntFunction<String>` seam (no API change).

### ADR-0010 — CI pipeline, supply-chain controls (LLM03) & multi-arch image
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P0
- **Context:** P0 DoD requires a CI gate, supply-chain security (OWASP LLM03), and multi-arch images for the
  Oracle Ampere A1 (arm64) prod target.
- **Options considered:**
  - CI shape: one monolithic job vs **separate jobs** (clearer required status checks).
  - Scanners blocking vs report-only; image base **distroless** vs full JRE; build-in-Dockerfile (multi-stage,
    emulated arm64 compile) vs **copy prebuilt jar** (arch-independent); action refs by major tag vs exact/SHA.
- **Decision:** **5 GitHub Actions jobs** — `java` (mvn verify), `python` (ruff+pytest), `secret-scan`
  (gitleaks), `supply-chain` (**Trivy** fs scan + **Syft** CycloneDX SBOM), `image` (buildx **amd64+arm64**,
  pushed to **GHCR on `main` only**). Image is **distroless nonroot, digest-pinned base**, built by **copying
  the arch-independent fat jar** (no QEMU emulation). The live Ollama IT is **gated out of CI** (`live`
  profile). Actions pinned to major tags; `setup-uv` pinned **exact** (`v8.2.0` — no moving `v8` tag exists).
- **Rationale:** Distinct jobs = readable branch-protection checks; distroless = minimal attack surface + fast
  multi-arch; copy-jar exploits the JVM's arch-independence so arm64 needs no emulated build. Trivy is
  **report-only initially** so an upstream Spring CVE can't block the first green build.
- **Consequences:** **TODO** flip Trivy to blocking (`exit-code 1`) once the baseline is triaged; consider
  **SHA-pinning** actions as hardening. Branch protection must require the five check **display names**
  (`Java build & test`, `Python lint & test`, `Secret scan (gitleaks)`, `Vuln scan & SBOM`,
  `Multi-arch image build`). First green run = #2.

### ADR-0009 — Local infra under snap-Docker confinement
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P0
- **Context:** The dev host runs Canonical's **snap** Docker, whose binaries are AppArmor-confined and
  **cannot read files under `/data`** — and the Atlas workspace lives at `/data/aiTrack/Atlas` (outside `$HOME`).
  Verified: a bind mount of `/data/...` appears **empty** in-container, and `docker compose -f /data/...yml`
  fails with *no such file or directory*.
- **Options considered:** relocate the repo under `$HOME` (rejected — workspace is fixed); connect extra snap
  interfaces (no plug grants arbitrary `/data`); a custom DB image baking the init SQL (extra image to
  maintain, and `docker build` from `/data` hits the same confinement); **feed everything via stdin/exec**.
- **Decision:** Never hand a `/data` path to a snap docker binary. The compose file is **piped via stdin**
  (`cat docker-compose.yml | docker compose -f -`), config is passed through **exported env vars** (not
  `--env-file`), DB init SQL is streamed via **`docker exec` stdin**, data lives in **named volumes**, and
  local image builds pipe context via **`tar | docker buildx build -`**. Images stay **stock** (multi-arch
  manifest preserved).
- **Rationale:** Confinement-proof and **portable** — stdin/exec work identically on non-snap Docker hosts, so
  the repo isn't snap-specific. Keeps the DB image unmodified (no custom build to maintain).
- **Consequences:** `infra/Makefile` encodes the pattern; documented in `infra/README.md` + RUNBOOK §3. A
  non-obvious gotcha for contributors, hence this ADR.

### ADR-0008 — Monorepo build topology & framework version pins
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P0
- **Context:** A polyglot monorepo with several future Spring modules (gateway, rag-engine, mcp-tools) needs
  one source of truth for dependency/plugin versions, and a stable, reproducible framework baseline.
- **Options considered:**
  - Parent: each module parents off `spring-boot-starter-parent` (free plugin mgmt, but per-module version
    duplication and no shared home for our own deps) vs a **root aggregator pom** that imports the Spring Boot
    + Spring AI BOMs in `dependencyManagement` and centralizes `pluginManagement`.
  - Framework pin: latest Spring AI (docs already show a 2.0 line) vs the **1.0.0 GA** verified on Maven Central.
- **Decision:** Root **aggregator pom** (packaging `pom`) imports `spring-boot-dependencies` + `spring-ai-bom`
  and centralizes plugin versions; modules parent off it and declare dependencies version-free. Pin
  **Spring Boot 3.4.7 + Spring AI 1.0.0 GA**, **Java 21**. Because we do *not* use `spring-boot-starter-parent`,
  the Spring Boot **`repackage`** execution is declared explicitly in each app module.
- **Rationale:** One upgrade point across all Java modules; no dual-parent; GA pin = downloadable + stable for
  a learning project (bumping is a property change + ADR). Avoids surprise from a moving 2.0 line mid-build.
- **Consequences:** App modules must bind `repackage` — forgetting it yields a non-executable thin jar (a bug
  this caught during P0). Compiler/surefire/failsafe versions are pinned centrally in the parent.

### ADR-0007 — Security & governance baseline (OWASP GenAI + OTel + AI governance)
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P0–P5 (cross-cutting)
- **Context:** Atlas is a financial/compliance copilot; its security and governance posture must be explicit
  and provable, not implicit per-developer judgment.
- **Options considered:** Ad-hoc per-phase security vs adopting a recognized framework set — **OWASP Top 10
  for LLM Apps (2025)** + **Agentic Apps (2026)** as the control map, **OpenTelemetry GenAI semantic
  conventions** for telemetry, and **NIST AI RMF / EU AI Act** as governance guides.
- **Decision:** Adopt the OWASP GenAI Top 10 as the security control map (`ROADMAP.md` §7); standardize
  observability on **OTel GenAI semantic conventions** (ingested by Langfuse); treat NIST AI RMF + EU AI Act
  high-risk principles (human oversight, traceability, record-keeping) as **design constraints**. Folded into
  each phase's DoD — **no separate security phase**.
- **Rationale:** Industry-standard, interview-relevant, and directly on-narrative for a compliance product;
  OTel graduated CNCF in 2026, making it the durable choice over proprietary-only tracing.
- **Consequences:** CI gains supply-chain scans + digest pinning + SBOM/AIBOM (LLM03, P0); P1 ingestion gains
  content validation/provenance (LLM04); P2 red-team adds system-prompt-leakage (LLM07) and OTel conventions;
  P3 adds output sanitization (LLM05); P5 adds safe UI rendering + secret-store injection. Not a formal
  certification — an engineering posture aligned to the standards.

### ADR-0006 — Production deploy target & GPU host
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P0/P5
- **Context:** Low INR budget for both the app stack and the LLM endpoint; the app services are CPU-only,
  the LLM needs a GPU only intermittently. Preference for an **Indian provider** billing in ₹ (UPI), easy to
  use, and ideally aligned with the financial/compliance (data-residency) narrative.
- **Options considered:**
  - App stack: Oracle Cloud Always Free (Ampere A1 ARM, 4 vCPU/24 GB, ₹0) vs Hetzner (~₹350–700/mo) vs DO/Lightsail.
  - GPU (Indian, INR): **JarvisLabs.ai** (~₹41/hr, per-minute, pause/resume) vs **E2E Networks** (~₹49/hr +GST,
    NSE-listed/MeitY/DPDP) vs **Yotta Shakti** (enterprise H100). Global USD options (RunPod/Vast.ai) rejected
    for not billing in INR.
- **Decision:** App stack on **Oracle Cloud Always Free ARM** (fallback **Hetzner**); LLM on **JarvisLabs.ai**
  with per-minute billing + pause/resume + persistent storage (fallback **E2E Networks**). A modest GPU
  (L4 / A5000 class) suffices for the small dev model.
- **Rationale:** Near-zero standing cost; JarvisLabs' per-minute billing + pause/resume is the cleanest match
  for our "stop-when-idle" discipline and the easiest UX for a solo developer; INR/UPI removes the USD-payment
  friction. Env-swappable endpoint means the app stack is indifferent to the live GPU.
- **Consequences:** Must build **multi-arch (amd64+arm64)** images for the ARM box (anticipated in P0).
  Resuming a paused instance may change its public endpoint → update `OLLAMA_BASE_URL`. See `RUNBOOK.md` §1.3, §2.

### ADR-0005 — Dev models & embedding dimension
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P0/P1
- **Context:** Cost discipline mandates small/quantized models in dev; the embedding model fixes the
  pgvector column dimension and cannot change cheaply later.
- **Options considered:** Chat — `qwen2.5:3b-instruct` vs `llama3.2:3b`. Embeddings — `nomic-embed-text`
  (768-dim) vs `mxbai-embed-large` (1024-dim) vs `bge-*`.
- **Decision:** Dev chat **`qwen2.5:3b-instruct`**; embeddings **`nomic-embed-text`** → **768-dim** pgvector.
- **Rationale:** Both small/quantization-friendly and well-supported on Ollama; 768-dim keeps index size and
  latency modest for dev. Larger/frontier models reserved for P5 demos.
- **Consequences:** pgvector `vector(768)` column + HNSW index sized accordingly. Swapping the embedding
  model later requires a re-embed/migration — record as a new ADR if it happens.

### ADR-0004 — Dataset & RBAC clearance overlay
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1
- **Context:** Need a realistic financial corpus *and* a permission model to enforce; no off-the-shelf
  dataset ships with clearance labels. Additionally, the forcing story is a financial-*crime* (AML/SAR)
  scenario whose data shape differs from public financial-disclosure corpora — one source cannot serve both.
- **Options considered:**
  - Corpus: pure synthetic vs real HF finance corpus (SEC 10-K/EDGAR, `PatronusAI/financebench`) vs licensed.
  - AML data: real AML transaction sets (IBM AMLSim/SAML-D, `VynFi/vynfi-aml-100k`, `alerterra/aml_transactions`)
    vs synthetic narrative case files. The transaction sets are **structured rows for fraud *classification***,
    not a document corpus for retrieval-with-citations — **off-thesis**, so excluded.
  - RBAC overlay: per-document role tags vs row-level security vs dynamic partitioning (SIGMOD '26).
- **Decision:** A **two-layer corpus + authored fixtures**:
  - **Layer 1 (RAG substrate):** HF finance corpus (SEC filings and/or FinanceBench). FinanceBench's 150
    `(question, answer, evidence, doc)` tuples also seed the P2 golden eval set.
  - **Layer 2 (compliance/AML demo):** ~10–20 hand-authored narrative docs (account memos, AML exception
    summaries, AML policy, SAR template) carrying `public`/`analyst`/`compliance`/`restricted` tags.
  - **Fixtures:** identity (users→clearance), negative-access golden cases, adversarial/red-team set,
    poisoned-doc fixtures, PII-bearing samples.
  AML *transaction* CSVs are **excluded**.
- **Rationale:** Layer 1 gives realistic retrieval + a credible external eval set; Layer 2 gives the story,
  RBAC, and the SAR action something to operate on; keeping transaction CSVs out keeps Atlas a
  retrieval/agent system, not a fraud classifier. License: FinanceBench is **CC-BY-NC-4.0** (non-commercial) —
  acceptable for a portfolio; raw **EDGAR** (public domain) is the commercial-clean fallback.
- **Consequences:** Overlay-tagging + fixture authoring are ours to build and test; exact corpus subset
  finalized at P1 start. **This is the complete data inventory for Atlas across all phases** — the two-layer
  corpus is the *core*, but these fixture artifacts are first-class data the corpus does not supply:

  | ID | Artifact | Purpose / case | Source | Phase |
  |----|----------|----------------|--------|-------|
  | D1 | RAG document corpus (Layer 1) | chunking, embeddings, hybrid search, citations | FinanceBench / EDGAR subset | P1 |
  | D2 | Clearance overlay + AML case files (Layer 2) | RBAC tags; Priya/AML/SAR story; "Northwind account" | authored (synthetic) | P1/P4 |
  | D3 | Identity fixtures (users → clearance) | simulated IdP; who-sees-what | authored config | P3 (used in P1 tests) |
  | D4 | Negative-access golden set | prove no above-clearance leakage | authored from D1+D2 tags | P1 |
  | D5 | Golden QA eval set | RAGAS faithfulness / context-recall thresholds | FinanceBench tuples + select D2 | P2 |
  | D6 | Adversarial / red-team set | prompt-injection, jailbreak, access-bypass, prompt-leakage | authored | P2 |
  | D7 | Poisoned-document fixtures | LLM01/LLM04 ingestion + injection guardrails | authored, injected into corpus copy | P1 |
  | D8 | PII-bearing samples | PII detection + egress redaction | baked into D2 | P3 |

### ADR-0003 — Identity / clearance provider (simulated)
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P3
- **Context:** Atlas must resolve a verifiable clearance per request, but standing up a real IdP is out of
  scope for a portfolio demo.
- **Options considered:** Full OIDC (Keycloak) vs simulated identity/clearance provider issuing signed claims.
- **Decision:** **Simulated identity/clearance provider** that issues a verifiable clearance claim the RAG
  engine and MCP tools enforce.
- **Rationale:** Keeps focus on the AI-engineering surface (permission-aware retrieval, governed tools)
  while still proving the enforcement path; aligns with MCP OAuth 2.1 resource-server pattern conceptually.
- **Consequences:** Claims must be cryptographically verifiable, not trusted blindly; if a real IdP is added
  later, supersede with a new ADR.

### ADR-0002 — Vector store: Postgres + pgvector
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1
- **Context:** Need embeddings + role-tagged metadata with RBAC filtering, on a low-spec/low-cost footprint.
- **Options considered:** pgvector vs Pinecone/Weaviate/Qdrant (dedicated vector DBs).
- **Decision:** **PostgreSQL ≥ 16 + pgvector ≥ 0.7**, **HNSW** index; hybrid search = dense (pgvector) +
  sparse (`tsvector` full-text).
- **Rationale:** One datastore for vectors + metadata + RBAC + agent checkpoints (P4) avoids extra infra and
  cost; pgvector is production-validated in 2026; HNSW gives strong recall/latency for our scale.
- **Consequences:** Index tuning (`ef_search`, `m`) is ours to own; HNSW vs IVFFlat trade-off re-evaluated if
  data volume grows (new ADR).

### ADR-0001 — Core language/runtime split (Java + Python)
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P0
- **Context:** Engineer's moat is Java/Spring; the AI-orchestration/eval ecosystem is Python-first.
- **Options considered:** All-Java vs all-Python vs polyglot split.
- **Decision:** **Java/Spring Boot + Spring AI 1.0** for gateway, RAG engine, MCP tool servers; **Python**
  for LangGraph agents and RAGAS/DeepEval evals.
- **Rationale:** Plays to existing depth while using best-in-class tools where each is strongest; Spring AI
  1.0 (GA early 2026) covers RAG, pgvector, Advisors, native evaluators, and MCP client/server.
- **Consequences:** Two toolchains (Maven + uv) and a cross-language boundary (HTTP/MCP) to maintain and test.

---

## 3. ADR template (copy for new entries)

```
### ADR-NNNN — <short title>
- **Date:** YYYY-MM-DD · **Status:** Proposed|Accepted|Superseded by ADR-NNNN · **Phase:** PX
- **Context:** <the forces/problem requiring a decision>
- **Options considered:** <A vs B vs C, with the key trade-off each>
- **Decision:** <what we chose>
- **Rationale:** <why — the part interviewers ask about>
- **Consequences:** <follow-on work, risks, what would trigger revisiting>
```
