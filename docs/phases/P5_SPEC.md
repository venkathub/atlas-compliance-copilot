# P5 — React UI, Containerization & Production Deployment — SPEC

> Status: **APPROVED 2026-06-26 — §3 decisions owner-confirmed and logged as ADR-0051…0059 in
> `docs/DECISIONS.md`. Ready to begin Task 0.** Implementation follows the §5 task breakdown; P1/P3/P4 stay
> frozen.
> Date drafted: 2026-06-26 · Date approved: 2026-06-26.
> **Owner-confirmed §7 resolutions (2026-06-26):** (1) **client-side progressive reveal** for the chat answer +
> polled agent trace — backend SSE is a non-blocking stretch (D-P5-1=a+c); (2) **read-only admin**, eval scores
> read from the committed gate artifact (D-P5-3=a); (3) **multimodal frontier demo is a budget-gated stretch,
> not a gate** (D-P5-7=a); (4) **the Oracle Ampere A1 box is NOT yet provisioned** → the P5 deploy gate is
> **deploy *automation* + a local-TLS reverse-proxy proof + a multi-arch (arm64) image build**; the **live**
> Oracle/Hetzner deploy + DNS/TLS is a documented, dry-run runbook executed **post-merge when the box exists**
> (it does not block the phase). See §1.7, §4.5, §6.
> Phase owner doc set: `CLAUDE.md` · `docs/ROADMAP.md` (§2 P5, §0.3 deploy, §7.1 LLM05) · `docs/DECISIONS.md`
> (ADR-0003 sim-IdP, ADR-0006 deploy targets, ADR-0007 NIST AI RMF / EU AI Act design constraints, ADR-0034
> verified-clearance trust boundary, ADR-0037 output sanitization) · `docs/phases/P3_SPEC.md` (Gateway the UI
> calls) · `docs/phases/P4_SPEC.md` (Agent run + HITL the UI drives) · `docs/RUNBOOK.md`.

This is the **last** phase. It ships the **clickable product**: a React chat + admin UI that makes the entire
forcing story visible — Priya logs in, asks her question, sees a **streamed, cited answer**, is shown the
**proposed draft-SAR action**, **approves it** (the human-in-the-loop checkpoint), and watches the
**execution trace** — then the whole stack is **containerized (multi-arch ARM)** and **deployed to Oracle
Cloud Always Free (Ampere A1)** behind TLS with a single documented command.

P5 adds **no new intelligence**. P1 retrieval/RBAC, P3 gateway, and P4 agent/MCP behaviour are **frozen**; the
UI is a new *consumer* of their existing HTTP contracts, plus a thin **read-only admin surface** for evals,
cost, and the audit log. The phase is "done" when the forcing story runs end-to-end **on the deployed box**,
not on a laptop.

---

## 1. Scope

### In scope
1. **React UI (`/ui`) — NEW.** A single-page app (Vite + React + TypeScript) with two areas:
   - **Chat** — login (sim-IdP), a streamed answer pane with **inline citations** (click → source snippet +
     clearance), the **agent run** flow surfacing `AWAITING_APPROVAL` with an **Approve / Reject** control
     (the P4 HITL checkpoint), and a collapsible **execution-trace** panel (planner→retrieve→assess→approve→act).
   - **Admin** — read-only views of **eval scores** (latest gate results), **cost/latency dashboards**, and the
     **append-only audit log** of governed actions. Gated to `compliance`/admin clearance.
2. **Two backend integrations (existing contracts, unchanged):**
   - **Gateway** — `POST /v1/auth/token` (login → JWT w/ clearance), `POST /v1/query` (RAG chat; the §2.3 P3
     envelope: answer + citations + routing/cache/cost).
   - **Agents** — `POST /v1/agent/runs`, `POST /v1/agent/runs/{id}/resume`, `GET /v1/agent/runs/{id}` (the P4
     planner→executor + HITL run).
3. **Streaming answer UX** (strategy chosen in D-P5-1) so the chat reads as a live assistant, not a spinner.
4. **Safe rendering (OWASP LLM05 — the P5 security gate).** All model/markdown output (answers, citations,
   rationales, audit rows) is **sanitized before display** — no XSS via citation HTML, no script execution,
   links are `rel=noopener` and scheme-allowlisted. Complements the P3 server-side output sanitization
   (ADR-0037): defense-in-depth at the render boundary.
5. **Thin admin read API (NEW, additive).** A small read-only surface for the three admin views:
   - **Audit log** read endpoint (owner = `mcp-tools`, where `tool_audit` lives) — paginated, plus a
     chain-verify status field.
   - **Eval scores** — surfaced from the committed eval-gate result artifact (and/or Langfuse), not recomputed.
   - **Cost/latency** — Grafana panels (embedded) + a compact native summary from the Gateway's existing
     Prometheus metrics.
6. **Edge / topology (chosen in D-P5-2).** A reverse proxy fronts the stack: serves the built static UI, routes
   `/v1/*` to Gateway and `/v1/agent/*` to Agents under **one origin** (kills CORS), terminates TLS.
7. **Production deployment — automation now, live box deferred.** Multi-arch images (P0 already builds
   amd64+arm64) plus a **single documented deploy command** and a **prod Compose overlay** (TLS, secret
   injection, restart policies). Because the **Oracle Ampere A1 box is not yet provisioned (owner-confirmed)**,
   the **P5 gate is the automation + a local reverse-proxy-with-TLS proof + a verified arm64 image build**; the
   **live** deploy to **Oracle Always Free Ampere A1 (4 vCPU / 24 GB)** — with DNS, ACME TLS, and the GPU via
   `OLLAMA_BASE_URL` — is a **dry-run runbook executed post-merge** when the box exists (**Hetzner Cloud**
   fallback documented). Secrets are env/secret-store injected, never bundled.
8. **End-to-end acceptance.** A Playwright E2E test drives the **full forcing story** (Priya → cited answer →
   approved draft SAR → trace + audit row) against the running Compose stack; a deploy **smoke test** asserts a
   **local TLS reverse-proxy** serves the UI and a login+query round-trips (the same smoke runs against the live
   box once provisioned).
