# P1 — Permission-aware RAG engine + pgvector store — SPEC

> Status: **DRAFT — grooming, awaiting owner approval. No application code until approved.**
> Phase owner doc set: `CLAUDE.md` · `docs/ROADMAP.md` (§2 P1) · `docs/DECISIONS.md` (ADR-0002/0004/0005) · `docs/RUNBOOK.md`.
> Date drafted: 2026-06-13.

This phase builds the **core and hardest-correctness** subsystem: given a user + clearance, retrieve
**only** authorized documents and answer **with citations**, resisting prompt injection. It is entirely a
**Java / Spring AI** effort (the moat). Python enters only in P2.

---

## 1. Scope

### In scope
1. **Ingestion pipeline (admin-side):** load corpus → validate + record provenance → chunk → embed →
   write to pgvector with `clearance` + source metadata and a sparse `tsvector` column.
2. **Two-layer corpus, finalized:** Layer 1 RAG substrate (FinanceBench / EDGAR subset, D1) +
   Layer 2 authored AML clearance overlay (D2). Plus P1-owned fixtures: negative-access golden set (D4)
   and poisoned-document fixtures (D7).
3. **pgvector schema + HNSW index** on PostgreSQL 16, `vector(768)` (per ADR-0002/0005).
4. **Hybrid retrieval:** dense (pgvector HNSW) + sparse (Postgres full-text `tsvector`) candidate
   generation, fused, then reranked.
5. **RBAC enforcement at retrieval time:** a user can **never** receive a chunk above their clearance.
   Proven by the D4 negative-access test set as a **hard gate** (0 leaks).
6. **Answer generation with inline citations** to source chunks, via Spring AI Advisors.
7. **Prompt-injection guardrails (LLM01)** tested against the D7 poisoned-doc fixture.
8. **Ingestion integrity (LLM04):** trusted-corpus-only admission, content hash + provenance at ingest.
9. **HTTP API** for query (and an admin ingest trigger) on the existing `rag-engine` service.
10. **Manual quality baseline** (precursor that P2 automates) recorded in the module README.
11. Decisions logged in `docs/DECISIONS.md`; `rag-engine/README.md` updated; env-swappable config.

### Non-goals (explicit — prevent scope creep)
- **No automated eval thresholds / RAGAS / DeepEval / Langfuse.** That is **P2**. P1 ships only a *manual*
  baseline + the negative-access hard gate. (Per CLAUDE.md "evals before agents", but the harness itself is P2.)
- **No real IdP / OIDC.** Clearance arrives via a P1 stand-in (see Decision D-P1-6); the simulated provider
  is **P3** (ADR-0003).
- **No API Gateway, cost routing, caching, rate limiting, PII redaction.** All **P3**.
- **No agents, LangGraph, MCP tools, SAR action, human-in-the-loop.** All **P4**.
- **No React UI.** Citations/traces surfaced as JSON only; UI is **P5**.
- **No AML *transaction* CSV ingestion** (off-thesis; ADR-0004).
- **No semantic caching, no multi-tenant beyond the role overlay, no doc-update/re-embed migration tooling**
  (re-ingest is full-rebuild in P1).
- **No fine-tuning / training.** Off-the-shelf Ollama models only (ADR-0005).
- **No production deploy.** Local + CI only (deploy is P5).

---

## 2. Design

### 2.1 Language split (Java vs Python) — and why
- **100% Java / Spring Boot + Spring AI 1.0 GA** (the `rag-engine` module). Reasons:
  - This subsystem *is* the Java moat (CLAUDE.md). Spring AI 1.0 GA provides first-class `PgVectorStore`,
    `EmbeddingModel`/`ChatModel` (Ollama), Advisors (`RetrievalAugmentationAdvisor` / `QuestionAnswerAdvisor`),
    `DocumentReader`/`TextSplitter`, and `FilterExpression` metadata filtering — covering the whole pipeline.
  - RBAC enforcement must live as close to the datastore as possible; doing it in the Java retrieval layer
    (and/or Postgres) keeps one trust boundary.
