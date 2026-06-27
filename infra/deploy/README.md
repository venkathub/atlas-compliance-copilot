# Atlas :: infra/deploy

One-command deploy automation + the **local-TLS smoke test** (P5 Task 10 — §1.7, §4.5,
G-P5-6). The P5 gate is **deploy automation + a local internal-TLS proof + a verified
multi-arch (arm64) image** — the live Oracle Ampere A1 deploy is a documented dry-run
runbook executed post-merge (see `docs/RUNBOOK.md` §9).

## Scripts

| Script      | What it does                                                                 |
| ----------- | --------------------------------------------------------------------------- |
| `up.sh`     | Build the UI/proxy image + bring the stack up behind Caddy internal-TLS.     |
| `smoke.sh`  | Assert the proxy serves the UI over TLS with CSP/headers, SPA, no secret.    |

```bash
# Local-TLS proof (proxy-only — serves the built UI over https://localhost:8443):
make -C infra deploy-up
make -C infra deploy-smoke

# Full stack (also starts the in-compose backends — needs built jars + a GPU):
make -C infra deploy-up FULL=1
make -C infra deploy-smoke              # now the login (+ query) round-trip runs too
```

## What `smoke.sh` asserts (GPU-free hard gate)

1. The UI is **served over TLS** (`https://…/` → 200, the SPA root).
2. The strict **CSP + security headers** are present (`script-src 'self'`, `object-src
   'none'`, `X-Content-Type-Options`, `Referrer-Policy`, `HSTS`, `X-Frame-Options`).
3. The **SPA fallback** serves `index.html` for client-side routes (`/admin`).
4. **No secret** is in the served JS bundle (LLM02 — the bundle is public).
5. **Login round-trip** `POST /v1/auth/token` over TLS — and **query** `POST /v1/query` —
   when the backends are reachable; otherwise skipped-with-warning (the live GPU lane).

## Notes

- **Snap-Docker:** the daemon can't read `/data` paths, so `up.sh` streams the build
  context as a tar and pipes compose over stdin (mirrors `infra/Makefile`). On a normal
  Docker host (CI / the Oracle/Hetzner box) the plain `docker build` / `docker compose`
  commands in the script comments work directly.
- **TLS:** `PROXY_TLS=internal` (default) uses Caddy's local CA — the local-TLS proof. For
  the live box set `PROXY_SITE_ADDRESS=<domain>` and `PROXY_TLS=<acme-email>` for automatic
  Let's Encrypt (`infra/docker-compose.prod.yml`).
- **Secrets** are env/secret-store injected, never baked into the image or the UI bundle.