9. **Docs + config:** `ui/README.md` (setup, scripts, test, build), `docs/RUNBOOK.md` (deploy / rollback /
   TLS / secrets), `docs/DECISIONS.md` (ADR-0051…), `docs/PORTFOLIO.md` **completed** + demo recording;
   `.env.example` extended with UI/proxy/deploy vars; `/ui` wired into CI (lint + unit + build + E2E).
10. **CSP + security headers at the proxy (LLM05 defense-in-depth — G-P5-2).** The Caddy proxy emits a strict
    **Content-Security-Policy** (`default-src 'self'`; `script-src` nonce/`strict-dynamic`, **no**
    `unsafe-inline`; scheme-allowlisted `img-src`/`connect-src`; `frame-ancestors` scoped for the Grafana
    embed) plus `X-Content-Type-Options`, `Referrer-Policy`, and HSTS — an independent second wall behind the
    client-side sanitizer.
11. **AI-transparency surfacing (EU AI Act / NIST AI RMF — G-P5-4).** The UI shows a **session-start
    AI-system disclosure**, labels assistant messages as **AI-generated**, and stamps the draft SAR as
    **"AI-assisted draft — requires human review."** Treated as a **design constraint**, not a certification
    (consistent with ADR-0007).

### Non-goals (explicit — prevent scope creep)
- **No change to P1/P3/P4 behaviour or contracts.** Retrieval/RBAC, gateway routing/cache/budget/PII, agent
  graph, MCP tool, and the audit schema are **frozen**. P5 is additive: a UI, a reverse proxy, a read-only
  admin surface, and deploy automation. Any regression in the prior phases' hard gates **blocks** P5.
- **No second MCP tool, no new agent capability, no new eval metric.** P5 ships zero new model-touching logic,
  so it introduces **no new RAGAS/agent eval thresholds** — it must keep the **existing** P2/P4 gates green and
  adds an **E2E acceptance + deploy smoke** gate on top.
- **No real OIDC / SSO / multi-tenant user management.** Login uses the existing sim-IdP (ADR-0003). No signup,
  password reset, org management, or refresh-token rotation beyond what the sim-IdP already mints.
- **No mutable admin actions.** Admin is **read-only** (view evals / cost / audit). No "re-run eval", "edit
  budget", "delete audit row", or any state change from the UI. (Audit is append-only by DB grant anyway.)
- **No bespoke metrics/trace store.** Cost dashboards reuse the **existing** Grafana/Prometheus (P3) and
  Langfuse traces (P2); the UI embeds/links them rather than reimplementing them.
- **No native mobile app, no PWA/offline, no i18n/l10n, no theming system.** One responsive desktop-first web UI.
- **No Kubernetes / Terraform / autoscaling / multi-node.** Single-box Docker Compose deploy on the free ARM
  VM (Compose is the documented prod runtime for this portfolio). IaC is post-P5.
- **No CDN, no managed TLS service dependency** beyond the chosen proxy's ACME (D-P5-5). Cloudflare, if used,
  is optional and env-gated.
- **Multimodal frontier demo is a budget-gated STRETCH (D-P5-7), not a phase gate.** The phase passes without
  it; it is reserved final-demo polish on the cloud-frontier budget, excluded from the §5 time band.

---

## 2. Design

### 2.1 Language / runtime split (and why)
P5 is the **only phase whose primary new surface is TypeScript/React**, but the polyglot thesis holds: the UI
is a thin presentation client over the Java/Spring "moat" (Gateway + MCP tools) and the Python orchestration
brain (Agents). No business logic moves into the browser.

- **TypeScript / React (`/ui`) — NEW, presentation only.** Chat, citations, HITL approval control, trace view,
  admin read views, streamed-answer rendering, client-side output sanitization (LLM05). Rationale: React is the
  mandated UI (CLAUDE.md §Architecture-1); Vite + TS is the lean, fast-feedback toolchain that fits a low-spec
  laptop. **No secrets, no authorization logic, no model calls** live here — the browser only renders what the
  trusted backends return, and clearance is always re-enforced server-side (the UI hiding an admin tab is UX,
  not a security boundary).
- **Java / Spring (`gateway`, `mcp-tools`) — reused + one additive read endpoint.** `mcp-tools` gains a
  **read-only** `GET /v1/audit` (paginated, with chain-verify status) — it owns the `tool_audit` table, so the
  audit read belongs there, secured by the same OAuth 2.1 resource server (refuse `< compliance`). The Gateway
  is otherwise untouched (it already exposes `/v1/auth/token`, `/v1/query`, and Prometheus metrics).
- **Python (`agents`, `evals`) — reused, not extended (hot path).** The UI calls the **existing** agent run
  API. Eval scores are read from the **committed gate artifact** the P2/P4 harness already produces (and/or the
  Langfuse API) — the UI never triggers an eval run.
- **Reverse proxy (`infra`, Caddy/nginx — D-P5-2/5).** Serves static UI + path-routes to Gateway/Agents under
  one origin + terminates TLS. Infra config, not application code.

**Boundary contracts (all HTTP/JSON, unchanged): browser → proxy → { Gateway `/v1/*`, Agents `/v1/agent/*`,
mcp-tools `/v1/audit` } each with `Authorization: Bearer <sim-IdP JWT>`.** The UI never holds a downstream
secret and never talks to `rag-engine`, Postgres, or the MCP tool directly.