- **Python appears in P1 only as data, not code:** corpus prep can be a throwaway script, but the canonical
  fixtures (D2/D4/D7) are committed as **static files** (JSON/Markdown/CSV) consumed by Java tests. No Python
  service or dependency is added in P1. (RAGAS/DeepEval Python harness = P2.)

### 2.2 Component breakdown (`rag-engine`)
```
rag-engine/
  ingest/
    CorpusLoader            # reads Layer-1 + Layer-2 source files (DocumentReader)
    IngestionValidator      # LLM04: trusted-source allow-list, content-hash, provenance record
    DocumentChunker         # TextSplitter wrapper (strategy per D-P1-1)
    EmbeddingWriter         # embeds chunks (nomic-embed-text 768) + writes pgvector + tsvector
    IngestionService        # orchestrates load→validate→chunk→embed→store (idempotent, full-rebuild)
  retrieval/
    ClearanceLevel          # ordered enum: PUBLIC < ANALYST < COMPLIANCE < RESTRICTED
    RbacFilterBuilder       # builds the clearance predicate (Spring AI FilterExpression / SQL)
    HybridDocumentRetriever # custom DocumentRetriever: dense + sparse + RBAC filter + fusion (D-P1-3)
    Reranker                # DocumentPostProcessor: reorders fused candidates (D-P1-4)
    InjectionGuardrail      # LLM01: sanitize/quarantine retrieved content + answer-time defense
  qa/
    QueryService            # wires Advisor chain → answer + citations
    CitationExtractor       # maps answer spans → source chunk ids/metadata (D-P1-8)
  api/
    QueryController         # POST /v1/query
    AdminIngestController   # POST /v1/admin/ingest (guarded)
  config/
    VectorStoreConfig, AdvisorConfig, ...
  probe/                    # (existing P0 connectivity probe — retained)
```

### 2.3 Data model / schema (pgvector, PostgreSQL 16)
Two tables: a document (provenance) table and a chunk (embedding) table. `vector(768)` fixed by ADR-0005.

```sql
-- documents: one row per source document (provenance / LLM04)
CREATE TABLE atlas_document (
  id            UUID PRIMARY KEY,
  source_uri    TEXT NOT NULL,            -- where it came from (file path / EDGAR url)
  source_layer  SMALLINT NOT NULL,        -- 1 = RAG substrate, 2 = AML overlay
  title         TEXT,
  clearance     TEXT NOT NULL,            -- public|analyst|compliance|restricted
  content_sha256 TEXT NOT NULL,           -- integrity (LLM04)
  trusted       BOOLEAN NOT NULL DEFAULT TRUE,
  ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT clearance_chk CHECK (clearance IN ('public','analyst','compliance','restricted'))
);

-- chunks: retrieval unit. clearance denormalized onto the chunk for single-predicate filtering.
CREATE TABLE atlas_chunk (
  id            UUID PRIMARY KEY,
  document_id   UUID NOT NULL REFERENCES atlas_document(id) ON DELETE CASCADE,
  chunk_index   INT  NOT NULL,
  content       TEXT NOT NULL,
  clearance     TEXT NOT NULL,            -- inherited from document; the RBAC key
  metadata      JSONB NOT NULL DEFAULT '{}',  -- title, page, section, source_uri (for citations)
  embedding     vector(768) NOT NULL,
  content_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  CONSTRAINT chunk_clearance_chk CHECK (clearance IN ('public','analyst','compliance','restricted'))
);

CREATE INDEX atlas_chunk_hnsw   ON atlas_chunk USING hnsw (embedding vector_cosine_ops);  -- dense
CREATE INDEX atlas_chunk_tsv    ON atlas_chunk USING gin (content_tsv);                   -- sparse
CREATE INDEX atlas_chunk_clear  ON atlas_chunk (clearance);                              -- RBAC pre-filter
```
> Note: Spring AI's stock `PgVectorStore` owns its own `vector_store` table. We use a **custom schema +
> custom `DocumentRetriever`** because hybrid (tsvector) + a hard RBAC predicate are not expressible through
> the stock store alone. Schema managed by **Flyway** (new dependency) for reproducibility.

