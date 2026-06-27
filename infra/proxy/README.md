# Atlas :: infra/proxy (Caddy reverse proxy)

Single-origin reverse proxy (P5 Task 7 — D-P5-2/5, G-P5-2/3). Caddy serves the built
React UI as static files and path-routes API calls to the **frozen** backends under one
origin — no CORS, one TLS endpoint — and emits a strict **Content-Security-Policy** +
security headers (the independent second wall behind the client-side sanitizer, ADR-0058).

## Routing (order matters)

| Path           | Upstream (default: host-run)        | Purpose                          |
| -------------- | ----------------------------------- | -------------------------------- |
| `/v1/agent/*`  | `AGENTS_UPSTREAM` (`…:8083`)         | agent runs + HITL resume + trace |
| `/v1/audit*`   | `MCP_UPSTREAM` (`…:8082`)            | read-only audit query            |
| `/v1/*`        | `GATEWAY_UPSTREAM` (`…:8080`)        | sim-IdP auth + RAG query         |
| everything else| static `ui/dist` (SPA fallback)     | the React app                    |

The `/mcp` tool endpoint is **not** proxied to the browser — only the agent reaches it
in-network. Upstreams default to host-run backends (`host.docker.internal:*`, the dev
flow) and are env-overridable to the compose service names (`gateway:8080` …) for a full
in-compose bring-up (`--profile app --profile proxy`).

## Security headers (G-P5-2)

Strict CSP: `default-src 'self'`; **`script-src 'self'`** and **`style-src 'self'`** (no
`unsafe-inline`/`unsafe-eval` — the Vite build emits only hashed external scripts + a
linked stylesheet); `object-src 'none'`; `frame-ancestors 'self'`; `frame-src 'self'
{$GRAFANA_ORIGIN}` for the cost embed; scheme-allowlisted `img/connect/font`. Plus
`X-Content-Type-Options`, `Referrer-Policy`, `HSTS`, `X-Frame-Options`, and `-Server`.
(Grafana embedding also needs `GF_SECURITY_ALLOW_EMBEDDING: "true"`, set in compose.)

## TLS

`PROXY_TLS=internal` (default) uses Caddy's local CA / self-signed cert — the P5
local-TLS proof on `https://localhost`. For the live deploy (Task 10), set
`PROXY_SITE_ADDRESS` to the real domain and `PROXY_TLS` to an ACME email for automatic
Let's Encrypt.

## Run

```bash
make -C infra proxy-validate    # validate the Caddyfile (no bring-up)
make -C infra proxy-up          # build the UI image + start the proxy (needs ui/Dockerfile, Task 8)
```

The image (multi-stage: build UI → Caddy serving `dist` + this Caddyfile) is produced by
`ui/Dockerfile` (P5 Task 8); the one-command deploy + local-TLS smoke test is P5 Task 10.
All endpoints/TLS/upstreams are env-injected (see root `.env.example`); no secret is baked
into the UI bundle.
