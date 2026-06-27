# syntax=docker/dockerfile:1
#
# Atlas UI + reverse-proxy image (P5 Task 8 — D-P5-2/5).
#
# Multi-stage, MULTI-ARCH (amd64 + arm64 — runs on the Oracle Ampere A1 prod target):
#   stage 1 builds the React UI to static assets (Node 22, the repo .nvmrc toolchain);
#   stage 2 is Caddy serving those assets and path-routing /v1/* to the FROZEN backends
#   under one origin, with the strict CSP + security headers baked in (infra/proxy/Caddyfile).
#
# No secret is baked in — the bundle is public; all endpoints/TLS/upstreams are env-injected
# at runtime (see root .env.example + docker-compose). Build context = repo ROOT:
#   docker build -f ui/Dockerfile -t atlas/ui:latest .
#
# Bases pinned by digest (OWASP LLM03 supply-chain). The arm64 layers build under QEMU in CI.

# ── stage 1: build the static UI ──────────────────────────────────────────────
FROM node:22-bookworm-slim@sha256:813a7480f28fdadac1f7f5c824bcdad435b5bc1322a5968bbbdef8d058f9dff4 AS build
WORKDIR /ui
# Install deps first (layer-cached until the lockfile changes).
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
# App sources, then the production build (tsc --noEmit && vite build -> /ui/dist).
COPY ui/ ./
RUN npm run build

# ── stage 2: Caddy serving the built UI + reverse proxy ───────────────────────
FROM caddy:2-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648
# The single-origin routing + CSP/security headers (P5 Task 7).
COPY infra/proxy/Caddyfile /etc/caddy/Caddyfile
# The static bundle the Caddyfile serves from /srv/ui.
COPY --from=build /ui/dist /srv/ui
EXPOSE 80 443
# The official caddy image's ENTRYPOINT runs `caddy run --config /etc/caddy/Caddyfile`.
