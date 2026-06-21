# P4 — Agent Orchestrator (LangGraph) + MCP Tool Servers — SPEC

> Status: **COMPLETE — implemented & verified 2026-06-21** (built across 14 commits on `docs/p4-grooming`;
> the §6 Definition of Done is checked honestly, with deviations noted inline). Full suite green: rag-engine
> 90u+40IT · gateway 66u+14IT · mcp-tools 12u+21IT · agents 60 tests (+3 live-gated, skipped offline) ·
> agent eval gate 12/12 · evals 63 + both RAG gates · gpu-helper 24 · ruff clean. The live agent-path
> invariant gate (§4.3) runs in the live lane (running stack + GPU), like the P2/P3 live calibration.
> All §3 decisions (D-P4-1…10) + the §7 clarifications (Q5 single configurable breach threshold; Q6 exactly
> one write tool) are **owner-confirmed and logged as ADR-0041–0050** in `docs/DECISIONS.md`. Implementation
> followed the §5 task breakdown (Task 0 = the Spring AI 1.1.x bump).
> Date drafted: 2026-06-21 · Date completed: 2026-06-21.
> **Updated 2026-06-21 with §8 — a web-validated (June 2026) P4 gap analysis** (8 refinements, G-P4-1…8, folded
> into the sections below + a new **OWASP Agentic Top 10 (2026) → P4 control map**). The validation pinned the
> **MCP spec to `2025-11-25`** (RFC 8707 / OAuth Resource Server from `2025-06-18`), surfaced one new decision —
> **D-P4-10, the Spring AI version bump** the Streamable-HTTP MCP server stack requires — and enriched the
> agent-eval metric set to be **trajectory-first**.
> Phase owner doc set: `CLAUDE.md` · `docs/ROADMAP.md` (§2 P4, §3 R4, §6 G3/G8/G9, §7.2 Agentic 2026 + LLM06) ·
> `docs/DECISIONS.md` (ADR-0001 split, ADR-0002 pgvector, ADR-0003 sim-IdP, ADR-0005 models, ADR-0034 verified-clearance
> trust boundary, ADR-0035 router, ADR-0024 eval thresholds) · `docs/phases/P3_SPEC.md` (the Gateway this phase
> sits behind) · `docs/RUNBOOK.md`.

This phase turns **answers into governed actions**. It adds the two stub modules the whole roadmap has been
building toward: the **Agent Orchestrator** (`/agents`, Python/LangGraph) that plans and executes the
conditional second half of the forcing story, and a **governed MCP Tool Server** (`/mcp-tools`, Spring Boot)
that exposes a single state-changing enterprise action — **open a draft Suspicious Activity Report (SAR)** —
behind OAuth 2.1, a per-call clearance re-check, a **mandatory human-in-the-loop approval**, and an
**append-only, tamper-evident audit log**.

It completes the second half of Priya's story:

> *"…and if any [AML exception] breaches the reporting threshold, open a draft Suspicious Activity Report for
> my review."*

The agent **retrieves through the P3 Gateway** (reusing verified-clearance auth, cost-aware routing, semantic
cache, PII redaction — all frozen), decides whether the breach condition holds, and — only with Priya's
explicit approval — calls the MCP tool to create the draft SAR. Every step is traced (Langfuse) and the agent
run is **evaluated as a CI merge gate** (per CLAUDE.md: *evals before/around agents*).

It does **not** build the React UI (P5), does **not** change P1 retrieval/RBAC or P3 gateway behaviour, and
ships **exactly one** governed write tool — breadth is deliberately out of scope.

---

## 1. Scope

### In scope
1. **Agent Orchestrator service (`/agents`, Python / LangGraph) — NEW.** A standalone service exposing a run
   API (`POST /v1/agent/runs`, `POST /v1/agent/runs/{id}/resume`). It hosts a **planner→executor** state graph
   that: (a) retrieves grounded, RBAC-filtered context by calling the **P3 Gateway** `/v1/query`; (b) evaluates
   the conditional ("does any exception breach the reporting threshold?"); (c) on a breach, plans a draft-SAR
   action; (d) **pauses for human approval** before any write; (e) on approval, calls the MCP tool; (f) returns
   a cited answer + the draft-SAR reference + an execution trace.
2. **Durable agent memory.** LangGraph **Postgres checkpointer** reusing the P0 Postgres (separate `agent`
   schema), so a run can **resume after interrupt or process restart**.
3. **Human-in-the-loop (HITL) checkpoint.** No state change occurs without an explicit approval step,
   implemented as a LangGraph `interrupt` → `Command(resume)` gate (the authoritative decision point), with the
   MCP tool independently refusing an unapproved write (defense-in-depth). MCP **elicitation** is available for
   mid-task field confirmation.
4. **Governed MCP Tool Server (`/mcp-tools`, Spring Boot) — NEW.** Exposes **one** write tool —
   `open_draft_sar` — over **MCP Streamable HTTP**, secured as an **OAuth 2.1 resource server** (RFC 8707
   resource indicators / audience-restricted tokens). The tool performs a governed write to a `sar_draft`
   Postgres table and returns a draft reference.
5. **Per-call authorization re-check (LLM06, defense-in-depth with P1 RBAC).** The tool re-derives the caller's
   clearance from the validated token and **refuses** to act for a caller below `compliance` — independently of
   any upstream check.
6. **Append-only, tamper-evident audit log.** Every tool invocation (attempt, approval, success, failure)
   writes an immutable, **hash-chained** Postgres audit row; UPDATE/DELETE are revoked for the app role; a
   chain-verification utility proves tamper-evidence; the log is queryable for compliance review.
7. **Identity propagation.** The sim-IdP (ADR-0003) is extended to mint **resource-scoped** tokens
   (`aud` = the MCP resource server) so the verified clearance flows client → agent → MCP tool and is
   re-validated at the tool.
8. **Observability + agent evaluation (CI-gated).** Agent runs traced in Langfuse (OTel GenAI / MCP spans);
   a Python **agent eval set** (task scenarios) scored for **task success**, **tool-call correctness**, and the
   **HITL/authorization hard gates** — wired as a **merge-blocking** gate, mirroring P2/P3 (cassette-replay in
   CI, live calibration on the GPU).
9. **Docs + config:** `agents/README.md`, `mcp-tools/README.md`, `docs/RUNBOOK.md` (run/approve/audit-query),
   `docs/DECISIONS.md` (ADR-0041…), `docs/PORTFOLIO.md` bullet; `.env.example` extended with all P4 vars;
   `/mcp-tools` added to the Maven reactor; `/agents` as a `uv` project (mirroring `/evals`).

### Non-goals (explicit — prevent scope creep)
- **No React UI / admin console.** The agent run + approval are exercised via the run API + tests + a scripted
  demo. Visual chat/citations/trace surfacing is **P5**.
- **No second/third MCP tool, no tool marketplace.** Exactly **one** governed write tool (`open_draft_sar`) +
  (at most) read-only helpers it needs. Additional enterprise actions are post-P4.
- **No change to P1 retrieval/RBAC/chunking/embeddings/guardrails or P3 gateway behaviour.** Both are frozen;
  the agent is a new *consumer* of the Gateway. Any regression in P1 D4/D7 or P3 hard gates blocks this phase.
- **No real OIDC IdP / token service.** ADR-0003 stands — the sim-IdP is extended to mint resource-scoped
  tokens; no real authorization server, consent screen, or refresh-token rotation beyond proving the resource-
  server enforcement path.
- **No external/real SAR filing, FinCEN integration, or PII-bearing real data.** The "SAR" is a draft row in
  our Postgres, on synthetic Layer-2 data; it is never transmitted anywhere.
- **No multi-agent swarm / autonomous long-horizon planning.** A single planner→executor graph for one
  conditional action. No self-spawning agents, no unbounded tool loops (step/iteration caps enforced).
- **No fine-tuning / training a planner model.** Reasoning uses the existing self-hosted Ollama tiers
  (ADR-0005 / ADR-0035), env-swappable.
