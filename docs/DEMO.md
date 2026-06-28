# Atlas — 3-Minute Demo Script

> The exact click-through that proves the four headline capabilities — **RBAC RAG**, an **agent action
> via MCP**, the **cost dashboard**, and the **eval/trace view** — in under three minutes, on a seeded,
> deterministic dataset. Automated form: `cd ui && npm run e2e:demo` (asserts every step below).

---

## 0. One-time setup (before the clock starts)

```bash
# Stack + observability (Postgres+pgvector, Redis, Langfuse, Prometheus, Grafana, Alertmanager)
make -C infra up
# Resume the GPU (ingestion + answers need embeddings/chat on OLLAMA_BASE_URL) — cost discipline: pause after
make -C infra gpu-up
# Run the backends (host dev) — or use the compose `app` profile
set -a && . ./.env && set +a
mvn -pl rag-engine spring-boot:run &   mvn -pl gateway spring-boot:run &
docker compose -f infra/docker-compose.yml --profile app up -d mcp-tools agents
# Seed the deterministic demo dataset (idempotent): ingest the two-layer RBAC corpus + list demo users
infra/deploy/seed-demo.sh
# Serve the UI
cd ui && npm run build && npm run preview   # http://localhost:4173
```

**Seeded dataset (what `seed-demo.sh` loads):**

- **Corpus (RBAC-tagged, 24 docs):** 12 **FinanceBench** evidence snippets (`public`/`analyst`) + 12 authored
  **Northwind Trading LLC** AML/compliance docs spanning all four clearances (`public` < `analyst` <
  `compliance` < `restricted`), incl. a SAR draft, OFAC screening, EDD/KYC, exception register — with synthetic
  PII for the redaction story. (`rag-engine/src/main/resources/corpus/`.)
- **Demo users (P1 dev shim, header `X-Atlas-User`):** `guest-public` → public · `analyst-bob` → analyst ·
  **`priya` → compliance** (protagonist) · `bsa-admin` → restricted.

> **Cost discipline:** `make -C infra gpu-down` when done — the GPU is the only paid dependency (RUNBOOK §11).

---

## 1. The click-through (target ≈ 2:45)

| Time     | Action                                                                                                                                           | What it proves                                                                                                                                                                             |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **0:00** | Open `http://localhost:4173/login` → click **Priya**                                                                                             | Login as a `compliance` user (RBAC identity).                                                                                                                                              |
| **0:20** | On **Chat**, tick **Investigate as governed action**; ask: _"Any AML exceptions breaching the threshold for Northwind this quarter?"_ → **Send** | **RBAC RAG**: retrieval is permission-filtered to what Priya may see.                                                                                                                      |
| **0:35** | Read the answer                                                                                                                                  | A **cited, AI-generated** answer ("**1 breaches the $10k threshold** [1]"), labelled **AI-generated** (EU AI Act transparency); the citation links to a `compliance` doc.                  |
| **0:50** | Click **▸ Execution trace**                                                                                                                      | **Trace view**: the `retrieve → assess → approve → act` timeline (NIST AI RMF traceability) with per-node badges (breach / citations).                                                     |
| **1:10** | See the **Approval required** card → click **Approve**                                                                                           | **Agent + MCP / HITL**: the agent proposes `open_draft_sar`; the human checkpoint gates the governed write. On approve it mints an aud-scoped (RFC 8707) token and calls the MCP tool.     |
| **1:30** | See the result                                                                                                                                   | The **`SAR-2026-000123`** draft ref + the completed trace.                                                                                                                                 |
| **1:40** | **Admin ▸ Audit**                                                                                                                                | The new **SUCCESS** row for `open_draft_sar` with **chain verified** (append-only, hash-chained audit).                                                                                    |
| **2:10** | **Admin ▸ Cost**                                                                                                                                 | **Cost dashboard**: the cost-reduction headline (**100%** cache+routing vs a **30%** target, _meets target: yes_) + the live Grafana cost/latency embed (uid `atlas-cost-p3`).             |
| **2:40** | **Admin ▸ Evals**                                                                                                                                | **Eval view**: the committed gate snapshot — **RAG gate PASS** (RAGAS + **100% adversarial**) and **Agent gate PASS** (trajectory + HITL/authorization, 0 unapproved/unauthorized writes). |

**Optional 20-second RBAC kicker:** log out → log in as **`analyst-bob`** → ask the same question → the
compliance/restricted exceptions are **absent** and there is **no Admin tab** (the negative-access path).

**Where the trace/eval also live (for a deeper dive):**

- **Langfuse** (`http://localhost:3000`): the `gen_ai.*` span tree for the query (gateway → rag-engine → agent),
  stitched by the `X-Request-Id` correlation id.
- **Grafana** (`http://localhost:3001`): _Atlas — Cost-aware Gateway_ (cost/token/latency **p50+p95**),
  _Eval & Observability_ (RAGAS trend + adversarial pass-rate), _Agent Orchestrator_.
- **Alertmanager** (`http://localhost:9093`): the cost / error-rate / breaker / eval-gate alerts (P6).

---

## 2. Run it automated (CI-grade, no GPU)

The same path is a Playwright spec against the production build with pinned mocks — deterministic, GPU-free:

```bash
cd ui && npm run e2e:demo          # ui/e2e-demo/forcing-story.demo.spec.ts
```

It asserts every row above: the cited answer, the trace steps, the `open_draft_sar` HITL approval, the
`SAR-2026-000123` audit SUCCESS row (chain verified), the **100%** cost-reduction panel, and the two green
gate badges. Use this as the reliable fallback if the live GPU is paused during a presentation.
