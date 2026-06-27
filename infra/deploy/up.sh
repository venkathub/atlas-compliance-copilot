#!/usr/bin/env bash
#
# Atlas one-command deploy bring-up (P5 Task 10 — §1.7, G-P5-6).
#
# Builds the UI + reverse-proxy image and starts the single-origin proxy over TLS. By
# default it brings up ONLY the proxy (serving the built UI over Caddy internal-TLS) — the
# local-TLS proof. Pass --full to also start the in-compose backends (`--profile app`,
# needs the built Java jars + a reachable GPU via OLLAMA_BASE_URL).
#
# Snap-Docker note: the daemon can't read /data paths, so compose is piped over stdin and
# the image is built from a tar-streamed context (mirrors infra/Makefile). On a normal
# Docker host (CI / the Oracle/Hetzner box) the plain commands in the comments work too.
#
# Usage:
#   infra/deploy/up.sh           # proxy-only (local-TLS proof)
#   infra/deploy/up.sh --full    # proxy + backends (full stack)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] && { set -a; . "$ENV_FILE"; set +a; }

PROFILES=(--profile proxy)
[ "${1:-}" = "--full" ] && PROFILES+=(--profile app)

echo "== Build the UI + proxy image (atlas/ui) =="
# Normal host:  docker build -f ui/Dockerfile -t atlas/ui:0.1.0-SNAPSHOT .
# Snap-Docker:  stream the context as a tar (the daemon can't read /data directly).
tar -czh \
  --exclude='./.git' --exclude='./ui/node_modules' --exclude='./ui/dist' \
  --exclude='**/target' --exclude='**/.venv' --exclude='**/__pycache__' \
  --exclude='**/playwright-report' --exclude='**/test-results' . \
  | docker build -f ui/Dockerfile -t atlas/ui:0.1.0-SNAPSHOT -

echo "== Start the stack (${PROFILES[*]}) behind Caddy internal-TLS =="
# Normal host:  docker compose -p atlas -f infra/docker-compose.yml "${PROFILES[@]}" up -d
# Snap-Docker:  pipe the compose file over stdin.
cat infra/docker-compose.yml | docker compose -p atlas -f - "${PROFILES[@]}" up -d

echo "== Up. Proxy: https://${PROXY_SITE_ADDRESS:-localhost}:${PROXY_HTTPS_PORT:-8443}/ =="
echo "   Smoke it:  infra/deploy/smoke.sh https://localhost:${PROXY_HTTPS_PORT:-8443}"