- **No Spring Boot 4 / Spring AI 2.0 migration.** P4 bumps Spring AI to **1.1.x on Spring Boot 3.x** only (D-P4-10).
  Spring AI 2.0 (which requires Boot 4 / Framework 7 / Jakarta EE 11 / Jackson 3) is a deliberate, dedicated
  future-work track — explicitly **out of P4 scope** (planned against the Boot 3.5 EOL 2026-06-30, not rushed
  into this phase).
- **No production deploy.** Local Docker Compose + CI only (deploy is **P5**).
- **No routing of agent traffic through the Gateway as a gateway route.** The agent is a standalone service in
  P4 that *calls* the Gateway; exposing the agent behind the Gateway/UI is **P5** (D-P4-5).

---

## 2. Design

### 2.1 Language split (Java vs Python) — and why
P4 is the phase that **exercises the polyglot seam on purpose** (ADR-0001): the agent-orchestration ecosystem
is Python-first; the governed enterprise tool is the Java/Spring "moat."

- **Python / LangGraph (`/agents`) — the orchestration brain.** Planner→executor graph, durable Postgres
  checkpointer, `interrupt`/`resume` HITL, the **MCP client** that calls the Java tool server, and the HTTP
  client that calls the Gateway. Rationale: LangGraph (1.x/2.0) is the production agent framework with
  first-class durable checkpointing + interrupt/resume HITL (ROADMAP §6 G3/G8) — this is exactly where Python
  is best-in-class and where the in-demand "agent orchestration" skill is evidenced.
- **Java / Spring Boot (`/mcp-tools`) — the governed action surface (the moat).** MCP server (Streamable HTTP),
  OAuth 2.1 resource server (Spring Security), the `open_draft_sar` tool, per-call clearance re-check, the
  append-only hash-chained audit log, and the `sar_draft` write. Rationale: "MCP tool server design (governed
  actions)" + "MCP transport/auth (Streamable HTTP, OAuth 2.1)" are the Java/Spring skills the project exists to
  prove; keeping the *write* and its governance in Spring (transactional, audited, secured) is the honest
  production shape and reuses the Maven reactor + Postgres.
- **Java (`gateway`, `rag-engine`) — reused, not extended.** The agent calls the **existing** Gateway
  `/v1/query`; no new gateway/rag code is required (additive auth-scope only — minting resource-scoped tokens
  in the sim-IdP, which lives in the Gateway).
- **Python (`/evals`) — extended.** The P2 harness gains an **agent eval lane** (scenario scorers + the HITL/
  authz hard gates), reusing the cassette-replay + live-calibration + Langfuse-sync machinery already built.

**Boundary contracts (all HTTP, no shared process):** client → `agents` (HTTP/JSON + Bearer JWT) → `gateway`
`/v1/query` (HTTP/JSON + Bearer JWT) and → `mcp-tools` (**MCP Streamable HTTP** + Bearer JWT, `aud`=mcp). The
modules never import one another.

### 2.2 Component breakdown
```
agents/                                  # Python / LangGraph — orchestration brain (NEW module, uv project)
  app/
    api.py                  # FastAPI: POST /v1/agent/runs, POST /v1/agent/runs/{id}/resume, GET .../{id}, /healthz
    graph.py                # LangGraph StateGraph: plan → retrieve → assess → (breach?) → approve(interrupt) → act
    state.py                # AgentState (typed): query, clearance, contexts, citations, breach, plan, approval, result
    nodes/
      planner.py            # builds the plan for the forcing query (retrieve → assess → conditional SAR)
      retrieve.py           # calls Gateway POST /v1/query (verified-clearance Bearer); returns cited contexts
      assess.py             # deterministic breach check over retrieved exceptions (threshold from config)
      act_sar.py            # MCP client → open_draft_sar tool; only reachable AFTER the approval gate
    hitl.py                 # interrupt() before any write; Command(resume) carries the approval decision
    mcp_client.py           # MCP Streamable HTTP client; attaches aud-scoped Bearer; elicitation handler
    checkpointer.py         # langgraph-checkpoint-postgres over the P0 Postgres ('agent' schema)
    tracing.py              # Langfuse / OTel GenAI + MCP spans; links run_id → request trace
    config.py               # env: GATEWAY_BASE_URL, MCP_BASE_URL, model tier, thresholds, step caps (12-factor)

mcp-tools/                               # Java / Spring Boot — governed MCP tool server (NEW Maven module)
  src/main/java/com/atlas/mcptools/
    McpToolsApplication.java
    config/
      ResourceServerConfig    # Spring Security: OAuth 2.1 resource server; validate sig+exp+iss+aud (RFC 8707)
      McpServerConfig         # Spring AI MCP server, Streamable-HTTP WebMVC (protocol=STREAMABLE; SSE deprecated)
    tool/
      DraftSarTool            # @McpTool open_draft_sar(account, period, rationale, citations) → structured output
      SarDraftService         # transactional write to sar_draft (status=DRAFT); links citations + run_id
      ClearanceRecheck        # re-derive clearance from Authorization (TransportContextExtractor); refuse < compliance (ASI03/LLM06)
    audit/
      AuditService            # append-only, hash-chained write per invocation (attempt/approve/ok/fail)
      AuditChainVerifier      # recompute + verify the hash chain (tamper-evidence)
  src/main/resources/db/migration/
    V2__atlas_agent_audit_schema.sql   # sar_draft + tool_audit (append-only grant); 'agent' schema bootstrap

gateway/ (Java — additive only)
  auth/
    ResourceScopedTokenIssuer # sim-IdP mints aud-restricted token for the MCP resource server (RFC 8707)

evals/ (Python — extended, no hot-path change)
  atlas_evals/datasets/agent.py        # agent task scenarios (forcing story + variants)
  atlas_evals/metrics/agent_scorer.py  # task-success, tool-call-correctness, HITL/authz hard gates
  atlas_evals/agent_gate.py            # cassette-replay agent gate (merge-blocking) + live calibration

infra/
  docker-compose.yml        # + agents (python) + mcp-tools (java) services; reuse Postgres/Redis/Langfuse
  grafana/                  # + agent panel: run count, tool-call rate, approval latency, failures
```

### 2.3 Data models / schemas

**Agent run request/response (`POST /v1/agent/runs`, client-facing; `Authorization: Bearer <jwt>`).**
```jsonc
// request
{ "query": "Summarize open AML exceptions for Northwind this quarter, and if any breach the reporting
             threshold, open a draft SAR for my review.",
  "account": "Northwind", "period": "2026-Q2" }
// response (when the graph hits the HITL gate)
{ "runId": "run_…", "status": "AWAITING_APPROVAL",
  "answer": "3 open AML exceptions for Northwind in Q2; 1 breaches the $10k reporting threshold …",
  "citations": [ { "n": 1, "documentId": "l2-northwind-amlexc-q2", "clearance": "compliance", "snippet": "…" } ],
  "proposedAction": { "tool": "open_draft_sar", "args": { "account": "Northwind", "period": "2026-Q2",
                      "rationale": "Exception #2 exceeds threshold", "citations": [1] } },
  "trace": [ { "node": "retrieve", "ms": 2810 }, { "node": "assess", "breach": true }, { "node": "approve" } ] }
```

**Resume (`POST /v1/agent/runs/{id}/resume`).**
```jsonc
// request — the human decision (Command(resume) payload)
{ "approved": true, "note": "Reviewed; proceed" }
// response (on approval)
{ "runId": "run_…", "status": "COMPLETED",
  "action": { "tool": "open_draft_sar", "draftRef": "SAR-2026-000123", "status": "DRAFT" },
  "auditRef": "audit_…" }
// on rejection → status:"REJECTED", no tool call, audit row records the declined action
```

**MCP tool contract — `open_draft_sar` (input schema).**
```jsonc
{ "name": "open_draft_sar",
  "description": "Create a DRAFT Suspicious Activity Report for human review. Never auto-files.",
  "inputSchema": {
    "account":   { "type": "string" },
    "period":    { "type": "string", "pattern": "^[0-9]{4}-Q[1-4]$" },
    "rationale": { "type": "string", "maxLength": 2000 },
    "citations": { "type": "array", "items": { "type": "integer" } } },
  "requiresApproval": true }            // tool-side precondition; refuses if no approval context present
// returns: { "draftRef": "SAR-2026-000123", "status": "DRAFT", "createdAt": "…" }
```