### 2.2 Component breakdown
```
ui/                                      # Vite + React + TypeScript (NEW)
  index.html
  src/
    main.tsx                 # app bootstrap, router
    app/
      routes.tsx             # /login, /chat, /admin (admin guarded by clearance)
      auth/
        AuthContext.tsx      # holds the in-memory JWT + decoded clearance; login/logout
        LoginPage.tsx        # sim-IdP POST /v1/auth/token; pick a seeded identity (Priya, analyst, public)
        useClearance.ts      # decode claim for UI gating (NOT a security boundary)
      chat/
        ChatPage.tsx         # message list + composer; orchestrates query vs agent-run
        useQuery.ts          # POST /v1/query (streamed per D-P5-1)
        useAgentRun.ts       # POST /v1/agent/runs → AWAITING_APPROVAL → resume; GET poll for state
        Answer.tsx           # sanitized markdown render (LLM05) with citation anchors
        Citation.tsx         # [n] chip → popover: documentId, clearance, snippet
        ApprovalCard.tsx     # proposedAction + Approve/Reject → POST .../resume (the HITL surface)
        TracePanel.tsx       # collapsible planner→retrieve→assess→approve→act timeline + cost/cache badges
      admin/
        AdminPage.tsx        # tabbed: Evals | Cost | Audit (clearance-gated)
        EvalScores.tsx       # latest gate results (faithfulness/relevancy/agent-success) from artifact/Langfuse
        CostDashboard.tsx    # embedded Grafana panel(s) + native summary from Gateway metrics
        AuditLog.tsx         # paginated table from GET /v1/audit + chain-verify badge
      lib/
        apiClient.ts         # fetch wrapper: base URL, Bearer attach, 401→login, typed errors
        sanitize.ts          # DOMPurify-based allowlist; markdown→safe HTML (LLM05)
        sse.ts               # SSE/stream consumer (if D-P5-1 = backend streaming)
        types.ts             # shared response types mirrored from backend contracts
  tests/                     # Vitest + React Testing Library (unit/component) + Playwright (e2e)
  Dockerfile                 # multi-stage: build → static assets served by the proxy image (multi-arch)
  vite.config.ts, tsconfig.json, package.json, .eslintrc, .prettierrc

mcp-tools/ (Java — additive, read-only)
  src/main/java/com/atlas/mcptools/audit/
    AuditQueryController     # GET /v1/audit?account=&page= → paginated rows + chainVerified:boolean
                             # OAuth 2.1 resource server; refuse < compliance; SELECT-only (no new write path)

infra/
  proxy/                     # Caddy/nginx (D-P5-2/5): static UI + /v1 → gateway, /v1/agent → agents, TLS/ACME
  docker-compose.yml         # + ui (static, behind proxy) + proxy service; prod overlay
  docker-compose.prod.yml    # prod overlay: TLS domain, restart policies, secret-store env, no dev mounts
  deploy/                    # one-command deploy to Oracle Ampere A1 (script + docs); Hetzner fallback notes
  grafana/                   # + cost/latency panel for SECURE embed (public-dashboard share token, never anonymous — G-P5-3)
```

### 2.3 Data models / schemas (UI-facing — all mirror existing backend contracts)

**Login (`POST /v1/auth/token`, existing sim-IdP).**
```jsonc
// request
{ "subject": "priya" }                  // seeded identity → clearance resolved server-side
// response
{ "token": "<jwt>", "clearance": "compliance", "expiresIn": 3600 }
```

**RAG chat (`POST /v1/query`, existing P3 envelope — rendered in the answer pane).**
```jsonc
{ "answer": "…inline [1] cited markdown…",
  "citations": [ { "n": 1, "documentId": "l2-northwind-amlexc-q2", "clearance": "compliance", "snippet": "…" } ],
  "routing": { "tier": "TIER1_SMALL", "cache": "miss" },
  "cost": { "inputTokens": 412, "outputTokens": 220, "units": 0.0031 } }
```

**Agent run (`POST /v1/agent/runs` → `…/resume`, existing P4 — drives the HITL flow).**
```jsonc
// after the breach is found:
{ "runId": "run_…", "status": "AWAITING_APPROVAL",
  "answer": "3 open AML exceptions; 1 breaches the $10k threshold …",
  "citations": [ … ],
  "proposedAction": { "tool": "open_draft_sar", "args": { "account": "Northwind", "period": "2026-Q2", … } },
  "trace": [ { "node": "retrieve", "ms": 2810 }, { "node": "assess", "breach": true }, { "node": "approve" } ] }
// UI shows ApprovalCard → POST /v1/agent/runs/{id}/resume { "approved": true, "note": "Reviewed" }
// → { "status": "COMPLETED", "action": { "draftRef": "SAR-2026-000123", "status": "DRAFT" }, "auditRef": "audit_…" }
```

**Audit read (`GET /v1/audit`, NEW read-only — admin table).**
```jsonc
{ "page": 0, "size": 25, "total": 7, "chainVerified": true,
  "rows": [ { "seq": 7, "ts": "…", "runId": "run_…", "tool": "open_draft_sar",
             "phase": "SUCCESS", "caller": "priya", "clearance": "compliance",
             "resultRef": "SAR-2026-000123" } ] }   // args_digest/hashes summarized, not raw PII (LLM02)
```

**Eval scores (read from the committed gate artifact / Langfuse — admin Evals tab).**
```jsonc
{ "ragGate":   { "faithfulness": 0.91, "answerRelevancy": 0.88, "contextRecall": 0.84, "passed": true },
  "agentGate": { "taskSuccess": 12, "of": 12, "toolCallCorrectness": 1.0, "hitlEnforced": true, "passed": true },
  "generatedAt": "…", "commit": "…" }
```

### 2.4 Key interfaces & contracts

**Auth / session contract.** Login posts to the sim-IdP, receives a short-lived JWT carrying the verified
clearance (ADR-0034). The UI stores it **in memory** (per D-P5-6) and attaches it as `Authorization: Bearer`
to every backend call; on `401`/expiry it routes to login. The decoded clearance gates which UI tabs render —
**but every backend independently re-enforces clearance**, so a tampered client cannot reach data above its
level (RBAC at retrieval, OAuth re-check at the tool, refuse-`<compliance` on `/v1/audit`).

**Streaming contract (D-P5-1).** Whichever streaming strategy is chosen, the **final** payload the UI renders
is byte-identical to today's synchronous envelope, so P3/P4 grounding/citation/cost guarantees are preserved.
If backend SSE is added, it is **additive** (`Accept: text/event-stream` opt-in); the existing JSON path stays.

