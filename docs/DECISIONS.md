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
| 0020 | 2026-06-13 | Layer-1 ingestion form: committed FinanceBench evidence snippets | Accepted | P1 |
| 0019 | 2026-06-13 | Testcontainers ITs: docker-java API pin + exec-classifier jar | Accepted | P1 |
| 0018 | 2026-06-13 | Answer generation scope & citation granularity | Accepted | P1 |
| 0017 | 2026-06-13 | Final Layer-1 corpus subset (FinanceBench) | Accepted | P1 |
| 0016 | 2026-06-13 | Clearance transport in P1 (pre-IdP shim) | Accepted | P1 |
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
> decisions made while implementing P0.** **ADR-0011–0018 are the P1 grooming decisions** (`docs/phases/P1_SPEC.md`
> §3), confirmed with the project owner before P1 implementation begins. Each remains open to revision with a
> new superseding ADR if a later phase surfaces evidence against it.

---

## 2. Decisions

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
- **Date:** 2026-06-13 · **Status:** Accepted · **Phase:** P1 (superseded by ADR-0003's IdP in P3) · **Spec:** P1_SPEC §3 (D-P1-6)
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