**`sar_draft` table (Postgres, `agent` schema).**
```sql
sar_draft(
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  draft_ref TEXT UNIQUE NOT NULL,           -- SAR-2026-000123
  account TEXT NOT NULL, period TEXT NOT NULL,
  rationale TEXT NOT NULL,
  citations JSONB NOT NULL,                  -- source doc refs (grounding/provenance)
  clearance TEXT NOT NULL,                   -- caller clearance at write time (must be 'compliance'+)
  run_id TEXT NOT NULL,                      -- originating agent run
  status TEXT NOT NULL DEFAULT 'DRAFT',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now())
```

**`tool_audit` table (append-only, hash-chained).**
```sql
tool_audit(
  seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  run_id TEXT NOT NULL, tool TEXT NOT NULL,
  phase TEXT NOT NULL,                       -- ATTEMPT | APPROVED | REJECTED | SUCCESS | DENIED | ERROR
  caller TEXT NOT NULL, clearance TEXT NOT NULL,
  args_digest TEXT NOT NULL,                 -- hash of args (not raw PII; LLM02-consistent)
  result_ref TEXT,                           -- draft_ref on success
  prev_hash TEXT NOT NULL,                   -- chain link
  row_hash  TEXT NOT NULL)                   -- sha256(prev_hash || canonical(row fields))
-- app DB role: GRANT INSERT, SELECT; REVOKE UPDATE, DELETE  → append-only at the DB layer
```

**Resource-scoped token (sim-IdP extension, RFC 8707).** Same JWT as ADR-0034 plus an audience binding:
```jsonc
{ "sub": "priya", "clearance": "compliance", "iss": "atlas-sim-idp",
  "aud": "atlas-mcp-tools",                  // resource indicator → the MCP resource server validates this
  "iat": 1750000000, "exp": 1750003600, "jti": "…" }
```

### 2.4 Key interfaces & contracts

**Retrieval contract (agent → Gateway).** The agent calls the **P3 Gateway** `POST /v1/query` with the caller's
Bearer JWT (verified-clearance trust boundary, ADR-0034) — it never calls `rag-engine` directly and never
sets a clearance header. It consumes the existing §2.3 P3 response (answer + citations + cost/cache/routing),
so all RBAC, cost-routing, caching, and PII-redaction guarantees are inherited unchanged.

**Action contract (agent → MCP tool).** The agent's MCP client connects over **Streamable HTTP** (MCP spec
**`2025-11-25`**, the current stable; OAuth Resource Server classification + RFC 8707 Resource Indicators +
elicitation + **structured tool output** landed in `2025-06-18`) and attaches a Bearer token whose `aud` =
`atlas-mcp-tools`. On the server, a `TransportContextExtractor` lifts the `Authorization` header into the
`McpTransportContext`; the Spring Security OAuth 2.1 resource server validates **signature + `exp` + `iss` +
`aud`** (RFC 8707), re-derives clearance, **re-checks authorization per call** (refuse `< compliance` → MCP
error + `DENIED` audit row), then executes inside a transaction that writes both `sar_draft` and the `SUCCESS`
audit row atomically. The tool returns **structured output** (`{draftRef, status, createdAt}`), not free text.

**Replay / single-use approval contract (ASI07 inter-agent comms).** The approval that unlocks the write is
**single-use and task-scoped**: the resume payload is bound to the originating `run_id` + the checkpoint
version, the token carries a unique `jti` + short `exp`, and a consumed approval/`jti` cannot be replayed to
authorize a second or mutated write (the "replayed approval" attack). Channels are authenticated (Bearer +
`aud`); no plaintext, unauthenticated agent↔tool traffic.

**HITL contract (the safety invariant).** The `act_sar` node is **structurally unreachable** until the graph
passes the `interrupt` approval gate: the planner routes breach→`approve`→(resume)→`act_sar`. `interrupt()`
suspends the run and **persists state via the checkpointer**; the run resumes only on
`Command(resume={"approved": true})`. The MCP tool *additionally* refuses any call lacking an approval context
(belt-and-suspenders). **No path produces a write without a recorded human approval.**

**Authorization contract (defense-in-depth, LLM06).** Authorization is checked in **three** independent
places: (1) the Gateway resolves verified clearance for retrieval (P3); (2) retrieval itself is RBAC-filtered
(P1 — a sub-`compliance` caller never even sees the breaching exception); (3) the MCP tool re-derives clearance
from its own validated token and refuses to act below `compliance`. Removing any one must not enable an
unauthorized write (each is independently tested).

**Audit contract.** Every tool invocation emits ≥1 immutable audit row covering its lifecycle
(ATTEMPT → APPROVED/REJECTED → SUCCESS/DENIED/ERROR). Rows are hash-chained (`row_hash = sha256(prev_hash ||
canonical_fields)`); `AuditChainVerifier` recomputes the chain and flags any break. DB-level append-only
grants make UPDATE/DELETE impossible for the app role. The log is queryable by `run_id`, `caller`, `tool`.

**Tracing/metering contract.** Agent runs emit OTel GenAI + MCP spans (ROADMAP §7.3): a root `run` span with
child `retrieve`, `assess`, `approve`, `act` spans; the MCP call carries `gen_ai.*`/MCP attributes so the
trace stitches into the existing Langfuse view alongside the Gateway/RAG spans. Grafana gains an agent panel
(runs, tool-call rate, approval latency, failures).

### 2.5 Request / data flow

**Forcing story (happy path):**
1. **Run start:** client `POST /v1/agent/runs` with Bearer JWT → agent resolves caller from the token; a new
   `run_id` + checkpoint is created.
2. **Plan:** `planner` lays out retrieve → assess → (conditional) SAR.
3. **Retrieve:** `retrieve` calls Gateway `/v1/query` (verified clearance) → RBAC-filtered, cited context on
   the open AML exceptions for the account/period.
4. **Assess:** `assess` deterministically checks the retrieved exceptions against the configured reporting
   threshold → `breach = true/false` (grounded in citations, not free-LLM judgement).
5. **Branch:** no breach → return the cited summary, `status: COMPLETED`, no action. Breach → continue.
6. **HITL gate:** the graph `interrupt()`s with a `proposedAction`; state is checkpointed;
   response = `status: AWAITING_APPROVAL` (§2.3). **No write has happened.**
7. **Approve (separate call):** human `POST .../resume {approved:true}` → `Command(resume)` rehydrates state
   from the checkpoint.
8. **Act:** `act_sar` invokes the MCP `open_draft_sar` tool over Streamable HTTP (aud-scoped Bearer).
9. **Tool governance:** resource server validates token + aud; `ClearanceRecheck` confirms `compliance`;
   transactional write of `sar_draft` (status DRAFT) + `SUCCESS` audit row (chained).
10. **Return:** `status: COMPLETED` with `draftRef` + `auditRef`; spans flushed to Langfuse; Grafana updates.

**Failure / safety branches:**
- **Rejection:** `approved:false` → no tool call; `REJECTED` audit row; `status: REJECTED`.
- **Restart mid-interrupt:** process dies after step 6; on restart, `.../resume` resumes from the durable
  checkpoint (resume-after-restart test).
- **Sub-`compliance` caller:** retrieval returns no breaching chunk (P1 RBAC) → no breach → no action; even a
  forced tool call is `DENIED` at the resource server (LLM06). 0 unauthorized writes.
- **Injection in source docs attempting to trigger/skip approval (LLM01/LLM06):** P1 guardrail strips it at
  retrieval; the breach decision is deterministic over citations, not instructions in the text; the HITL gate
  is graph-structural, not promptable.
- **Tool/timeout failure:** bounded retries + step cap; `ERROR` audit row; run ends in a clear failed state
  (no partial write — transactional).

**The hard problems this phase must answer:**
- **No unauthorized / unapproved action (R4, LLM06):** the scariest failure. Answered by the graph-structural
  HITL gate + the tool-side approval precondition + triple authorization + the unauthorized-action eval gate.