### 2.4 Key interfaces & contracts
**Clearance hierarchy (the RBAC core):**
- Ordered: `PUBLIC(0) < ANALYST(1) < COMPLIANCE(2) < RESTRICTED(3)`.
- Rule: a user with level *L* may see chunks where `chunk.level <= L`. (Hierarchical, not set-membership —
  see D-P1-2.) Enforced as a **mandatory SQL predicate**, never as an optional post-filter.

**Query API — `POST /v1/query`**
```jsonc
// request
{ "query": "Summarize open AML exceptions for the Northwind account this quarter",
  "topK": 6 }
// clearance supplied per D-P1-6 (header X-Atlas-Clearance in P1)
// response
{ "answer": "… [1] … [2] …",
  "citations": [
    { "marker": 1, "chunkId": "…", "documentId": "…", "title": "…",
      "sourceUri": "…", "clearance": "compliance", "score": 0.83, "snippet": "…" }
  ],
  "retrieval": { "denseHits": 20, "sparseHits": 20, "fused": 12, "reranked": 6,
                 "clearanceApplied": "compliance" } }
```
- **Contract guarantees:** every `citations[].clearance <= caller clearance`; `answer` cites only chunks in
  `citations`; if no authorized chunk is found, return a grounded "no authorized information" answer (not a
  hallucination).

**Admin ingest — `POST /v1/admin/ingest`** → triggers full rebuild from the configured corpus path; returns
counts (docs, chunks, rejected-untrusted). Guarded (see D-P1-6).

### 2.5 Request / data flow
**Ingestion (offline):**
`CorpusLoader` → `IngestionValidator` (allow-list + sha256 + provenance row) → `DocumentChunker` →
`EmbeddingWriter` (embed 768 + insert chunk; `content_tsv` auto-generated) → committed to pgvector.

**Query (online):**
1. Resolve caller clearance (D-P1-6) → `ClearanceLevel`.
2. `HybridDocumentRetriever`: embed query → run **dense kNN (HNSW)** AND **sparse full-text** queries, both
   with the **RBAC predicate `clearance_level <= caller`** applied *in SQL* → fuse candidates (D-P1-3).
3. `Reranker` reorders fused set, truncates to `topK` (D-P1-4).
4. `InjectionGuardrail` wraps/sanitizes retrieved content (LLM01) before it enters the prompt.
5. `RetrievalAugmentationAdvisor` / `QuestionAnswerAdvisor` builds the grounded prompt → `ChatModel` (Ollama).
6. `CitationExtractor` attaches citation metadata; controller returns answer + citations + retrieval stats.

**Security mapping touched in P1:** LLM01 (injection guardrail), LLM04 (ingestion integrity),
LLM08 (RBAC at retrieval / no cross-clearance leakage), LLM09 (grounded citations). Per ROADMAP §7.

---

## 3. Decisions to make now

> ADR-0002 (pgvector + HNSW + dense/sparse hybrid), ADR-0004 (two-layer corpus + fixtures), and ADR-0005
> (nomic-embed-text 768 / qwen2.5:3b) are **already locked** and not re-opened here. Below are the **open**
> P1 choices. On your confirmation I log each as a new ADR (0011…) in `docs/DECISIONS.md`.

**D-P1-1 — Chunking strategy & size**
- (a) **Recursive/structural splitter, ~512 tokens, ~64 overlap** *(recommended)* — respects paragraph/section
  boundaries, overlap preserves cross-boundary context; good citation granularity.
- (b) Fixed token windows (e.g. 256/0 overlap) — simplest, but cuts mid-sentence, weaker citations.
- (c) Sentence-window / small-to-big (retrieve small, expand to parent) — best precision/context, but more
  moving parts; defer the complexity to P2 tuning.