**HITL surfacing contract (the safety story made visible).** The `act_sar` write is **server-side
unreachable** until `…/resume {approved:true}` (P4 invariant). The UI's Approve button is the *trigger*, not
the *authority*: rejecting (or never approving) yields **no write** and a `REJECTED` audit row. The UI must
never construct or pre-fill a write call itself — it only forwards the human decision to the agent.

**Safe-rendering contract (LLM05).** Model output is treated as **untrusted**. Markdown is rendered through a
sanitizer with an HTML allowlist (no `<script>`, no event handlers, no `javascript:`/`data:` URLs); citation
snippets are escaped; external links get `target=_blank rel="noopener noreferrer"`. A red-team fixture (a
document/answer carrying an XSS payload) is asserted inert in tests.

**Deploy / config contract.** All endpoints, the TLS domain, and `OLLAMA_BASE_URL` are env-injected at the
proxy/compose layer; **no secret is baked into the UI bundle** (the bundle is public). The build is the same
multi-arch image set P0 produces; the prod overlay differs only in env + restart policy + TLS.

### 2.5 Request / data flow (the forcing story, on the deployed box)
```
Browser (Priya)
  └─(1) POST /v1/auth/token {subject:priya} ──► [proxy] ─► Gateway sim-IdP ─► JWT(clearance=compliance)
  └─(2) types the forcing question ─► UI routes to AGENT run (conditional action present)
        POST /v1/agent/runs {query,account,period}  (Bearer) ──► [proxy] ─► Agents
            Agents ─► Gateway POST /v1/query (RBAC retrieval, cited, cost-routed)  ◄─ grounded context
            Agents assess breach=true ─► returns status=AWAITING_APPROVAL + proposedAction + trace
  └─(3) UI renders streamed cited answer + ApprovalCard + TracePanel
  └─(4) Priya clicks Approve ─► POST /v1/agent/runs/{id}/resume {approved:true} ──► Agents
            Agents ─► MCP open_draft_sar (OAuth aud=mcp, clearance re-check) ─► sar_draft + hash-chained audit
            ◄─ status=COMPLETED {draftRef:SAR-2026-000123}
  └─(5) UI shows the draft-SAR reference + final trace; Admin▸Audit shows the new SUCCESS row (chainVerified)
Everything traced in Langfuse; cost/latency on Grafana — both reachable from Admin.
```

---

## 3. Decisions to make now

> Each has 2–3 options + a recommendation. On your confirmation these become **ADR-0051…** in
> `docs/DECISIONS.md`. (Latest existing ADR: ADR-0050.)

**D-P5-1 — Streaming answer UX (backends are synchronous today)**
Both `/v1/query` and `/v1/agent/runs` currently return a **complete** JSON payload (no SSE). Options:
- (a) **Client-side progressive reveal (no backend change).** Render the completed answer with a fast
  typewriter/skeleton effect. *+* zero change to frozen P3/P4, lowest risk, fast. *−* not "real" streaming;
  perceived latency for long answers unchanged.
- (b) **Add SSE token streaming to the Gateway (and pass-through from Agents).** *+* genuine live tokens, best
  demo polish, in-demand skill. *−* touches the **frozen** P3 gateway (additive `Accept: text/event-stream`
  path) and Ollama streaming plumbing; more test surface; must preserve the post-stream sanitized/grounded
  envelope.
- (c) **Poll `GET /v1/agent/runs/{id}` for node-by-node trace + reveal answer on completion.** *+* no new
  streaming transport; reuses the existing GET; naturally animates the **trace**. *−* chat answer still arrives
  in one chunk; polling is chattier.
- **Recommendation: (a) for the chat answer + (c) for the agent trace.** Gets a live-feeling UI with **no
  change to the frozen backends**, honoring the "P5 adds no new intelligence / contracts frozen" rule. Mark
  **(b) backend SSE as an explicit stretch** if time remains, since it’s a strong portfolio talking point.

**D-P5-2 — UI ↔ backend topology (two origins: Gateway + Agents)**
- (a) **Reverse proxy as single origin (serves static UI; `/v1/*`→Gateway, `/v1/agent/*`→Agents, `/v1/audit`→mcp-tools).**
  *+* no CORS, one TLS endpoint, one URL to demo, mirrors prod shape. *−* one more infra component to configure.
- (b) **Gateway becomes a BFF that proxies to Agents + serves the UI.** *+* single Java entry point. *−*
  **violates "Gateway frozen"**; couples UI lifecycle to the Gateway; more Java work for no real gain.
- (c) **UI calls Gateway + Agents directly with CORS.** *+* no proxy. *−* CORS config on two frozen services,
  two public origins, awkward TLS, leaks topology to the browser.
- **Recommendation: (a).** Cleanest, keeps every backend frozen, and is the honest production shape.

**D-P5-3 — Admin observability surfacing (evals, cost, audit)**
- (a) **Hybrid: native React panels for audit (`GET /v1/audit`) + eval artifact, embed Grafana for cost/latency.**
  *+* reuses the rich P3 Grafana dashboards (no reinvention), native where data is small/structured. *−* the
  embed must be secured (**G-P5-3**): use Grafana **read-only public-dashboard share tokens** *or* Grafana
  behind the **same Caddy auth** with `allow_embedding` + matching CSP `frame-ancestors` — **never anonymous
  org access** (it would leak cost data publicly). The native cost summary (from the Gateway's existing
  Prometheus metrics) is the always-on path; the Grafana embed is the drill-down.
- (b) **Fully native React panels hitting new read endpoints for all three.** *+* consistent look, no iframe.
  *−* re-implements dashboards Grafana already gives for free; most build cost.
- (c) **Just deep-link out to Grafana/Langfuse from the admin page.** *+* near-zero build. *−* weakest "one
  product" story; leaves the app to show off external tools.
- **Recommendation: (a).** Best effort/impact: native audit table (the compliance headline) + **securely
  embedded** Grafana (the cost story) + eval scorecard from the committed gate artifact.

**D-P5-4 — Frontend stack & styling**
- (a) **Vite + React + TypeScript + Tailwind; TanStack Query for server state; DOMPurify + `marked` for safe markdown.**
  *+* fast, lean, low-spec-friendly, industry-standard, great DX. *−* Tailwind opinion (fine for one UI).