- **Durable, resumable agency (G8):** a real production agent survives restart mid-decision — proven by the
  Postgres checkpointer resume test.
- **Tamper-evident governance (G9):** compliance needs to trust the trail — proven by the append-only,
  hash-chained audit log + chain verifier.
- **Agent quality is measurable (CLAUDE.md):** task success / tool-call correctness scored as a merge gate, so
  agentic behaviour is non-regressable like RAG quality.

**Security mapping touched in P4 (OWASP Top 10 for Agentic Applications 2026 — full map in §8.2):** ASI01 goal
hijack (P1 injection guardrail on retrieved docs + deterministic `assess` + immutable graph structure), ASI02
tool misuse (one least-privilege tool, no tool-chaining, the `proposedAction` shown at the gate is a *dry-run
preview*), ASI03 identity/privilege abuse (task-scoped short-lived RFC 8707 tokens + per-call clearance
re-check + no credential sharing), ASI04 agentic supply chain (only our own pinned/signed MCP server; AIBOM
from P0), ASI06 memory poisoning (validated, per-run-isolated, trusted-write Postgres checkpoints), ASI07
inter-agent comms (authenticated channels + single-use replay-protected approval), ASI08 cascading failures
(circuit breaker + planning-separated-from-execution + HITL governance gate), ASI09 human-agent trust (the gate
surfaces **provenance/citations**, not just a confident recommendation), ASI10 uncontrolled scaling (step/
iteration caps, no sub-agent spawning, reused P3 budget caps). Plus LLM06 excessive agency (the agentic lens of
ASI02/ASI03).

### 2.6 Model inventory (env-swappable; CLAUDE.md: never hardcoded)
P4 adds **no new default model**; it **routes agent reasoning** to an existing tier (D-P4-2).

| Role | Full model (proposed) | Env var | Served on | Status |
|---|---|---|---|---|
| Agent reasoning / tool-calling (default) | `qwen2.5:7b-instruct` (tier2, already pulled P2/P3) | `ATLAS_AGENT_MODEL` | Cloud Ollama GPU | proposed D-P4-2 |
| Sub-steps / cheap calls | `qwen2.5:3b-instruct` (tier1) | `OLLAMA_CHAT_MODEL` | Cloud Ollama GPU | reused, ADR-0005 |
| Demo-only frontier (off by default) | `gpt-4o` *(swappable)* | `ATLAS_ROUTER_FRONTIER_MODEL` | Cloud frontier API | reserved (P5 demo) |

- **Why tier2 for the agent:** small models are unreliable at multi-tool planning + structured tool-args;
  routing agent reasoning to `qwen2.5:7b` raises task-success while staying self-hosted + cheap and honoring the
  eval floor (extends ADR-0035). The cost delta vs tier1 is recorded for the portfolio.
- **GPU footprint:** `qwen2.5:3b` (~2–3 GB) + `nomic-embed-text` (~0.5 GB) + `qwen2.5:7b` (~5 GB q4) ≈ **~8 GB**
  — within the L4/A5000-class GPU (ADR-0006), unchanged from P3.
- **Does the GPU need to be live?** Same pattern as P2/P3: the **CI agent gate runs on cassettes (GPU OFF)**;
  **dev + live agent-eval calibration need the GPU ON** (auto-paused via the P2 `infra/gpu` helper). MCP-tool,
  audit, authz, and HITL-structure tests are **model-free**.

---

## 3. Decisions to make now

> Locked and **not** re-opened: ADR-0001 (Java+Python split), ADR-0002 (pgvector/Postgres reuse), ADR-0003
> (sim-IdP direction), ADR-0005 (models/dim), ADR-0006 (GPU), ADR-0034 (verified-clearance trust boundary),
> ADR-0024 (eval thresholds), and all P1/P2/P3 retrieval/RBAC/cost ADRs. Below are the **open P4 choices.** On
> your confirmation each is logged as a new ADR in `docs/DECISIONS.md`. The five starred (★) are the
> most consequential and were surfaced as focused questions after this spec.
>
> **ALL DECISIONS OWNER-CONFIRMED & LOGGED 2026-06-21 (ADR-0041–0050).** Every §3 choice matched the
> recommendation: **D-P4-1 → (a)** planner→executor graph (ADR-0041) · **D-P4-2 → (a)** tier2 `qwen2.5:7b`
> (ADR-0042) · **D-P4-3 → (a)** Spring AI MCP server WebMVC (ADR-0043) · **D-P4-4 → (a)** graph `interrupt`
> authoritative gate + tool precondition (ADR-0044) · **D-P4-5 → (a)** standalone agent calling the Gateway
> (ADR-0045) · **D-P4-6 → (a)** RFC 8707 resource-scoped tokens + replay-protected approval (ADR-0046) ·
> **D-P4-7 → (a)** Postgres checkpointer, `agent` schema (ADR-0047) · **D-P4-8 → (a)** append-only hash-chained
> audit log (ADR-0048) · **D-P4-9 → (a)** `sar_draft` transactional write (ADR-0049) · **D-P4-10 → (a)
> re-scoped to Spring AI 1.1.x on Spring Boot 3.x** (not 2.0/Boot 4 — deferred; ADR-0050). **§7 clarifications:
> Q5 → single configurable breach threshold; Q6 → exactly one write tool** (both ADR-0049).

**★ D-P4-1 — Agent topology / graph shape**
- (a) **Explicit LangGraph planner→executor state graph** with a conditional `breach?` edge, a tool node, and a
  graph-structural `interrupt` gate before any write. *(recommended)* — Transparent and traceable; the
  conditional and the HITL gate are *real graph structure* (not LLM whim), which is exactly what makes the
  safety invariant testable and the trace portfolio-worthy. *Trade-off: more graph wiring than a prebuilt agent.*
- (b) **Prebuilt ReAct agent** (`create_react_agent` + tools) — least code, but the plan/branch lives implicitly
  in the LLM loop; harder to place a *deterministic* HITL gate before the write and harder to score tool-call
  correctness.
- (c) **Supervisor multi-agent** (retriever-agent + action-agent) — impressive, but over-engineered for one
  conditional action; more cost/latency/nondeterminism, off-thesis for a single forcing story.
- **Recommendation: (a)** — the explicit graph is what lets P4 *prove* "no write without approval."

**★ D-P4-2 — Agent reasoning model**
- (a) **Route agent reasoning to tier2 `qwen2.5:7b-instruct`** (already pulled), tier1 for cheap sub-steps,
  frontier reserved for the P5 demo. *(recommended)* — reliable tool-calling/planning matters more for agents
  than raw token cost; still self-hosted, cheap, and eval-floor-honoring; extends ADR-0035.
- (b) **Keep tier1 `qwen2.5:3b` for everything** — cheapest, but 3B models are flaky at multi-tool planning +
  structured args → more failed runs, fighting the task-success gate.
- (c) **Frontier model for the agent** — best reasoning, but breaks the cost thesis + self-hosted invariant;
  reserve strictly for the P5 multimodal/demo lane.
- **Recommendation: (a)** — record the tier1→tier2 cost/quality delta in the portfolio.

**★ D-P4-3 — MCP server implementation stack (Java)**
- (a) **Spring AI MCP Server (`spring-ai-starter-mcp-server-webmvc`) on Streamable HTTP** in `/mcp-tools`.
  *(recommended)* — idiomatic Java/Spring (the moat), annotation-driven `@Tool`, integrates Spring Security as
  the OAuth 2.1 resource server, reuses the Maven reactor + Postgres + WebMVC idiom (matches the P3 gateway
  choice). *Trade-off: track Spring AI MCP-server maturity / spec currency.*
- (b) **Official MCP Java SDK directly** — more control, but more boilerplate and weaker "Spring AI" portfolio
  story; re-implements what the starter gives.
- (c) **Python MCP server (FastMCP) co-located with the agent** — fastest to write, but abandons the Java/Spring
  "governed MCP tool server" moat the roadmap exists to prove, and splits governance away from the transactional
  DB write.
- **Recommendation: (a)**.

