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
| 0007 | 2026-06-13 | Security & governance baseline (OWASP/OTel/AI gov) | Accepted | P0–P5 |
| 0006 | 2026-06-13 | Production deploy target & GPU host | Accepted | P0/P5 |
| 0005 | 2026-06-13 | Dev models & embedding dimension | Accepted | P0/P1 |
| 0004 | 2026-06-13 | Dataset & RBAC clearance overlay | Accepted | P1 |
| 0003 | 2026-06-13 | Identity / clearance provider (simulated) | Accepted | P3 |
| 0002 | 2026-06-13 | Vector store: Postgres + pgvector | Accepted | P1 |
| 0001 | 2026-06-13 | Core language/runtime split (Java + Python) | Accepted | P0 |

> These six are pre-recorded from the roadmap planning (CLAUDE.md + `ROADMAP.md` §0). Each remains open to
> revision with a new superseding ADR if a phase surfaces evidence against it.

---

## 2. Decisions

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
