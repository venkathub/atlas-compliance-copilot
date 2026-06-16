# gateway — Atlas API Gateway (Spring Boot)

The **single front door** in front of `rag-engine` (P3, **ADR-0033**). Built on **Spring Cloud
Gateway Server WebMVC** (Servlet/blocking — matches the blocking Spring AI core; see ADR-0033 and
P3_SPEC §8.1).

When complete, the gateway provides: simulated-IdP auth + verified-clearance trust boundary
(ADR-0034), a cost-aware model router (ADR-0035), a clearance-safe semantic cache (ADR-0036), PII
egress redaction + output sanitization (ADR-0037), rate limiting + budget caps + circuit breaker
(ADR-0038/0039, LLM10), and a cost-units cost model (ADR-0040) surfaced on a Grafana dashboard.

## Status — P3 task 1 (skeleton)

Module skeleton only: a Spring Cloud Gateway (WebMVC) app exposing **actuator health + Prometheus
metrics**. No proxy routes, auth, router, cache, or redaction yet — those land in P3 tasks 2–8.

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

`mvn -pl gateway -am test` runs the skeleton smoke tests (context loads, `/actuator/health` is `UP`,
`/actuator/prometheus` exposed). Integration (`*IT`) and `live`-tagged tests follow the rag-engine
conventions (Failsafe; `live` excluded by default, enabled via `-P live`).

## Config (env-swappable, never hardcoded — CLAUDE.md)

See the **API GATEWAY (P3)** section of `.env.example` for the full var set. Skeleton-relevant:

| Var | Default | Purpose |
|---|---|---|
| `GATEWAY_PORT` | `8080` | Gateway HTTP port |
| `ATLAS_GATEWAY_RAG_ENGINE_URL` | `http://localhost:8081` | Downstream rag-engine (wired into the query path in task 3) |