**★ D-P4-4 — Human-in-the-loop placement & mechanism**
- (a) **Authoritative gate in the LangGraph graph (`interrupt`→`Command(resume)`), durably checkpointed, with
  the MCP tool independently enforcing a "requires-approval" precondition** (defense-in-depth); MCP
  **elicitation** used only for mid-task *field* confirmation. *(recommended)* — the pause survives restart; the
  graph is the single, traceable, evaluable decision point; the tool still refuses an unapproved write.
- (b) **HITL only via MCP elicitation** (server asks the user) — native MCP, but the pause lives in the
  tool/transport, is harder to checkpoint durably, harder to evaluate as graph state, and couples HITL to the
  client's elicitation support.
- (c) **HITL only at the tool** (tool returns "pending", external approve call) — simple, but the agent loses
  durable resumable state and the approval falls outside the agent trace.
- **Recommendation: (a)** — graph-structural gate is the strongest, most demonstrable safety story; elicitation
  is complementary, not the primary gate.

**★ D-P4-5 — Agent placement: standalone service vs behind the Gateway**
- (a) **Standalone Python agent service** (`POST /v1/agent/runs` + resume) that *calls* the Gateway `/v1/query`
  for retrieval and the MCP server for actions; exposing the agent behind the Gateway/UI is deferred to **P5**.
  *(recommended)* — keeps P4 focused on agents+MCP; the agent still consumes the governed Gateway path (RBAC,
  cost, cache, PII all reused); clean seam for the P5 UI.
- (b) **Route agent traffic through the Gateway now** (`gateway → agent`) — more "single front door" purity, but
  adds gateway routing/streaming work that belongs to P5 and isn't needed to prove the agent thesis.
- (c) **Agent calls `rag-engine` directly** (bypass Gateway) — least integration, but discards P3's verified-
  clearance/cost/cache controls and weakens the security story.
- **Recommendation: (a)**.

**D-P4-6 — Clearance / identity propagation to the MCP tool (OAuth 2.1)**
- (a) **Audience-restricted Bearer tokens (RFC 8707 resource indicators):** sim-IdP mints a token with
  `aud=atlas-mcp-tools`; the agent forwards it; the MCP resource server validates sig+exp+iss+**aud** and
  re-derives clearance. *(recommended)* — exactly the current MCP security model the roadmap calls for (§6 G2);
  proves the "OAuth 2.1 resource server" skill; defense-in-depth with P1 RBAC.
- (b) **Reuse the gateway internal-clearance signed header (ADR-0034 mechanism)** for the agent→MCP hop —
  consistent with P3, less new code, but does **not** demonstrate the OAuth 2.1 resource-server / RFC 8707
  skill the roadmap specifically wants.
- (c) **Network-trust only** — unacceptable for a governed write (LLM06).
- **Recommendation: (a)** — extend the sim-IdP (ADR-0003) to mint resource-scoped tokens.

**D-P4-7 — Durable checkpointer store**
- (a) **Postgres checkpointer (`langgraph-checkpoint-postgres`) reusing the P0 Postgres, in a separate `agent`
  schema/DB.** *(recommended)* — one datastore (ADR-0002 ethos), production-shaped resume-after-restart, no new
  infra. *Trade-off: schema/migration ownership across two modules — isolated via a dedicated schema.*
- (b) **SQLite checkpointer** — simplest in dev, but not the shared-prod story and not multi-instance safe.
- (c) **In-memory checkpointer** — fails the "durable, resume after interrupt/restart" DoD.
- **Recommendation: (a)**.

**D-P4-8 — Audit-log tamper-evidence mechanism (G9)**
- (a) **Append-only Postgres table with a hash-chain** (`prev_hash`/`row_hash`) + DB-level INSERT/SELECT-only
  grant (REVOKE UPDATE/DELETE for the app role) + a chain verifier. *(recommended)* — tamper-evident +
  queryable + cheap + reuses Postgres; the verifier is a clean compliance demo. *Trade-off: chain-maintenance
  code.*
- (b) **Append-only table, revoked UPDATE/DELETE only (no hash chain)** — simpler + queryable, but not
  tamper-*evident* (a privileged actor could rewrite history undetectably).
- (c) **External WORM / object store** — strongest immutability, but new infra + egress, off-budget and
  off-thesis (self-hosted).
- **Recommendation: (a)**.

**D-P4-9 — Draft-SAR write target**
- (a) **Governed transactional write to a `sar_draft` Postgres table** (status DRAFT, links citations + run_id),
  returned for human review. *(recommended)* — a real, inspectable, audited state change with no external
  integration; demo-able; P5 can render it.
- (b) **Render a SAR markdown/PDF artifact to disk** — tangible, but file IO is a weaker "governed enterprise
  action" story than a transactional, audited DB write (and harder to audit atomically).
- (c) **Stub / no-op tool returning a fake id** — least work, but doesn't prove a governed write at all.
- **Recommendation: (a)** (P5 may render (b) from the row).

**★ D-P4-10 — Spring AI version for the MCP server stack** *(new, surfaced by §8 / G-P4-2; **re-scoped 2026-06-21** after the Boot-4 finding)*
- **Context:** the repo is pinned to **Spring AI `1.0.0`** on **Spring Boot `3.4.7`**. The MCP **server** stack
  D-P4-3 depends on — **Streamable-HTTP on WebMVC** (`spring.ai.mcp.server.protocol=STREAMABLE`),
  annotation-driven **`@McpTool`**/`@McpToolParam`, the `TransportContextExtractor` auth hook, and the "MCP
  Security" integration — is **already present in the Spring AI `1.1.x` line, which stays on Spring Boot 3.x.**
  **Critically, Spring AI `2.0.x` requires Spring Boot `4.0`** (Spring Framework 7, Jakarta EE 11, Jackson 3,
  JSpecify) and "cannot be loaded in a 3.x context" — i.e. adopting 2.0 forces a full Boot-4 migration of the
  *entire* repo (rag-engine, gateway/Spring Cloud Gateway, Spring Security), a multi-month effort wholly
  disproportionate to adding one tool server. P1/P3 are frozen and green against 1.0.0 / Boot 3.4.
- (a) **Bump repo-wide to the latest Spring AI `1.1.x` (e.g. 1.1.8), staying on Spring Boot 3.x, as P4 Task 0;
  acceptance = all frozen P1/P3 unit/IT + eval cassette gates + RBAC/PII hard gates re-green.** *(recommended —
  re-scoped)* — gets Streamable-HTTP WebMVC + `@McpTool` + MCP security with a **minor** bump on the same Boot
  major line (Advisor/VectorStore/RAG APIs shipped in 1.0 and are stable through 1.1). *Trade-offs: 1.1.x may
  want Spring Boot ≥3.5 (a low-risk same-major patch, and the recommended pre-4.0 step anyway — verify at Task 0);
  watch the `FunctionCallback`→`ToolCallback` deprecation, though `rag-engine` uses `ChatModel`/`EmbeddingModel`/
  `ChatClient`/evaluators, not `FunctionCallback`.*
- (b) **Bump only `mcp-tools` to 1.1.x, leave `gateway`/`rag-engine` on 1.0.0** — smaller diff, but two Spring AI
  versions in one reactor risks BOM/transitive conflicts and is a less honest production shape.
- (c) **Adopt Spring AI 2.0.x / Spring Boot 4.0 now** — most "current," but a major multi-layer framework
  migration (Jackson 3 silent JSON-shape changes, removed deprecated APIs, third-party Boot-4 compatibility
  blockers, Spring Cloud Gateway/Security upgrades) that would destabilize frozen P1/P3 for no P4 benefit.
- (d) **Stay on 1.0.0** — no bump, but 1.0.0's MCP-server maturity is weaker (risk of falling back to SSE or
  hand-wiring the Java SDK), under-selling the "current MCP" skill.
- **Recommendation: (a) — Spring AI 1.1.x, Boot 3.x, Task 0, gate-verified.** The **Spring AI 2.0 / Spring Boot
  4** migration is logged as **deliberate future work** (its own dedicated track — and a strong standalone
  portfolio story), explicitly **out of P4 scope** (and noted against the Boot 3.5 EOL 2026-06-30).

---

## 4. Test strategy

