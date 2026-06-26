# Atlas :: ui (React)

Chat + admin UI (**P5**) — a thin **presentation client** over the frozen backend HTTP
contracts. Streamed, cited answers; the human-in-the-loop agent approval surface; a
collapsible execution trace; and a **read-only** admin area (eval scores, cost/latency,
audit log). All model/markdown output is **sanitized before render** (OWASP LLM05).

> **Status — P5 Task 3 (RAG chat path).** Auth (1) + safe render (2) in place, plus
> the **chat query path**: a composer + conversation list calling the frozen
> `POST /v1/query` (`useQuery`), the cited `Answer`, **cost/cache/latency `MetaBadges`**,
> a **client-side progressive reveal** (`useProgressiveReveal`, reduced-motion aware),
> and the **AI-transparency** surface (session-start disclosure + per-message
> "AI-generated" label, G-P5-4). Still to come: the agent/HITL surface (Task 4), the
> additive `GET /v1/audit` admin views (Task 6), the Caddy reverse proxy + CSP (Task 7),
> and deploy automation (Tasks 8/10).

## Real `/v1/query` contract (frozen Gateway)

The chat path matches the **actual** Gateway response (it relays the rag-engine
envelope and merges `routing`/`cache`/`redaction`/`cost`), which differs from the spec
§2.3 illustration — corrected in `lib/types.ts` since the backend is frozen:

```
POST /v1/query  body { "query": "…", "topK"?, "includeContexts"? }
200  { answer, citations[], retrieval?, routing{modelTier,model,escalated},
       cache{hit,similarity?}, redaction{applied,counts}, cost{promptTokens,
       completionTokens,costUnits,latencyMs} }
```

Citation index is **`marker`** (not `n`); citations also carry `docId` (human slug),
`title`, `sourceUri`, `score`. Errors surfaced as calm messages: **402** budget,
**413** too-long, **429** rate-limit, **503** unavailable. No streaming exists
server-side, so the "live" feel is the client-side reveal (D-P5-1a / ADR-0051).

## Safe rendering (OWASP LLM05)

Model output is treated as **untrusted interpreter input**. Anything rendered as HTML
goes through `sanitizeMarkdown` (markdown → DOMPurify allowlist) first; snippets/audit
cells go through `sanitizeText`. Guarantees: no `<script>`/event handlers/`<iframe>`,
URLs limited to http(s)/mailto/tel/relative/anchor (`javascript:`/`data:` stripped),
external links forced to `target="_blank" rel="noopener noreferrer"`. This is the
**client wall**; the Caddy proxy CSP (Task 7) is the independent **second wall**
(ADR-0058). assistant-ui was evaluated and not adopted — its streaming runtime would
force a backend change (ADR-0054 fallback to a hand-rolled `Answer`/`Citation`).

## sim-IdP contract (real, frozen Gateway)

The login surface matches the **actual** `SimIdpController` contract, which differs from
the spec §2.3 illustration (corrected here, since the backend is frozen):

```
POST /v1/auth/token   body { "user": "priya" }          # field is `user`, not `subject`
200  { token, tokenType:"Bearer", expiresIn:3600, subject, clearance }
```

Seeded identities (the only accepted logins) and their clearance:

| `user` (login id) | Clearance    | Who                   |
| ----------------- | ------------ | --------------------- |
| `priya`           | `compliance` | Priya — Compliance    |
| `bsa-admin`       | `restricted` | BSA Officer / Admin   |
| `analyst-bob`     | `analyst`    | Bob — Markets Analyst |
| `guest-public`    | `public`     | Public Guest          |

Clearance ladder: `public < analyst < compliance < restricted`. There is no `/refresh`
endpoint — a page refresh drops the in-memory token and the user re-logs-in (D-P5-6).
No CORS is needed on the Gateway: the single-origin proxy (dev: Vite proxy; prod: Caddy)
makes every call same-origin (ADR for D-P5-2). The Gateway stays untouched.

## Design boundaries (why this stays thin)

- **No secrets, no authorization logic, no model calls in the browser.** The bundle is
  public; only `VITE_`-prefixed config is exposed. Clearance is **always re-enforced
  server-side** (RBAC at retrieval, OAuth re-check at the tool, refuse-`<compliance` on
  `/v1/audit`). The UI hiding an admin tab is UX, not a security boundary.
- **Single origin.** In dev, the Vite proxy path-routes `/v1/*` → Gateway,
  `/v1/agent/*` → Agents, `/v1/audit` → mcp-tools; in prod the Caddy reverse proxy does
  the same. No CORS, no backend topology leaked to the browser (D-P5-2).
- **Backends are frozen.** P1 retrieval/RBAC, P3 gateway, and P4 agent/MCP contracts are
  unchanged. The UI is a new _consumer_ only.

## Stack

- **Vite + React 19 + TypeScript** (D-P5-4) — builds to static assets served behind the
  proxy; smallest footprint for a low-spec laptop.
- **Tailwind v4** (CSS-first config via `@tailwindcss/vite`; no `tailwind.config.js`).
- **TanStack Query** for server state; **DOMPurify + marked** for safe markdown (LLM05).
- **Vitest + React Testing Library** for unit/component tests; **Playwright** E2E in Task 9.

## Setup

```bash
cd ui
nvm use            # Node 22 (repo-root .nvmrc)
npm ci             # clean, lockfile-pinned install
cp ../.env.example ../.env   # if not already present; UI reads VITE_* vars
```

## Scripts

| Script                 | What it does                                              |
| ---------------------- | --------------------------------------------------------- |
| `npm run dev`          | Vite dev server (proxies `/v1/*` to local backends)       |
| `npm run build`        | `tsc --noEmit` typecheck **then** `vite build` to `dist/` |
| `npm run preview`      | Serve the built `dist/` locally                           |
| `npm run lint`         | ESLint (flat config, TS + React hooks)                    |
| `npm run typecheck`    | `tsc --noEmit`                                            |
| `npm test`             | Vitest (run mode) — unit/component tests                  |
| `npm run test:watch`   | Vitest watch mode                                         |
| `npm run format`       | Prettier write                                            |
| `npm run format:check` | Prettier check (CI gate)                                  |

## Configuration (`.env`, all public)

| Var                       | Default                 | Purpose                                          |
| ------------------------- | ----------------------- | ------------------------------------------------ |
| `VITE_API_BASE_URL`       | _(empty = same-origin)_ | Base URL for backend calls; blank uses the proxy |
| `VITE_DEV_GATEWAY_TARGET` | `http://localhost:8080` | Dev-proxy upstream for `/v1/*` (Gateway)         |
| `VITE_DEV_AGENTS_TARGET`  | `http://localhost:8083` | Dev-proxy upstream for `/v1/agent/*` (Agents)    |
| `VITE_DEV_MCP_TARGET`     | `http://localhost:8082` | Dev-proxy upstream for `/v1/audit` (mcp-tools)   |

These are the only UI vars in P5 Task 0; proxy/TLS/deploy vars arrive in later tasks.

## Tests / CI

`npm run lint && npm run typecheck && npm run format:check && npm test && npm run build`
run in the `ui` CI job (Node 22), plus a bundle scan asserting **no secret** ships in
`dist/`. Results are green as of Task 0 (1 smoke test).
