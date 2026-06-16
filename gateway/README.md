# gateway — Atlas API Gateway (Spring Boot)

The **single front door** in front of `rag-engine` (P3, **ADR-0033**). Built on **Spring Cloud
Gateway Server WebMVC** (Servlet/blocking — matches the blocking Spring AI core; see ADR-0033 and
P3_SPEC §8.1).

When complete, the gateway provides: simulated-IdP auth + verified-clearance trust boundary
(ADR-0034), a cost-aware model router (ADR-0035), a clearance-safe semantic cache (ADR-0036), PII
egress redaction + output sanitization (ADR-0037), rate limiting + budget caps + circuit breaker
(ADR-0038/0039, LLM10), and a cost-units cost model (ADR-0040) surfaced on a Grafana dashboard.

## Status — P3 task 4 (cost-aware model router)

Implemented so far:
- **Module skeleton** (task 1): Spring Cloud Gateway WebMVC app + actuator health/Prometheus.
- **Simulated IdP + verified-clearance trust boundary** (task 2, ADR-0034).
- **Query passthrough** (task 3): `POST /v1/query` proxies to `rag-engine` with the verified clearance.
- **Cost-aware model router** (task 4, ADR-0035/0040): default tier1-small; escalate to tier2-mid only
  on `X-Atlas-Quality: high` or a long query; frontier reserved + never auto-selected; eval-floor guard.
  The selected tier is forwarded as `X-Atlas-Model-Tier`; `rag-engine` maps it to the chat model. The
  response now carries a `routing` section. A `CostTable` (cost-units/1k per tier) backs later metering.

Not yet: semantic cache (task 5), rate-limit/budget/breaker (task 6), PII redaction + output
sanitization (task 7), cost metering (task 8). **Deferred (see DECISIONS ADR-0035 note / spec §6.1):**
the model-cascade + `retrieved_context_tokens` rule (post-generation signals).

### Response shape (incremental)

The relayed `rag-engine` JSON (`answer` + `citations` + `retrieval`) is now augmented with a `routing`
section (`{modelTier, model, escalated}`) — the first §2.3 envelope section. The remaining sections
(`cache` / `redaction` / `cost`) are added in tasks 5–8; Task 4 does not fabricate them.

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