> Four things get verified: (i) **agent graph logic** (Python unit), (ii) the **MCP tool + governance**
> (Java unit/IT), (iii) the **safety invariants** (HITL/authz/audit hard gates), and (iv) **agent quality**
> (the new merge-blocking agent eval set). Per CLAUDE.md, P4 touches agents → it ships an **eval set + metric
> thresholds that gate it**. CI runs **model-free / cassette-replay (GPU off)**; live calibration runs on the
> GPU (auto-paused).

### 4.1 Agent unit tests (Python, model-free / stubbed LLM + stubbed Gateway/MCP)
- **Graph structure:** graph compiles; the only path to `act_sar` traverses the `approve` interrupt node
  (assert reachability) — `act_sar` is unreachable without approval.
- **Planner:** the forcing query yields the retrieve→assess→conditional-SAR plan.
- **Assess (deterministic):** breach=true when an exception exceeds the configured threshold; false otherwise;
  decision is a function of retrieved citations, not free-LLM text.
- **Branch:** no-breach → COMPLETED with no proposed action; breach → AWAITING_APPROVAL with a `proposedAction`.
- **HITL:** `interrupt` suspends + checkpoints; `Command(resume, approved=false)` → no tool call (REJECTED);
  `approved=true` → exactly one `open_draft_sar` call with the expected args.
- **Checkpointer:** state persists and **resumes after a simulated process restart** (new graph instance, same
  thread/run id).
- **Tool-call correctness:** the MCP client is invoked with valid args matching the input schema (account,
  period pattern, citations) — asserted against fixtures.
- **Step/iteration caps:** the graph cannot loop unbounded (max-steps enforced).

### 4.2 MCP tool / governance tests (Java, JUnit + Testcontainers Postgres)
- **OAuth 2.1 resource server:** missing/expired/forged token → `401`; **wrong `aud`** → `401`/`403` (RFC 8707);
  valid aud-scoped token → accepted.
- **Per-call clearance re-check (LLM06):** caller `< compliance` → tool refuses (`DENIED`), no `sar_draft` row.
- **Tool contract:** input-schema validation (bad `period`, oversized `rationale`) → rejected.
- **Transactional write:** success writes `sar_draft` (DRAFT) **and** the `SUCCESS` audit row atomically; a
  forced failure rolls back both (no orphan draft, no missing audit).
- **Audit append-only:** UPDATE/DELETE on `tool_audit` denied for the app role; chain verifier passes on a good
  log and **detects** a tampered row.
- **MCP transport:** Streamable HTTP round-trip (tool list + call) against the running server.

### 4.3 Hard gates (must pass — block the phase)
- **★ No unapproved write (R4, LLM06):** across all agent paths/fixtures, **0** `sar_draft` writes occur
  without a recorded human approval. The analogue of P1's negative-access gate, for actions.
- **★ No unauthorized action (R4, LLM06):** a sub-`compliance` caller can **never** cause a write — neither via
  retrieval (P1 RBAC: never sees the breach) nor via a forced tool call (resource server `DENIED`). **0**
  unauthorized writes.
- **Audit completeness + tamper-evidence (G9):** every tool invocation produces ≥1 immutable, chained audit
  row; chain verifies; **0** missing rows; tampering is detected.
- **Durable resume (G8):** a run interrupted at the HITL gate **resumes correctly after restart** (no lost
  state, no duplicate write).
- **★ Single-use / replay-protected approval (ASI07):** a captured/consumed approval (or its `jti`/resume
  token) **cannot be replayed** to authorize a second or mutated write; approval is bound to `run_id` +
  checkpoint version. **0** replayed/duplicate writes.
- **P1/P3 invariants hold through the agent path:** negative-access (0 cross-clearance leaks), prompt-injection
  (LLM01) on retrieved docs, and PII egress (LLM02) re-verified end-to-end via the agent → Gateway path.

### 4.4 Agent eval set (Python `/evals`, merge-blocking — the headline CLAUDE.md deliverable)
- **Scenario set (~10–15, committed + versioned)** spanning: the forcing story (breach → SAR), no-breach (→ no
  action), wrong-clearance caller (→ refusal, no leak), injection-in-source attempting to trigger/skip approval
  (→ resisted), ambiguous input (→ elicitation/clarify), rejection path (→ no write). Each scenario has an
  expected outcome (tool-called? approval-required? final answer grounded? authorized?).
- **Metrics + scorers** (`agent_scorer.py`), scored **trajectory-first** (the 2026 agent-eval consensus — score
  the whole execution trace, not just the final answer), on cassette replay in CI:
  - **Task success** — final state matches the scenario's expected outcome (outcome-level).
  - **Tool-selection correctness** — the right tool is chosen (or correctly *not* called).
  - **Argument correctness** — tool args are valid + match expectations (distinct from selection — a right tool
    with wrong args is a real, separately-scored failure mode).
  - **Step efficiency / trajectory hygiene** — no extraneous, looping, or *dangerous* tool calls (ties to
    ASI02 tool-misuse + ASI10 scaling); step/iteration cap respected.
  - **Plan adherence** — the executed trajectory follows the planner's plan (no off-plan actions).
  - **HITL-respected** — binary, **hard gate**.
  - **Authorization-respected** — binary, **hard gate**.
- Reuses the P2/P3 machinery and the project's eval triad: **DeepEval** agent metrics over the execution trace
  (consistent with the RAGAS/DeepEval choice), optionally LangChain **agentevals** trajectory evaluators;
  cassette-replay gate (GPU off) for CI, **live calibration** (GPU on, auto-paused) to set/record thresholds,
  Langfuse dataset sync for agent runs.

### 4.5 Thresholds (gate numbers)
| Check | Type | Gate |
|---|---|---|
| Unapproved writes | binary, **hard gate** | **0** |
| Unauthorized actions (sub-`compliance`) | binary, **hard gate** | **0** |
| Audit completeness + chain integrity | binary, **hard gate** | **100%** rows present + chain verifies |
| Durable resume-after-restart | binary, **hard gate** | passes |
| HITL-respected (eval set) | binary, **hard gate** | **100%** |
| Authorization-respected (eval set) | binary, **hard gate** | **100%** |
| Single-use / replay-protected approval (ASI07) | binary, **hard gate** | a consumed approval cannot re-authorize |
| Agent task success rate | metric, gate | ≥ floor calibrated on first live run (target ≥ 0.80) |
| Tool-selection correctness | metric, gate | ≥ floor calibrated on first live run (target ≥ 0.90) |
| Argument correctness | metric, gate | ≥ floor calibrated on first live run (target ≥ 0.90) |
| Step efficiency / no dangerous or looping calls | metric, gate | ≥ floor; 0 dangerous calls; step-cap respected |
| P1 D4 negative-access via agent path | binary, **hard gate** | **0** cross-clearance leaks |
| P1 D7 / LLM01 injection via agent path | binary, **hard gate** | **100%** pass |
| PII egress (LLM02) via agent path | binary, **hard gate** | **0** PII strings in any response |
| Agent cost/quality (tier2 vs tier1) | report (portfolio) | quantified delta recorded |

---

## 5. Task breakdown (ordered, independently committable)

0. **Spring AI version bump (D-P4-10, prerequisite):** raise `spring-ai.version` to the latest **`1.1.x`**
   (Streamable-HTTP WebMVC + `@McpTool` + MCP security, **staying on Spring Boot 3.x**); bump Spring Boot to
   3.5.x only if 1.1.x requires it (low-risk same-major patch). **Do NOT adopt Spring AI 2.0 / Spring Boot 4 in
   P4.** Acceptance = all frozen P1/P3 unit/IT + eval cassette gates + RBAC/PII hard gates re-green; cassettes
   re-recorded only if a fingerprint legitimately changes. *(commit: `chore(deps): bump Spring AI to 1.1.x (Boot 3.x) for MCP server stack; re-green P1/P3 gates`)*
1. **`/mcp-tools` module skeleton + reactor + compose:** new Spring Boot module (Spring AI MCP server starter,
   D-P4-3), added to the Maven reactor + `infra/docker-compose.yml`; actuator/health; `.env.example` P4 vars.
   *(commit: `feat(mcp-tools): module skeleton + MCP server + compose`)*