- (b) **Next.js (App Router).** *+* SSR/routing batteries. *−* SSR is pointless here (pure client over JSON
  APIs), heavier, fights the "static assets behind a proxy" deploy.
- (c) **Vite + React + plain CSS modules.** *+* zero styling deps. *−* slower to build a polished admin/chat UI.
- **Recommendation: (a).** Matches `.nvmrc` Node 22, builds to static assets, smallest footprint for the demo.
  **Sub-decision (G-P5-1):** evaluate **assistant-ui (`@assistant-ui/react`)** composable primitives for the
  chat surface (streaming reveal, auto-scroll, accessibility, citation rendering) behind a **custom runtime
  adapter** over our **frozen** synchronous JSON contracts — **do not** adopt the Vercel AI-SDK streaming wire
  protocol (it would force a backend change). If the adapter proves heavier than hand-rolling, fall back to
  Tailwind + TanStack Query primitives. Either way the backends stay frozen.

**D-P5-5 — Reverse proxy + TLS (live box deferred; local-TLS proof is the gate)**
The Oracle box is not provisioned yet (owner-confirmed), so P5 **gates on the automation + a local-TLS proof**;
the proxy choice still matters because it’s what the deferred live deploy will use.
- (a) **Caddy.** *+* automatic HTTPS (ACME/Let’s Encrypt) with ~3 lines, arm64 image, trivial static-file +
  reverse-proxy config, and a one-line **internal/self-signed TLS** mode perfect for the **local-TLS proof**.
  *−* less ubiquitous than nginx in enterprises.
- (b) **nginx + certbot.** *+* ubiquitous, familiar. *−* manual cert renewal/automation, more config; local-TLS
  proof needs hand-rolled self-signed certs.
- (c) **Cloudflare Tunnel (no public port / managed TLS).** *+* hides the box, free TLS, **no DNS/box needed for
  a demo URL** — a clean option once we do go live without a domain. *−* hard third-party dependency, against
  the self-hosted ethos; keep optional/env-gated.
- **Recommendation: (a) Caddy** — its internal-TLS mode satisfies the P5 local-TLS gate today and its ACME mode
  serves the live Oracle deploy later, with (c) documented as the zero-DNS live-demo alternative.

**D-P5-6 — Browser token storage (security-relevant)**
- (a) **In-memory only (React state/context), re-login on refresh.** *+* not readable by XSS-persisted theft;
  simplest; fine for a demo. *−* refresh = re-login (acceptable; sim-IdP login is one click).
- (b) **`localStorage`.** *+* survives refresh. *−* XSS-exfiltratable; worst fit for a compliance demo.
- (c) **httpOnly cookie via a BFF session.** *+* most production-correct. *−* needs a session/BFF layer the
  sim-IdP doesn’t have; over-scoped for P5.
- **Recommendation: (a) in-memory**, paired with the strict LLM05 sanitizer to shrink the XSS surface anyway.
  Note the (c) upgrade path in the ADR.

**D-P5-7 — Multimodal frontier demo (budget-gated)**
- (a) **Out of P5 scope; documented as optional post-ship polish.** *+* protects the time band; phase passes on
  the self-hosted stack. *−* no multimodal in the gated demo.
- (b) **In scope as a stretch behind an env flag + the reserved frontier budget.** *+* flashy final demo. *−*
  risk to the deadline; new model path to test.
- **Recommendation: (a) — explicit stretch, not a gate.** The forcing story (text RAG + governed action) is the
  thesis; multimodal is garnish (ROADMAP §5 excludes it from the band).

---

## 4. Test strategy

> P5 introduces **no new model logic**, so it adds **no new RAGAS/agent eval thresholds**. It must keep **all
> existing P2 RAG gates and P4 agent gates green**, and adds a UI/test layer + an **E2E acceptance gate** + a
> **deploy smoke gate**.

### 4.1 UI unit / component tests (Vitest + React Testing Library)
- Auth: login stores token, attaches Bearer, `401`→login redirect, logout clears in-memory token.
- Chat: renders streamed/progressive answer; **citation chip → popover** shows documentId + clearance + snippet.
- HITL: `AWAITING_APPROVAL` renders `ApprovalCard`; **Approve** calls `…/resume {approved:true}`, **Reject**
  calls `{approved:false}` and renders no draftRef; the UI never fabricates a write call.
- TracePanel: renders planner→retrieve→assess→approve→act with cost/cache badges.
- Admin gating: a sub-`compliance` clearance does **not** render the Admin tab (UX gate); audit table paginates;
  chain-verify badge reflects `chainVerified`.

### 4.2 Safe-rendering / security tests (LLM05 — hard gate)
- An answer/citation/audit row carrying an XSS payload (`<script>`, `<img onerror>`, `javascript:` link) renders
  **inert** (sanitizer strips/escapes; no execution). Asserted via DOM + a Playwright "no dialog/console-error"
  check. **Blocks the phase.**
- **CSP enforced (G-P5-2):** the proxy returns a strict `Content-Security-Policy` (no `unsafe-inline` script;
  nonce/`strict-dynamic`) + `X-Content-Type-Options`/`Referrer-Policy`/`frame-ancestors`; a test asserts the
  header is present and that an inline-script injection is blocked by CSP (independent of the sanitizer). **Blocks.**
- No secret/env value is present in the built JS bundle (grep the dist for forbidden keys in CI). **Blocks.**

### 4.3 Backend additive tests (Java, JUnit + Testcontainers Postgres)
- `GET /v1/audit`: returns paginated rows; **refuses `< compliance`** (401/403); is **SELECT-only** (no write
  path introduced); `chainVerified` reflects `AuditChainVerifier`. (Reuses P4 audit fixtures.)
- (If D-P5-1=b) Gateway SSE path: streamed chunks reassemble to the **same** sanitized/grounded envelope as the
  JSON path; RBAC/cost/cache invariants unchanged.