- **Recommendation: (a).** Sane default for 10-K prose + AML memos; revisit window size during the P1 manual
  baseline.

**D-P1-2 — RBAC model & enforcement mechanism**
- (a) **Hierarchical levels + mandatory SQL predicate in a custom retriever** *(recommended)* — `level <= caller`
  pushed into both dense and sparse queries; single trust boundary, fast (uses `atlas_chunk_clear` index).
- (b) Set-of-roles membership (chunk tagged with a set; caller holds a set; overlap required) — more flexible
  for non-hierarchical orgs, but our four labels are a clean hierarchy; overkill now.
- (c) Postgres Row-Level Security (RLS) policies — strongest DB-enforced guarantee, but adds session-role
  plumbing and complicates Spring connection pooling for modest gain at this scale.
- **Recommendation: (a)**, with the predicate centralized in `RbacFilterBuilder` so it can never be bypassed,
  and a defense-in-depth assert in the controller that every returned citation `<= caller`. (RLS noted as a
  future hardening ADR if needed.)

**D-P1-3 — Hybrid fusion method**
- (a) **Reciprocal Rank Fusion (RRF), k=60** *(recommended)* — score-scale-agnostic, robust, no weight tuning,
  the 2026 default for dense+sparse.
- (b) Weighted linear combination of normalized scores (e.g. 0.6 dense / 0.4 sparse) — tunable but needs
  normalization + weight selection (and a place to log the weights).
- **Recommendation: (a) RRF.** If the P1 baseline shows a systematic dense/sparse imbalance, switch to (b) in
  P2 where we can measure it.

**D-P1-4 — Reranking approach** *(no reranker ships on our Ollama by default — this is a real fork)*
- (a) **Cross-encoder reranker via a small ONNX/HF model served behind an interface** — best relevance, but
  adds a model/dependency and infra surface.
- (b) **LLM-as-reranker** (ask the chat model to score/order candidates) — no new infra, reuses Ollama, but
  adds latency/cost and is less consistent.
- (c) **No dedicated reranker in P1 — ship RRF-fused order as the rerank, keep the `DocumentPostProcessor`
  seam** *(recommended for P1)* — keeps P1 focused on RBAC correctness; add a real reranker in P2 when evals
  can prove it earns its cost.
- **Recommendation: (c)** for the P1 MVP, with the interface in place so (a)/(b) drop in later. (Roadmap lists
  reranking under P1 skills; we satisfy it with the fusion+seam and explicitly schedule the cross-encoder for
  P2 — flag if you want the cross-encoder in P1 instead.)

**D-P1-5 — Prompt-injection guardrail (LLM01)**
- (a) **Defense-in-depth: delimiter/spotlighting of retrieved content + system-prompt instruction hardening +
  a lightweight heuristic scanner (known injection phrases) that quarantines/flags chunks** *(recommended)* —
  pragmatic, testable against D7, no extra model.
- (b) Dedicated classifier model (e.g. prompt-guard) — stronger, but new model/infra; better fit once P2
  red-team set exists.
- (c) Instruction-only hardening — weakest; insufficient for a compliance narrative.
- **Recommendation: (a)**; escalate to (b) in P2 alongside the adversarial eval set.

**D-P1-6 — Clearance transport in P1 (IdP is P3)**
- (a) **Trusted request header `X-Atlas-Clearance` + a small dev user→clearance map (D3 fixture), gated so it
  only works under the `local`/test profile** *(recommended)* — unblocks all RBAC tests now without faking
  crypto we'll replace in P3.
- (b) A minimal self-signed JWT stub now — closer to the P3 shape, but builds throwaway crypto plumbing P3
  replaces anyway.
- **Recommendation: (a)**, documented loudly as a P1-only shim that P3's simulated IdP supersedes. Admin
  ingest endpoint guarded by the same shim (requires `restricted`/admin).