2. **Audit log (append-only, hash-chained):** Flyway `V2` (`agent` schema, `tool_audit` + append-only grant);
   `AuditService` + `AuditChainVerifier`; unit/IT incl. tamper-detection. *(commit: `feat(mcp-tools): append-only hash-chained audit log`)*
3. **`open_draft_sar` tool + `sar_draft` write:** `@Tool` over Streamable HTTP; input-schema validation;
   transactional `sar_draft` write + `SUCCESS` audit row; contract tests. *(commit: `feat(mcp-tools): governed draft-SAR write tool`)*
4. **OAuth 2.1 resource server + clearance re-check:** Spring Security resource server (sig+exp+iss+**aud**,
   RFC 8707); `ClearanceRecheck` (refuse `< compliance`); authz/`DENIED` tests. *(commit: `feat(mcp-tools): OAuth 2.1 resource server + per-call clearance re-check (LLM06)`)*
5. **Sim-IdP resource-scoped tokens (gateway, additive):** `ResourceScopedTokenIssuer` mints `aud=atlas-mcp-tools`
   tokens (D-P4-6); resource-server validation ITs. *(commit: `feat(gateway): RFC 8707 resource-scoped token issuance`)*
6. **`/agents` module skeleton:** `uv` project (mirrors `/evals`); FastAPI run API + `/healthz`; Postgres
   checkpointer wired (D-P4-7, `agent` schema); compose service. *(commit: `feat(agents): module skeleton + run API + Postgres checkpointer`)*
7. **Planner→executor graph + retrieval:** `graph.py`/`state.py`/`nodes` (D-P4-1); `retrieve` calls Gateway
   `/v1/query`; deterministic `assess`; conditional breach edge; graph-structure unit tests. *(commit: `feat(agents): planner-executor graph with RBAC retrieval via gateway`)*
8. **HITL gate + MCP action:** `interrupt`→`Command(resume)` before any write (D-P4-4); `mcp_client.py` calls
   `open_draft_sar` (aud-scoped Bearer); resume-after-restart test. *(commit: `feat(agents): human-in-the-loop approval gate + MCP action`)*
9. **End-to-end forcing-story IT:** Testcontainers Postgres + cassette LLM: retrieve → breach → interrupt →
   approve → audited write; rejection + restart branches. *(commit: `test(agents): end-to-end forcing-story integration`)*
10. **Agent tracing + Grafana panel:** Langfuse/OTel GenAI+MCP spans; agent panel (runs, tool-call rate,
    approval latency, failures). *(commit: `feat(agents): Langfuse tracing + Grafana agent panel`)*
11. **Agent eval set + merge gate:** `datasets/agent.py` scenarios + `agent_scorer.py` + `agent_gate.py`
    (cassette-replay CI gate + live calibration); CI wiring (merge-blocking). *(commit: `ci(evals): agent eval set + merge-blocking agent gate`)*
12. **Docs + portfolio + ADRs:** `agents/README.md`, `mcp-tools/README.md`, `docs/RUNBOOK.md` (run/approve/
    audit-query/GPU), `docs/DECISIONS.md` (ADR-0041…), quantified `docs/PORTFOLIO.md` bullet. *(commit: `docs(p4): agent + MCP READMEs, RUNBOOK, ADRs, portfolio`)*

---

## 6. Definition of Done (P4 — generic DoD from CLAUDE.md, instantiated)

> **STATUS — COMPLETE (2026-06-21).** Full suite green: rag-engine 90u+40IT · gateway 66u+14IT ·
> mcp-tools 12u+21IT · agents 60 tests (+3 live-gated, skipped offline) · agent eval gate 12/12 ·
> evals 63 + both RAG gates · gpu-helper 24 · ruff clean. Notes below record *how* each item is met,
> including the owner-confirmed deviations.

- [x] **Code complete & matches this spec.** `/agents` (LangGraph planner→executor, durable Postgres
      checkpointer, HITL interrupt/resume, clarify/field-confirmation, MCP client) + `/mcp-tools` (Spring AI
      MCP server, OAuth 2.1 resource server, `open_draft_sar` governed write returning `auditRef`, per-call
      clearance re-check, append-only hash-chained audit) — all config env-swappable. *Deviations (logged):
      caller identity read from Spring Security `SecurityContextHolder` rather than a manual
      `TransportContextExtractor` (ADR-0046 note, same outcome); "mid-task field confirmation" realized as a
      durable graph `clarify` interrupt rather than MCP-protocol elicitation, given the deterministic
      single-tool design + raw-httpx client (ADR-0044 note).*
- [x] **Unit + integration tests pass in CI.** Agent graph/HITL/clarify/checkpointer/act-retry/tool-call +
      MCP-tool Java unit/ITs (resource server, clearance re-check, transactional write + auditRef, audit
      append-only + tamper-detection, Streamable HTTP) all green.
- [x] **Safety hard gates met & recorded:** **0** unapproved writes; **0** unauthorized actions; audit
      completeness **100%** + chain verifies; durable **resume-after-restart** passes; single-use approval
      (no duplicate write); **bounded tool retries only on connect errors** (no duplicate write). P1 D4/D7 +
      PII egress through the **agent path**: offline conformance gate proves the agent uses the governed
      `/v1/query` with only the caller's Bearer + no clearance header (cannot bypass P1/P3), and a
      **live-tagged** end-to-end gate (`test_agent_path_invariants.py`, `ATLAS_LIVE_AGENT_PATH=1`) asserts
      0 cross-clearance citations / 0 PII / injection-quarantined through the agent against the running stack.
- [x] **Eval thresholds met & recorded (agents):** the agent eval set is a **merge-blocking** gate (offline,
      no GPU — the agent is deterministic, owner-confirmed, so no cassettes/DeepEval needed; ADR-0024 note);
      HITL-respected + authorization-respected = **100%**; task-success/tool-selection/argument/plan-adherence
      = 1.0 ≥ floors in `agents/data/agent-baseline.json`.
- [x] **Roadmap P4 exit criteria met** (ROADMAP §2 P4): planner-executor completes the conditional action
      E2E; the MCP tool exposes a governed write over Streamable HTTP secured as an OAuth 2.1 resource server
      (RFC 8707) with audit logging; **no state change without explicit HITL approval** (graph `interrupt`;
      field confirmation via `clarify`); state durably checkpointed in Postgres (resume after restart); tool
      re-checks clearance; audit log append-only/immutable + queryable; runs traced (OTel→Langfuse) + a CI
      eval gate; contracts + safety boundaries documented; decisions logged.
- [x] **Security & standards alignment recorded:** controls mapped to the **OWASP Top 10 for Agentic
      Applications (2026)** ASI01/02/03/06/07/09/10 (§8.2) with evidence; MCP pinned to spec **`2025-11-25`**
      on **Streamable HTTP** (SSE not used); RFC 8707 audience-restricted, single-use replay-protected
      approval verified; Spring AI bumped to **1.1.8 on Spring Boot 3.5** (D-P4-10; Spring AI 2.0/Boot 4
      deferred) with frozen P1/P3 gates re-green.
- [x] **Module READMEs + `docs/DECISIONS.md` updated** (ADR-0041–0050 + 0024/0030 dated implementation/
      deviation notes). Tool contracts + safety boundaries documented.
- [x] **Runs cleanly from a fresh clone** via `infra` compose + documented `.env`; RUNBOOK §8 (start a run,
      approve/reject, query the audit log, GPU note, live agent-path gate).
- [x] **A 30-second demo path:** RUNBOOK §8.2 — mint a `compliance` token → start the forcing-story run →
      cited summary + breach + `AWAITING_APPROVAL` → approve → audited `SAR-…` draft + immutable audit row
      (and the sub-`compliance` refusal / no write).
- [x] **A resume-ready, quantified portfolio bullet** drafted in `docs/PORTFOLIO.md` (P4 section).

---

## 7. Open questions / ambiguities to resolve (focused) — ALL RESOLVED 2026-06-21

These were surfaced as focused questions after this spec; **all are now owner-confirmed and logged (ADR-0041–0050):**