### 4.4 End-to-end acceptance (Playwright — the headline P5 gate)
- **The forcing story, full loop:** login as Priya → ask the question → assert **streamed cited answer** →
  assert **ApprovalCard** with proposed `open_draft_sar` → **Approve** → assert `draftRef` shown → assert
  **Admin▸Audit** shows the new `SUCCESS` row with `chainVerified:true`.
- **Negative-access UX:** login as a sub-`compliance` identity → ask the same question → assert **no
  restricted content** in the answer and **no Admin tab** (the P1 RBAC guarantee, surfaced).
- Runs against the running Compose stack in CI with **Playwright network mocking** (`page.route`/`route.fulfill`)
  pinning backend responses for **determinism** (no live-model variance in the gate); a **live** variant runs
  against the GPU on demand (G-P5-5).
- **Accessibility smoke (G-P5-5):** an **axe-core** scan runs on the chat + admin pages as part of the E2E gate
  (no critical violations).

### 4.5 Deploy smoke test (gates the *automation*; live box deferred)
- **Local-TLS proof (the gate):** against the local Compose stack behind the Caddy proxy in **internal-TLS**
  mode — `https://localhost/` serves the UI; `POST /v1/auth/token` + `POST /v1/query` round-trip over TLS;
  healthchecks green; **no secret in the served bundle**.
- **Image portability (the gate):** multi-arch image manifests include `linux/arm64`; the stack boots from a
  **fresh clone + `.env`** via the one documented command.
- **Live deploy (deferred, non-blocking):** the **same** smoke script targets the real Oracle Ampere A1 box
  (ACME TLS, DNS) and is executed **post-merge once the box is provisioned**; documented as a runbook with a
  Hetzner fallback. It is not a P5 merge gate (owner-confirmed: box not yet provisioned).

### 4.6 Regression gate (inherited — must stay green)
- Full prior suite: rag-engine, gateway, mcp-tools, agents unit+IT; **RAG eval gate** (P2) and **agent eval
  gate** (P4) both pass. Any red prior gate **blocks** P5 (contracts are frozen — a break means a regression).

---

## 5. Task breakdown (ordered, independently committable)

0. **Scaffold `/ui` module (D-P5-4):** new Vite + React + TS + Tailwind project (mirrors the repo's module
   conventions), ESLint/Prettier, `apiClient`, typed contracts mirrored from the backend envelopes; `/ui` wired
   into CI (lint + unit + build); `ui/README.md` stub; `.env.example` UI vars. **No app logic.** Acceptance =
   CI lint+build green; nothing else regresses. *(commit: `feat(ui): Vite+React+TS module skeleton + CI lint/build`)*
1. **Auth + AuthContext + LoginPage (D-P5-6):** sim-IdP `POST /v1/auth/token`; **in-memory** token + decoded
   clearance; Bearer attach in `apiClient`; `401`/expiry → login; seeded-identity picker (Priya/analyst/public);
   unit tests. *(commit: `feat(ui): sim-IdP login + in-memory auth context`)*
2. **Safe-render core + `Answer`/`Citation` (LLM05, G-P5-1):** `sanitize.ts` (DOMPurify allowlist, markdown→safe
   HTML); citation `[n]` chip → source/clearance popover; evaluate **assistant-ui** primitives behind a custom
   runtime adapter (no AI-SDK backend protocol); **LLM05 XSS fixture test** (§4.2). *(commit: `feat(ui): sanitized markdown answer + citation rendering (LLM05)`)*
3. **Chat query path (D-P5-1 a, G-P5-4):** `useQuery` → `POST /v1/query`; render cited answer + cost/cache
   badges; client-side progressive reveal; **AI-generated message label + session-start AI disclosure**; tests.
   *(commit: `feat(ui): RAG chat query path with progressive reveal + AI disclosure`)*
4. **Agent run + HITL surface (D-P5-1 c, G-P5-4):** `useAgentRun` (runs → `AWAITING_APPROVAL` → resume; GET-poll
   trace); `ApprovalCard` (Approve/Reject); `TracePanel`; **"AI-assisted draft — requires human review" stamp**;
   approve/reject + never-fabricate-write tests. *(commit: `feat(ui): agent run + human-in-the-loop approval surface`)*
5. **`mcp-tools` read-only `GET /v1/audit` (Java, additive):** paginated rows + `chainVerified`; OAuth 2.1
   resource server (refuse `< compliance`); **SELECT-only**, no new write path; Testcontainers ITs (§4.3).
   *(commit: `feat(mcp-tools): read-only audit query endpoint (compliance-gated)`)*
6. **Admin views (D-P5-3, G-P5-3):** `EvalScores` (committed gate artifact/Langfuse), `CostDashboard` (securely
   embedded Grafana + native Prometheus summary), `AuditLog` (`GET /v1/audit`); clearance gating; tests.
   *(commit: `feat(ui): read-only admin (evals, cost, audit log)`)*
7. **Reverse proxy + security headers (D-P5-2/5, G-P5-2/3):** `infra/proxy` Caddy — serve static UI (SPA
   fallback) + path-route `/v1/*`→gateway, `/v1/agent/*`→agents, `/v1/audit`→mcp-tools under one origin, local
   internal-TLS; **strict CSP + `X-Content-Type-Options`/`Referrer-Policy`/HSTS + Grafana `frame-ancestors`**;
   compose wiring. *(commit: `feat(infra): Caddy single-origin reverse proxy + CSP/security headers`)*
8. **Containerize UI + prod overlay:** multi-stage **multi-arch (arm64)** UI image served behind the proxy;
   `docker-compose.prod.yml` (TLS domain, restart policy, secret-store env, no dev mounts); CI builds arm64.
   *(commit: `feat(infra): multi-arch UI image + prod compose overlay`)*
9. **Playwright E2E + a11y (G-P5-5):** forcing-story full loop + negative-access UX (§4.4); deterministic CI lane
   via **network mocking** (`page.route`/`route.fulfill`) + **axe-core a11y smoke**; live variant on the GPU.
   *(commit: `test(ui): Playwright forcing-story + negative-access E2E with a11y smoke`)*
