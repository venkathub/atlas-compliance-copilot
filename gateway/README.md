# gateway — Atlas API Gateway (Spring Boot)

The **single front door** in front of `rag-engine` (P3, **ADR-0033**). Built on **Spring Cloud
Gateway Server WebMVC** (Servlet/blocking — matches the blocking Spring AI core; see ADR-0033 and
P3_SPEC §8.1).

When complete, the gateway provides: simulated-IdP auth + verified-clearance trust boundary
(ADR-0034), a cost-aware model router (ADR-0035), a clearance-safe semantic cache (ADR-0036), PII
egress redaction + output sanitization (ADR-0037), rate limiting + budget caps + circuit breaker
(ADR-0038/0039, LLM10), and a cost-units cost model (ADR-0040) surfaced on a Grafana dashboard.

## Status — P3 task 10 (eval-through-Gateway + cost-delta)

Implemented so far:
- Tasks 1–8 (gateway pipeline) + task 9 deferred (Presidio off-path).
- **Eval-through-Gateway + cost-delta** (task 10, R2/R3): the reused P2 RAGAS gate now runs **through the
  Gateway** (`ATLAS_EVAL_THROUGH_GATEWAY=true` → `GatewayRagClient` mints a JWT + calls `/v1/query`),
  proving routing/caching/redaction don't drop quality below the floor; wired as a CI step (replays the
  committed cassettes, offline). `evals/cost_report.py` produces the cost-delta ("X% cheaper at equal eval
  score") → `gateway-baseline.json`. **Partial:** the measured cost numbers need the live calibration lane
  (GPU); see `evals/README` + spec §6.1.

Remaining: docs + quantified portfolio bullet (task 11).

### Dashboards

`make -C infra up` provisions Grafana (`http://localhost:${GRAFANA_PORT:-3001}`) → **Atlas — Cost-aware
Gateway (P3)** (uid `atlas-cost-p3`): tokens/cost/latency per route/tier/user, cache hit-rate, rate-limit/
budget rejections, redaction counts, circuit-breaker state, and a cost-spike threshold panel. The gateway
is scraped at `host.docker.internal:${GATEWAY_PORT}` (run it on the host with `mvn -pl gateway
spring-boot:run`). The cost-spike panel carries a threshold band; the circuit-breaker panel is best-effort.

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

### Resource-scoped tokens for the MCP tool hop (ADR-0046, P4)

`POST /v1/auth/resource-token` mints an **audience-restricted (RFC 8707)**, short-lived clearance JWT
(`aud=atlas-mcp-tools`, unique `jti`) that the agent forwards to the `mcp-tools` server, which validates
it as an OAuth 2.1 resource server. It reuses the sim-IdP signing key + issuer, so the MCP server must
share them (`ATLAS_IDP_SIGNING_KEY == ATLAS_MCP_TOKEN_SIGNING_KEY`, issuer/audience aligned).

```bash
curl -fsS -X POST "$GW/v1/auth/resource-token" \
     -H 'Content-Type: application/json' -d '{"user":"priya"}' | jq .
# → { "token": "...", "audience": "atlas-mcp-tools", "clearance": "compliance", ... }
```

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