1. **D-P4-2 (agent model):** ✅ **tier2 `qwen2.5:7b`** (ADR-0042).
2. **D-P4-3 (MCP stack):** ✅ **Spring AI MCP server (WebMVC)** (ADR-0043).
3. **D-P4-4 (HITL):** ✅ **graph `interrupt` as the authoritative gate** + tool precondition (ADR-0044).
4. **D-P4-5 (agent placement):** ✅ **standalone agent service calling the Gateway**; Gateway/UI integration
   deferred to P5 (ADR-0045).
5. **Breach rule (assess node):** ✅ **single configurable numeric threshold** over the period (deterministic) —
   confirmed; multi-factor is future work (ADR-0049).
6. **Scope check:** ✅ **exactly one** governed write tool (`open_draft_sar`); no read-only MCP tools or a second
   action (ADR-0049).
7. **D-P4-10 (Spring AI version):** ✅ **bump repo-wide to Spring AI 1.1.x on Spring Boot 3.x** as Task 0
   (re-scoped from the original 2.0.x framing — 2.0 requires Boot 4, deferred as future work); frozen P1/P3 gate
   suite is the acceptance test (ADR-0050).

> All §3 decisions are logged as **ADR-0041–0050** in `docs/DECISIONS.md`. Implementation followed the §5
> task breakdown (Task 0 = the Spring AI 1.1.x bump) and is **complete** — see the §6 Definition of Done.

---

## 8. Research-driven refinements (web-validated, June 2026)

Gaps found by checking P4's plan against the current (June 2026) ecosystem — the MCP spec, Spring AI's MCP
server stack, the just-published OWASP agentic framework, and 2026 agent-eval practice. Each is folded into the
sections above; this table + §8.2 are the audit trail (mirroring P2 §6 / P3 §8).

### 8.1 Gap analysis (G-P4-1…8)
| # | Gap found vs. the plan | Why it matters for Atlas | Resolution → section |
|---|---|---|---|
| G-P4-1 | MCP spec had drifted — current stable is **`2025-11-25`** (RFC 8707 / OAuth Resource Server / elicitation / **structured tool output** stabilized in `2025-06-18`) | Demonstrating the *current* MCP security + I/O model is the in-demand skill; structured output is cleaner than free-text tool returns | Pinned MCP `2025-11-25`; tool returns **structured output**; elicitation is spec-native → §2.4, §2.6, D-P4-6 |
| G-P4-2 | Repo is on **Spring AI 1.0.0 / Spring Boot 3.4.7**. Streamable-HTTP **WebMVC** + `@McpTool` + MCP-security exist in **Spring AI 1.1.x (Boot 3.x)**; **Spring AI 2.0.x requires Spring Boot 4.0** (Framework 7 / Jakarta EE 11 / Jackson 3) and can't load in a 3.x context | Getting the current MCP server idiom must **not** trigger a multi-month Boot-4 migration of frozen P1/P3 | New **★ D-P4-10** → **minor bump to 1.1.x on Boot 3.x** as Task 0; **Spring AI 2.0 / Boot 4 deferred** to a dedicated future track → §3, §5, §1 non-goals |
| G-P4-3 | The **OWASP Top 10 for Agentic Applications (2026)** (ASI01–ASI10, published 2025-12-09) post-dates the roadmap's vague "agentic 2026 extensions" | A compliance-domain agent must map to the *named* agentic threats, not just LLM Top 10 | Added explicit **§8.2 control map**; referenced in §2.5 + DoD |
| G-P4-4 | The HITL approval was not explicitly **replay-protected** (ASI07 "replayed approval") | An intercepted/duplicated approval could authorize a second or mutated write — catastrophic for a governed write | Approval is **single-use, task-scoped, bound to `run_id`+checkpoint**, `jti`+short `exp`; new hard gate → §2.4, §4.3, §4.5 |
| G-P4-5 | The approval surface risked being a bare "confident recommendation" (ASI09 human-agent trust) | Anthropomorphism is an attack vector; approvers need evidence, not confidence | The gate shows **provenance/citations + the exact proposed args (a dry-run preview, ASI02)** → §2.3, §2.5 |
| G-P4-6 | Scaling/agency limits were implicit (ASI10 uncontrolled scaling) | A looping/spawning agent can exhaust the GPU/API budget (R3) | Explicit **step/iteration caps, no sub-agent spawning, reused P3 budget caps** → §1, §2.5, §4 |
| G-P4-7 | Agent eval was final-answer-oriented; 2026 practice is **trajectory-first** | Output-only evals are blind to wrong-tool, bad-args, looping, dangerous-action failures | Split **tool-selection vs argument correctness**, added **step-efficiency / trajectory hygiene + plan adherence**; reuse DeepEval (+ agentevals) → §4.4, §4.5 |
| G-P4-8 | Identity/privilege wording predated ASI03 "confused deputy" guidance | Delegated trust becomes silent privilege escalation in agent→tool hops | **Task-scoped, short-lived tokens + per-step re-authorization + no credential sharing** across the agent→tool boundary → §2.4, D-P4-6 |

**Framework currency confirmed (June 2026):** MCP spec **`2025-11-25`** stable (Streamable HTTP replaces SSE;
RFC 8707 audience-restricted tokens + OAuth resource-server classification + elicitation + structured tool
output). **Spring AI** MCP Server Boot Starters provide STDIO/SSE/**Streamable-HTTP**/stateless on **both
WebMVC and WebFlux** (`spring.ai.mcp.server.protocol=STREAMABLE`), annotation-driven `@McpTool` with auto
JSON-schema, `TransportContextExtractor` for header/auth access, and an MCP-Security integration — validating
the Java/Spring "governed MCP tool server" thesis. **LangGraph** remains the production agent framework with
durable checkpointing (incl. Postgres) + `interrupt`/`Command(resume)` HITL. **DeepEval** (+ LangChain
agentevals, tau-bench) is the standard agent-eval tooling; the 2026 consensus is **trajectory-level**
evaluation (task success · tool-selection · argument correctness · step efficiency · plan adherence).

### 8.2 OWASP Top 10 for Agentic Applications (2026) → P4 control map
| ASI risk | P4 control | Where |
|---|---|---|
| **ASI01 Agent Goal Hijack** | P1 prompt-injection guardrail on retrieved docs; **deterministic** breach `assess` (not LLM-instruction-driven); immutable graph structure (HITL gate not promptable) | §2.5, §4.3 |
| **ASI02 Tool Misuse & Exploitation** | One least-privilege tool; no tool-chaining; the `proposedAction` at the gate is a **dry-run preview**; step caps | §1, §2.3, §4 |
| **ASI03 Identity & Privilege Abuse** | RFC 8707 **task-scoped, short-lived** tokens; **per-call** clearance re-check at the tool; no credential sharing across the agent→tool hop | §2.4, D-P4-6 |
| **ASI04 Agentic Supply Chain** | Only our **own, pinned, signed** MCP server (no third-party MCP); AIBOM + dep/secret scan reused from P0 | §1, §2.1 |
| **ASI05 Unexpected Code Execution** | Tool does a **typed, transactional DB write only** — no codegen/shell/eval surface | §2.3, non-goals |
| **ASI06 Memory & Context Poisoning** | Checkpointer holds **per-run-isolated, trusted-write, validated** agent state (not a shared knowledge base); P1 ingestion integrity for RAG | §2.1, D-P4-7 |
| **ASI07 Insecure Inter-Agent Comms** | Authenticated channels (Bearer + `aud`); **single-use, replay-protected** approval bound to `run_id`+checkpoint | §2.4, §4.3 (hard gate) |
| **ASI08 Cascading Failures** | Resilience4j circuit breaker (reused P3); **planning separated from execution** + the HITL governance gate; transactional all-or-nothing write | §2.5, D-P4-1 |
| **ASI09 Human-Agent Trust Exploitation** | The gate surfaces **provenance/citations + exact args**, not just a recommendation; friction (explicit approval) before any write | §2.3, §2.5 |
| **ASI10 Uncontrolled Scaling** | Step/iteration caps; **no sub-agent spawning**; reused P3 per-user/route budget caps on the agent's model spend | §1, §2.5, §4 |