10. **Deploy automation + smoke (G-P5-6):** `infra/deploy/` one-command bring-up behind Caddy (internal-TLS) +
    **deploy smoke test** (§4.5) over local TLS + arm64 manifest check; **live** Oracle Ampere A1 + ACME TLS +
    DNS written as a **dry-run runbook** (Hetzner fallback), executed post-merge; `docs/RUNBOOK.md` deploy/
    rollback/TLS/secrets section. *(commit: `feat(infra): one-command deploy automation + local-TLS smoke test`)*
11. **Docs + portfolio close-out + ADRs:** `ui/README.md` final; `.env.example` UI/proxy/deploy vars;
    `docs/DECISIONS.md` (ADR-0051…); `docs/PORTFOLIO.md` **completed** + 30-sec demo path + recording.
    *(commit: `docs(p5): UI README, RUNBOOK, ADR-0051…, completed PORTFOLIO`)*
12. **(Stretch, if time) Backend SSE + multimodal:** additive `Accept: text/event-stream` streaming
    (D-P5-1 b) and/or env-gated multimodal frontier demo (D-P5-7 b) — **non-blocking**, must not regress any
    frozen gate. *(commit: `feat(ui): optional backend SSE streaming + multimodal demo (env-gated)`)*

---

## 6. Definition of Done (P5 — generic CLAUDE.md DoD, instantiated)

- [ ] **Code complete & matches this spec.** React chat+admin UI, reverse proxy, additive `GET /v1/audit`, and
      deploy automation built; P1/P3/P4 contracts unchanged (frozen).
- [ ] **Unit + integration tests pass.** UI unit/component (Vitest/RTL), LLM05 sanitization gate, `GET /v1/audit`
      Java IT (Testcontainers), Playwright E2E (forcing story + negative-access), deploy smoke — all green in CI.
- [ ] **Eval thresholds met (inherited).** P5 adds no new model logic; the **existing** P2 RAG gate and P4 agent
      gate remain green and are recorded — a regression blocks the merge.
- [ ] **Safe rendering (LLM05).** Output sanitized at the render boundary **+ strict CSP/security headers at the
      proxy** (G-P5-2); XSS fixture proven inert; **no secret in the served bundle** (CI-asserted).
- [ ] **AI transparency (EU AI Act / NIST AI RMF — G-P5-4).** Session-start AI disclosure, AI-generated message
      labels, and the "AI-assisted draft — requires human review" SAR stamp are present (design-constraint, not
      a certification).
- [ ] **Module README + DECISIONS updated.** `ui/README.md` (setup/scripts/test/build/run); §3 decisions logged
      as ADR-0051… with options + rationale.
- [ ] **Runs clean from scratch.** Fresh clone + `.env` → one documented command brings up the full stack
      locally **behind a TLS reverse proxy** (Caddy internal-TLS); multi-arch (arm64) image build verified. The
      **live** Oracle ARM deploy is a documented, dry-run runbook (Hetzner fallback) **executed post-merge when
      the box is provisioned** — non-blocking for P5.
- [ ] **30-second demo path.** Click path: login as Priya → ask the forcing question → see cited streamed answer
      → Approve the draft SAR → see draftRef + trace → Admin shows the audit row + cost panel.
- [ ] **Resume-ready, quantified bullet** drafted in `docs/PORTFOLIO.md`, and **PORTFOLIO.md completed** (this is
      the final phase) + demo recording linked.
- [ ] **The full forcing user story is demonstrable** end-to-end on the **local TLS stack** now (ROADMAP §2 P5
      intent), and re-runs on the **live Oracle box** via the same E2E/smoke once provisioned (deferred,
      non-blocking).

---

## 7. Open questions / ambiguities — RESOLVED (2026-06-26)

1. ~~**Streaming (D-P5-1):**~~ → **Resolved:** client-side **progressive reveal** for the chat answer + **polled
   agent trace**; **no change to frozen P3/P4**. Backend SSE (D-P5-1=b) is an explicit **stretch** (Task 12).
2. ~~**Admin scope (D-P5-3):**~~ → **Resolved:** **read-only** admin; eval scores read from the **committed gate
   artifact** (and/or Langfuse), never a UI-triggered eval run; cost via embedded Grafana + native summary;
   audit via `GET /v1/audit`.
3. ~~**Deploy reality check (D-P5-5):**~~ → **Resolved:** Oracle box **not yet provisioned** → the P5 gate is
   **deploy automation + a local-TLS (Caddy internal) proof + an arm64 image build**. The **live** Oracle deploy
   (DNS + ACME TLS; Hetzner fallback; Cloudflare-Tunnel as a no-DNS option) is a **dry-run runbook executed
   post-merge** and does **not** block the phase.
4. ~~**Multimodal demo (D-P5-7):**~~ → **Resolved:** **budget-gated stretch**, not a gate; phase passes on the
   self-hosted text stack.

**Assumption (state-and-proceed, per CLAUDE.md):** the login screen exposes the existing seeded sim-IdP
identities — **`priya` (compliance)**, an **`analyst`**, and a **`public`** user — so the forcing-story and
negative-access UX are each one click. If the seeded identity set differs, flag it at Task 1 and I’ll adjust.

**On your approval of §3, I will log D-P5-1…7 (+ the §8 refinements) as ADR-0051… in `docs/DECISIONS.md` and
begin Task 0. No application code is written before then.**

---

## 8. Research-driven refinements (web-validated, June 2026)

Gaps found by checking the **current** ecosystem against the Atlas vision + ROADMAP §2 P5 / §7, then folded
into the sections above. **Invariant honored throughout: every refinement is additive to P5 only** — the new
UI, the new Caddy proxy, the new read-only `GET /v1/audit`, new infra config, and new tests. **None touch P1
retrieval/RBAC, P3 gateway, or P4 agent/MCP code or contracts** (those stay frozen).

### 8.1 Gap analysis (G-P5-1…6)