**D-P1-7 — Final Layer-1 corpus subset**
- (a) **FinanceBench subset (~N docs/filings)** *(recommended)* — its 150 `(q,a,evidence,doc)` tuples seed the
  P2 golden set, so picking it now aligns P1 ingestion with P2 evals. License CC-BY-NC-4.0 (fine for portfolio).
- (b) Raw EDGAR 10-K subset — public domain / commercial-clean, but no ready eval tuples.
- (c) Both (FinanceBench primary + a couple EDGAR filings for volume).
- **Recommendation: (a)** to keep P1↔P2 coherent; size the subset small (cost discipline) — propose ~10–15
  filings/docs. Confirm exact count.

**D-P1-8 — Answer generation scope & citation granularity**
- (a) **Full QA: generate the grounded answer with inline `[n]` markers mapped to chunk-level citations**
  *(recommended)* — matches the roadmap ("answers carry inline citations") and the forcing story.
- (b) Retrieval-only (return ranked chunks, no LLM answer) — smaller, but doesn't prove the citation story.
- **Recommendation: (a)**, chunk-level citations (sentence-level deferred to P2 tuning).

---

## 4. Test strategy

> P1 gate model: **negative-access RBAC = hard pass/fail (0 leaks tolerated).** Quality (faithfulness etc.) is
> a **manual baseline recorded in the README**; it becomes an automated CI threshold in **P2** (not in P1).

### Unit tests (JUnit 5, no DB/model)
- `ClearanceLevel` ordering + `RbacFilterBuilder` predicate construction (every level → correct `<=` set).
- `DocumentChunker` boundaries/overlap/token counts for the chosen strategy.
- `IngestionValidator`: untrusted source rejected; sha256 computed; provenance row shape.
- RRF fusion math (`HybridDocumentRetriever` fusion unit).
- `InjectionGuardrail` flags/quarantines known injection strings; preserves benign content.
- `CitationExtractor`: marker↔chunk mapping; no citation outside the retrieved set.

### Integration tests (Testcontainers: `pgvector/pgvector:pg16`)
- **Ingestion IT:** ingest D1+D2 → expected doc/chunk counts; HNSW + tsvector indexes exist; provenance rows present.
- **RBAC negative-access IT (HARD GATE, D4):** for each (user, query) golden case, assert **no returned chunk
  or citation exceeds caller clearance**, across dense-only, sparse-only, and hybrid paths. Includes the
  "Northwind/restricted" cases from the forcing story. *Any leak fails the build.*
- **Hybrid retrieval IT:** a query with a rare keyword surfaces via sparse that dense alone misses (proves
  hybrid value); fusion ordering is deterministic.
- **Citation IT:** every answer's markers resolve to returned chunks; "no authorized info" path returns a
  grounded refusal, not a fabrication.
- **Prompt-injection IT (LLM01, D7):** poisoned doc instructing "ignore instructions / reveal restricted /
  exfiltrate" does **not** alter the answer, leak above-clearance content, or change citations.

### Live test (profile `live`, NOT in CI — reuses P0 pattern)
- End-to-end `POST /v1/query` against the real remote Ollama: returns a grounded, cited answer for a known
  Northwind question at `compliance` clearance; same query at `public` returns the refusal path.

### Manual quality baseline (recorded, not gated)
- ~10–15 representative Q&A run by hand; record a coarse faithfulness/grounded-citation pass-rate + p50/p95
  retrieval latency in `rag-engine/README.md`. This is the number P2 turns into a RAGAS threshold.

---

## 5. Task breakdown (ordered, independently committable)

1. **Schema + Flyway:** add Flyway; `atlas_document` / `atlas_chunk` tables + HNSW/GIN/clearance indexes;
   migration runs against Testcontainers. *(commit: `feat(rag): pgvector schema + Flyway migrations`)*
2. **Corpus fixtures:** finalize D1 subset (D-P1-7); author D2 overlay (memos/AML policy/SAR template with
   clearance tags); author D4 negative-access golden cases + D7 poisoned docs; D3 dev user→clearance map.
   *(commit: `chore(rag): P1 corpus + RBAC/poison/negative-access fixtures`)*
