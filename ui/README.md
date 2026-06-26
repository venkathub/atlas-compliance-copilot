# Atlas :: ui (React)

Chat + admin UI (**P5**) — a thin **presentation client** over the frozen backend HTTP
contracts. Streamed, cited answers; the human-in-the-loop agent approval surface; a
collapsible execution trace; and a **read-only** admin area (eval scores, cost/latency,
audit log). All model/markdown output is **sanitized before render** (OWASP LLM05).

> **Status — P5 Task 0 (skeleton).** Vite + React + TypeScript + Tailwind v4 toolchain
> scaffolded and wired into CI (lint · typecheck · format · unit test · build). The
> `apiClient` fetch wrapper, the typed backend contracts (`src/lib/types.ts`), and a
> `sanitize` **stub** are in place. **No app logic yet** — auth (Task 1), the sanitized
> chat surface (Tasks 2–4), the additive `GET /v1/audit` admin views (Task 6), the
> Caddy reverse proxy (Task 7), and deploy automation (Tasks 8/10) follow.

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