| # | Gap found vs. vision | Why it matters for Atlas | Resolution → where folded |
|---|---|---|---|
| **G-P5-1** | A mature React **AI-chat primitive** ecosystem now exists — **assistant-ui** (`@assistant-ui/react`, actively published) and the **Vercel AI SDK** `useChat` — handling streaming, auto-scroll, **accessibility**, and tool/citation rendering. D-P5-4 chose a hand-rolled stack. | Reinventing streaming/scroll/a11y is wasted effort and likely *less* accessible than the library. But the AI SDK / assistant-ui **runtimes assume their own streaming wire protocol** — adopting it would force a change to the **frozen** synchronous Gateway/Agents contracts. | **D-P5-4 updated:** evaluate **assistant-ui composable primitives** behind a **custom runtime adapter** over our existing JSON contracts (no AI-SDK protocol on the backend). If the adapter is non-trivial, stay framework-light (Tailwind + TanStack Query) — either way **backends stay frozen**. Logged as a D-P5-4 sub-decision. |
| **G-P5-2** | LLM05 is now widely framed as **"the new XSS"** (Auth0/OWASP, Feb 2026): treat model output as untrusted interpreter input. D-spec had **DOMPurify only**; no **Content-Security-Policy** / security-header layer. | Sanitizer bugs happen; CSP is the cheap, independent second wall that neutralizes injected `<script>`/inline handlers even if a sanitizer rule is missed — exactly the defense-in-depth a compliance copilot should show. | **NEW: §1.10 + Caddy (Task 7).** A strict **CSP** (`default-src 'self'`, `script-src` nonce/`strict-dynamic`, **no** `unsafe-inline`, scheme-allowlisted `img/connect-src`) + security headers (`X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors`) emitted at the proxy. Added to the §4.2 LLM05 gate. |
| **G-P5-3** | **Grafana embedding** has a real security trap: **anonymous access leaks** the cost/observability data publicly. D-P5-3 said "anonymous read or signed embed" loosely. | A financial/compliance demo must not expose cost/latency dashboards to the open internet via an anonymous iframe. | **D-P5-3 updated:** use Grafana **read-only public-dashboard share tokens** (or Grafana behind the **same Caddy auth** with `allow_embedding` + matching CSP `frame-ancestors`) — **never anonymous org access**. The native cost summary (from the Gateway's existing Prometheus metrics) is the always-on path; the embed is the drill-down. |
| **G-P5-4** | **EU AI Act transparency** — the *Code of Practice on Transparency of AI-Generated Content* becomes **applicable 2026-08-02**, the same date as high-risk obligations (ROADMAP §7.3). The spec had **no user-facing AI disclosure / AI-content marking**. | Atlas is a financial/compliance copilot whose answers and the **drafted SAR** are AI-generated; disclosing "you are interacting with an AI" and **marking AI-generated content** is the in-vogue, low-cost governance signal — and reinforces the human-oversight story (the SAR is a *draft for human review*). | **NEW: §1.11 + DoD.** UI shows a **session-start AI-system disclosure**, labels assistant messages as **AI-generated**, and stamps the draft SAR as **"AI-assisted draft — requires human review."** Treated as a **design constraint** (not a certification), consistent with ADR-0007 / NIST AI RMF. |
| **G-P5-5** | E2E of a **non-deterministic LLM UI** needs determinism. §4.4 said "cassette/stubbed model" but didn't pin the browser-level mechanism, and had **no accessibility (a11y) check** despite "production-grade UI." | Flaky CI from live-model variance erodes the gate; a11y is table-stakes for production UI quality (and assistant-ui markets it). | **§4.4 updated:** the deterministic CI lane uses **Playwright network mocking** (`page.route`/`route.fulfill`) to pin backend responses; an **axe-core a11y smoke** runs on the chat + admin pages as part of the E2E gate. The **live** variant still runs against the GPU. |
| **G-P5-6** | The **deploy target isn't provisioned** (owner-confirmed §7). Without re-scoping, "deploy to Oracle" would be an unmeetable gate. | A phase gate must be *achievable now*; the live box is a calendar dependency, not an engineering one. | **Already folded (§1.7, §4.5, §6):** the P5 gate is **deploy automation + local-TLS (Caddy internal) proof + arm64 image build**; the **live** Oracle/Hetzner deploy is a **dry-run runbook executed post-merge**. Cloudflare-Tunnel documented as a **no-DNS** live-demo option (D-P5-5 c). |

### 8.2 OWASP / governance delta map (P5-owned controls only)

| Risk / obligation | P5 control | Where | Status |
|---|---|---|---|
| **LLM05 Improper Output Handling** | Client-side sanitizer (DOMPurify allowlist) **+** proxy **CSP**/security headers; XSS fixture proven inert | §1.4/1.10, §4.2, Task 2/7 | Added now (G-P5-2) |
| **LLM02 Sensitive Information Disclosure** | **No secret in the served bundle** (CI grep gate); `/v1/audit` returns digests/refs, not raw PII; clearance-gated admin | §1.5, §4.2/4.3 | In plan (explicit) |
| **LLM09 Misinformation** | Inline **citations** + clickable source/clearance provenance surfaced in the UI (renders the P1/P2 grounding) | §1.1, §2.3 | In plan |
| **LLM06 Excessive Agency** | UI **surfaces** (never bypasses) the P4 HITL approval; rejecting yields no write | §1.1, §2.4 | In plan |
| **EU AI Act transparency (2026-08-02)** | AI-system disclosure + AI-generated-content marking + "AI-assisted draft" SAR stamp | §1.11, §6 | Added now (G-P5-4) |
| **NIST AI RMF (human oversight/traceability)** | Visible execution **trace** + audit log + human-approval gate in the UI | §1.1, §2.5 | In plan |

> **Framework currency confirmed (June 2026):** **assistant-ui** + **Vercel AI SDK** are the current React
> AI-chat standard; **Caddy 2.11.x** remains the low-friction auto-HTTPS reverse proxy; **in-memory access
> token** (with httpOnly-cookie + BFF as the documented upgrade) is the OWASP-aligned SPA default; **Grafana
> public dashboards / authenticated embeds** are the safe embedding paths (anonymous org access is not). These
> validate the P5 stack picks and sharpen them via G-P5-1…6 — **without disturbing any prior phase.**
