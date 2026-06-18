# gateway — Atlas API Gateway (Spring Boot)

The **single front door** in front of `rag-engine` (P3, **ADR-0033**). Built on **Spring Cloud
Gateway Server WebMVC** (Servlet/blocking — matches the blocking Spring AI core; see ADR-0033 and
P3_SPEC §8.1).

When complete, the gateway provides: simulated-IdP auth + verified-clearance trust boundary
(ADR-0034), a cost-aware model router (ADR-0035), a clearance-safe semantic cache (ADR-0036), PII
egress redaction + output sanitization (ADR-0037), rate limiting + budget caps + circuit breaker
(ADR-0038/0039, LLM10), and a cost-units cost model (ADR-0040) surfaced on a Grafana dashboard.

## Status — P3 task 7 (PII egress redaction + output sanitization — LLM02/LLM05)

Implemented so far:
- **Module skeleton** (task 1) · **Sim IdP + trust boundary** (task 2) · **Query passthrough** (task 3) ·
  **Cost-aware router** (task 4) · **Semantic cache** (task 5) · **Resource controls** (task 6, LLM10).
- **PII egress redaction + output sanitization** (task 7, ADR-0037, LLM02/LLM05): deterministic
  `PiiRedactor` (structured finance-PII by regex + a configurable restricted-entity denylist) and
  `OutputSanitizer` (strip executable markup, escape residual HTML) run inline at ingress (prompt) +
  egress (answer + citation snippets, on both fresh and cache-hit paths). Metadata-only redaction traces;
  the response gains a `redaction` section. Hard gates: **0 PII strings + 0 unsafe payloads at egress**.

Not yet: cost metering + Grafana dashboard incl. cost-spike alert (task 8); off-path Presidio + LLM Guard
deep-scan (task 9). **Deferred:** real token-usage accounting (task 8); see earlier tasks for other deferrals.

### Response shape (incremental)

The relayed/cached `rag-engine` JSON now carries `routing` (task 4), `cache` (task 5), and `redaction`
(task 7) sections. The final §2.3 section — `cost` — is added in task 8.

## Auth — mint + use a clearance token (dev)

```bash
GW=http://localhost:${GATEWAY_PORT:-8080}

# 1) Mint a signed clearance JWT for a dev user (simulated IdP, ADR-0034)
TOKEN=$(curl -fsS -X POST "$GW/v1/auth/token" \
          -H 'Content-Type: application/json' \
          -d '{"user":"priya"}' | jq -r .token)

# 2) Call a protected route with the Bearer token (query path lands in task 3)
curl -i -X POST "$GW/v1/query" -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' -d '{"query":"...","topK":6}'
```

Dev users (simulated IdP directory, `dev/clearance-users.json`): `guest-public` (public),
`analyst-bob` (analyst), `priya` (compliance), `bsa-admin` (restricted). A missing/expired/forged
token → `401`; `/v1/auth/**` and `/actuator/**` are unauthenticated.

## Architecture (target)

```
client ──HTTP/JSON + Bearer JWT──▶ gateway ──HTTP/JSON + verified clearance + model-tier──▶ rag-engine
```

The gateway is the only component that resolves clearance from a client; `rag-engine` trusts only
the Gateway-asserted, verified clearance (supersedes the P1 `X-Atlas-Clearance` shim, ADR-0016).

## Run

```bash
# Build + test (model-free, no GPU/DB/Redis needed for the skeleton)
mvn -pl gateway -am test

# Run on the host (dev) — picks up GATEWAY_PORT / ATLAS_GATEWAY_* from your env/.env
set -a && . ./.env && set +a
mvn -pl gateway spring-boot:run

# Health + metrics
curl -fsS http://localhost:${GATEWAY_PORT:-8080}/actuator/health
curl -fsS http://localhost:${GATEWAY_PORT:-8080}/actuator/prometheus | head
```

Like `rag-engine`, the gateway runs **on the host** in dev and is scraped by Prometheus via
`host.docker.internal:${GATEWAY_PORT}`. A container image (`gateway/Dockerfile`, distroless/nonroot,
multi-arch) and a compose `gateway` service (under the `app` profile) exist for image parity and
full-stack bring-up.

## Tests

`mvn -pl gateway -am test` runs the model-free unit tests (auth, query controller). `mvn -pl gateway -am verify`
also runs the integration tests (`*IT`). Integration (`*IT`) and `live`-tagged tests follow the rag-engine
conventions (Failsafe; `live` excluded by default, enabled via `-P live`).

**Stub downstream (why MockWebServer):** `GatewayQueryIT` exercises the full path (JWT filter → controller →
`RestClient`) against an **OkHttp `MockWebServer`** standing in for `rag-engine`. A real localhost socket
round-trip lets the test assert the *on-the-wire* `X-Atlas-Internal-Clearance` assertion (decode + verify the
JWT, check the `clearance` claim) — something a pure in-JVM mock can't prove. It is also reused in task 6 to
simulate downstream delays/errors/disconnects for the circuit-breaker + timeout ITs. It is a lightweight,
test-scoped dependency (pinned `4.12.0`; not Boot-BOM-managed).

## Config (env-swappable, never hardcoded — CLAUDE.md)

See the **API GATEWAY (P3)** section of `.env.example` for the full var set. Skeleton-relevant:

| Var | Default | Purpose |
|---|---|---|
| `GATEWAY_PORT` | `8080` | Gateway HTTP port |
| `ATLAS_GATEWAY_RAG_ENGINE_URL` | `http://localhost:8081` | Downstream rag-engine (wired into the query path in task 3) |
