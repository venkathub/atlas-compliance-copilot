#!/usr/bin/env bash
#
# Atlas demo seed / reset (P6 Task 6).
#
# Loads the deterministic demo dataset so the <3-minute walkthrough (docs/DEMO.md) is repeatable:
#   * ingests the two-layer RBAC-tagged corpus (12 FinanceBench evidence snippets + 12 Northwind
#     AML/compliance docs with per-doc clearance) via the rag-engine admin ingest endpoint;
#   * the four demo users (guest-public · analyst-bob · priya · bsa-admin) are the P1 dev shim
#     (rag-engine/.../dev/clearance-users.json) — no seeding needed, just listed here.
#
# Requires: the stack up (`make -C infra up` + rag-engine running) AND a resumed GPU
# (`make -C infra gpu-up`) — ingestion computes embeddings on OLLAMA_BASE_URL.
#
# Usage:
#   infra/deploy/seed-demo.sh                 # ingest against http://localhost:8081
#   RAG_URL=http://localhost:8081 infra/deploy/seed-demo.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] && { set -a; . "$ENV_FILE"; set +a; }

RAG_URL="${RAG_URL:-http://localhost:${RAG_ENGINE_PORT:-8081}}"
ADMIN_USER="${ADMIN_USER:-bsa-admin}"   # the P1 shim maps this to RESTRICTED clearance

echo "== Atlas demo seed =="
echo "   rag-engine: $RAG_URL"

# 1) rag-engine must be live (liveness does NOT call the GPU).
if ! curl -fsS -o /dev/null "$RAG_URL/actuator/health"; then
  echo "!! rag-engine not reachable at $RAG_URL — start it (mvn -pl rag-engine spring-boot:run" >&2
  echo "   or the compose 'app' profile) and retry." >&2
  exit 1
fi

# 2) Ingest the two-layer corpus (needs a resumed GPU for embeddings).
echo "== Ingesting the two-layer RBAC corpus (needs a resumed GPU) =="
HTTP=$(curl -sS -o /tmp/atlas-seed-ingest.json -w '%{http_code}' \
  -X POST "$RAG_URL/v1/admin/ingest" -H "X-Atlas-User: $ADMIN_USER")
if [ "$HTTP" != "200" ]; then
  echo "!! ingest failed (HTTP $HTTP). If 5xx, the GPU is likely paused — run 'make -C infra gpu-up'." >&2
  cat /tmp/atlas-seed-ingest.json >&2 || true
  exit 1
fi
echo "   ingest OK:"
( command -v jq >/dev/null && jq . /tmp/atlas-seed-ingest.json ) || cat /tmp/atlas-seed-ingest.json

# 3) Optional RBAC spot-check (proves the seed is permission-tagged). Skip with NO_VERIFY=1.
if [ "${NO_VERIFY:-0}" != "1" ]; then
  echo "== RBAC spot-check: same question, two clearances =="
  Q='{"query":"Summarize the open AML exceptions for the Northwind account this quarter."}'
  echo "   priya (compliance) — expects compliance/restricted citations:"
  curl -fsS -X POST "$RAG_URL/v1/query" -H "X-Atlas-User: priya" \
    -H 'Content-Type: application/json' -d "$Q" \
    | { command -v jq >/dev/null && jq '{citations: (.citations | length)}' || cat; } || true
  echo "   guest-public — expects NO compliance/restricted citations (RBAC):"
  curl -fsS -X POST "$RAG_URL/v1/query" -H "X-Atlas-User: guest-public" \
    -H 'Content-Type: application/json' -d "$Q" \
    | { command -v jq >/dev/null && jq '{citations: (.citations | length)}' || cat; } || true
fi

cat <<'EOF'

== Demo users (P1 dev shim — header X-Atlas-User) ==
  guest-public   → public      (no compliance/restricted access)
  analyst-bob    → analyst      (MD&A / narrative)
  priya          → compliance   (the forcing-story protagonist)
  bsa-admin      → restricted   (admin ingest)

Now run the walkthrough in docs/DEMO.md (UI) or the automated version:
  cd ui && npm run e2e:demo
EOF
