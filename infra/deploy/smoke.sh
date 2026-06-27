#!/usr/bin/env bash
#
# Atlas deploy smoke test (P5 Task 10 — §4.5, G-P5-6).
#
# Proves the single-origin reverse proxy serves the UI over TLS and is wired correctly.
# HARD assertions (always run, GPU-free): the UI is served over TLS, the strict CSP +
# security headers are present, the SPA fallback works, and NO secret is in the served
# bundle. The login (+ query) round-trip is run when the backends are reachable and
# skipped-with-warning otherwise (the GPU-free CI lane vs the live GPU lane).
#
# Usage:
#   infra/deploy/smoke.sh [BASE_URL]
#     BASE_URL   default https://localhost:8443  (the local internal-TLS proxy)
# Env:
#   SMOKE_LOGIN_USER   default "priya"   (sim-IdP identity for the round-trip)
#
# Exit non-zero on any HARD failure. Self-signed/internal TLS is accepted (curl -k).
set -euo pipefail

BASE_URL="${1:-https://localhost:8443}"
LOGIN_USER="${SMOKE_LOGIN_USER:-priya}"
CURL=(curl -fsSk --max-time 15)

pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; exit 1; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

echo "== Atlas deploy smoke @ ${BASE_URL} =="

# 1. The UI is served over TLS (HTTP/2, 200, the SPA root element).
body="$("${CURL[@]}" "${BASE_URL}/" || fail "UI root not reachable over TLS")"
grep -q '<div id="root">' <<<"$body" || fail "served root is not the Atlas SPA"
pass "UI served over TLS"

# 2. Strict CSP + security headers (the LLM05 proxy wall — G-P5-2).
headers="$("${CURL[@]}" -D - -o /dev/null "${BASE_URL}/")"
grep -qi 'content-security-policy:.*script-src .self.' <<<"$headers" \
  || fail "missing/weak Content-Security-Policy (script-src 'self')"
grep -qi "content-security-policy:.*object-src 'none'" <<<"$headers" \
  || fail "CSP missing object-src 'none'"
for h in "x-content-type-options: nosniff" "referrer-policy:" "strict-transport-security:" "x-frame-options:"; do
  grep -qi "$h" <<<"$headers" || fail "missing security header: $h"
done
grep -qi '^server: caddy' <<<"$headers" && warn "Server header advertises caddy (expected hidden)" || true
pass "CSP + security headers present"

# 3. SPA fallback: a client-side route serves index.html (not a 404).
"${CURL[@]}" "${BASE_URL}/admin" | grep -q '<title>Atlas</title>' \
  || fail "SPA fallback for /admin did not serve index.html"
pass "SPA fallback works"

# 4. No secret in the served JS bundle (LLM02 — the bundle is public).
asset="$(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' <<<"$body" | head -1 || true)"
[ -n "$asset" ] || fail "could not locate the JS bundle in index.html"
js="$("${CURL[@]}" "${BASE_URL}/${asset}")"
if grep -aoiE 'signing[_-]?key|-----BEGIN [A-Z ]*PRIVATE KEY|_password=|_secret=' <<<"$js" >/dev/null; then
  fail "potential secret found in the served bundle (${asset})"
fi
pass "no secret in served bundle (${asset})"

# 5. Login round-trip over TLS (proxy -> Gateway). Soft: needs the Gateway up (GPU-free).
if token_json="$("${CURL[@]}" -X POST -H 'Content-Type: application/json' \
      -d "{\"user\":\"${LOGIN_USER}\"}" "${BASE_URL}/v1/auth/token" 2>/dev/null)"; then
  grep -q '"token"' <<<"$token_json" || fail "login round-trip returned no token"
  pass "login round-trip over TLS (POST /v1/auth/token)"
  # 6. Query round-trip (needs rag-engine + the GPU). Soft: warn if it can't answer.
  token="$(sed -n 's/.*"token":"\([^"]*\)".*/\1/p' <<<"$token_json")"
  if "${CURL[@]}" -X POST -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
        -d '{"query":"smoke test"}' "${BASE_URL}/v1/query" >/dev/null 2>&1; then
    pass "query round-trip over TLS (POST /v1/query)"
  else
    warn "POST /v1/query did not answer — needs rag-engine + the GPU (live-lane only)"
  fi
else
  warn "Gateway not reachable — login/query round-trip skipped (start the backends for the full smoke)"
fi

echo "== smoke PASS =="