3. **Ingestion pipeline:** loader + `IngestionValidator` (LLM04) + chunker (D-P1-1) + embedding writer +
   `IngestionService` (idempotent full rebuild) + unit tests + ingestion IT.
   *(commit: `feat(rag): ingestion pipeline with provenance + integrity`)*
4. **Clearance + RBAC core:** `ClearanceLevel`, `RbacFilterBuilder`, clearance transport shim (D-P1-6) +
   unit tests. *(commit: `feat(rag): hierarchical clearance + RBAC filter`)*
5. **Hybrid retriever:** `HybridDocumentRetriever` (dense+sparse+RBAC predicate + RRF fusion, D-P1-3) +
   reranker seam (D-P1-4) + hybrid IT + **negative-access hard-gate IT (D4)**.
   *(commit: `feat(rag): hybrid retrieval with RBAC hard gate`)*
6. **Injection guardrail:** `InjectionGuardrail` (D-P1-5) + unit + poisoned-doc IT (D7).
   *(commit: `feat(rag): prompt-injection guardrail (LLM01)`)*
7. **QA + citations + API:** Advisor wiring, `CitationExtractor` (D-P1-8), `QueryController` +
   `AdminIngestController`; citation IT + live test (profile).
   *(commit: `feat(rag): grounded QA with inline citations + query API`)*
8. **Docs + baseline:** run manual baseline; update `rag-engine/README.md` (setup, run, results/metrics) +
   `docs/RUNBOOK.md` (ingest/query ops) + draft `docs/PORTFOLIO.md` bullet; log ADRs 0011…
   *(commit: `docs(rag): P1 baseline, README, RUNBOOK, ADRs`)*

---

## 6. Definition of Done (P1 — generic DoD from CLAUDE.md, instantiated)

- [ ] **Code complete & matches this spec.** Ingestion + hybrid+RBAC retrieval + cited QA + guardrail
      implemented in `rag-engine`; config env-swappable (no hardcoded models/creds).
- [ ] **Unit + integration tests pass in CI.** Including Testcontainers ITs. The **D4 negative-access RBAC
      test is a hard gate — 0 chunks/citations above clearance** across dense/sparse/hybrid paths.
- [ ] **Eval thresholds:** *N/A as automated gate in P1 (deferred to P2).* P1 records a **manual quality
      baseline** in the README; the **D7 prompt-injection IT** and **D4 RBAC IT** pass.
- [ ] **Roadmap P1 exit criteria met:** dataset finalized & ingested; ingestion integrity (LLM04); RBAC
      no-leak proven; hybrid (HNSW + tsvector) + reranking seam; inline citations; stack pinned
      (pgvector ≥0.7 / PG16, Spring AI Advisors); injection guardrail passes.
- [ ] **`rag-engine/README.md` updated** (purpose, architecture, setup, how to run tests, baseline metrics).
- [ ] **`docs/DECISIONS.md` updated** with ADRs 0011… for confirmed D-P1-1…D-P1-8.
- [ ] **Runs cleanly from scratch:** fresh clone + `.env` + `make -C infra up` + ingest → query returns a
      cited answer.
- [ ] **30-second demo path:** `POST /v1/query` (Northwind question) at `compliance` → cited answer; same at
      `public` → grounded refusal; documented one-liner.
- [ ] **Resume-ready quantified bullet** drafted in `docs/PORTFOLIO.md` (e.g. "permission-aware hybrid RAG
      over pgvector; 0 cross-clearance leaks across N negative-access cases; p95 retrieval <Xms").

---

## 7. Open questions for the owner (please confirm before I log ADRs)
The eight decisions in §3 each carry a recommendation. The four most consequential — **D-P1-4 (reranker in P1
or defer to P2)**, **D-P1-2 (RBAC mechanism)**, **D-P1-7 (corpus = FinanceBench vs EDGAR & size)**, and
**D-P1-6 (clearance transport shim)** — are surfaced as focused questions. The rest I'll proceed with as
recommended unless you object.
