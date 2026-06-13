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
> decisions made while implementing P0.** Each remains open to revision with a new superseding ADR if a later
> phase surfaces evidence against it.

---

## 2. Decisions

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
