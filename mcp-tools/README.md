# Atlas :: mcp-tools

Governed **MCP Tool Server** (P4) — the Java/Spring "moat." It exposes a single state-changing
enterprise action over **MCP Streamable HTTP** (spec `2025-11-25`), with production-grade governance
around the write: OAuth 2.1 resource-server auth (RFC 8707), a per-call clearance re-check, a
transactional draft-SAR write, and an append-only, tamper-evident audit log.

> **Status — P4 task 2.** The Spring AI MCP server (WebMVC, Streamable HTTP) is up with actuator
> health/metrics and **no tools registered yet**, and the **append-only, hash-chained audit log** now
> exists (`agent.tool_audit`, ADR-0048). The governed `open_draft_sar` tool + `sar_draft` table, the
> OAuth 2.1 resource server, and the per-call clearance re-check are layered on in the remaining P4 tasks
> (see `docs/phases/P4_SPEC.md`).

## Purpose
Turn an answer into a **governed action**: when the agent (`/agents`) decides an AML exception breaches
the reporting threshold and a human approves, it calls this server's `open_draft_sar` tool to create a
DRAFT Suspicious Activity Report for review — never auto-filed, fully audited.

## Audit log (ADR-0048) — append-only + tamper-evident
- **Two DB identities (least privilege):** the runtime pool connects as the restricted role
  `atlas_mcp_app` (INSERT/SELECT only on `agent.tool_audit`); **Flyway** runs as a privileged role that
  creates the `agent` schema, the app role, the GRANTs, and the guard. Configured via
  `spring.datasource.*` (app) vs `spring.flyway.user/password` (privileged).
- **Append-only at the DB layer, two ways:** (1) the GRANT model (UPDATE/DELETE never granted to the app
  role) and (2) a `BEFORE UPDATE/DELETE` trigger that raises — which holds even against the table owner
  (a Postgres owner keeps UPDATE/DELETE regardless of REVOKE).
- **Tamper-evident:** each row is `row_hash = sha256(prev_hash || canonical_fields)`, chained from a
  genesis link. `AuditChainVerifier` recomputes the chain and reports the first broken `seq` — so even if
  a privileged actor disables the guard and rewrites history, it is detectable.
- **Reproducible hashes:** the app sets `ts` (truncated to microseconds) and appends under a
  transaction-scoped advisory lock, keeping the chain strictly linear.

## Architecture (target, P4)
- **MCP server** — Spring AI MCP server starter on WebMVC, Streamable HTTP (`spring.ai.mcp.server.protocol=STREAMABLE`); SSE is deprecated (ADR-0043 / ADR-0050).
- **OAuth 2.1 resource server** — validates signature + `exp` + `iss` + **`aud`** (RFC 8707 resource indicators); re-derives clearance from the token.
- **`ClearanceRecheck`** — refuses any call below `compliance`, independently of upstream RBAC (defense-in-depth, LLM06 / ASI03).
- **`open_draft_sar` tool** — the one governed write; transactional `sar_draft` insert + structured output (`{draftRef,status,createdAt}`).
- **Audit log** — append-only, hash-chained `tool_audit` (UPDATE/DELETE revoked at the DB role); `AuditChainVerifier` proves tamper-evidence (ADR-0048).

## Stack
- Spring Boot 3.5.15 · Spring AI 1.1.8 (`spring-ai-starter-mcp-server-webmvc`) · Java 21
- Postgres 16 (shared, `agent` schema; ADR-0002/0047) — wired in P4 task 2
- Versions centralized in the root `pom.xml` (monorepo BOM/plugin management).

## Run
```bash
# Build the runnable (-exec) jar
mvn -pl mcp-tools -am package

# Run locally (defaults: port 8082)
MCP_TOOLS_PORT=8082 java -jar mcp-tools/target/mcp-tools-*-exec.jar

# Or via Docker Compose (app profile)
docker compose -f infra/docker-compose.yml --profile app up mcp-tools
```

Endpoints:
- `GET  /actuator/health` — liveness
- `GET  /actuator/prometheus` — metrics scrape
- `POST /mcp` — MCP Streamable HTTP (JSON-RPC). Handshake: `initialize` → `Mcp-Session-Id` → `tools/list`.

## Test
```bash
mvn -pl mcp-tools test     # skeleton smoke tests (context, health, MCP handshake → 0 tools)
mvn -pl mcp-tools verify   # + integration tests (added across P4)
```
All P4 tasks are model-free for this module; no GPU is required.

## Config (env-swappable — see root `.env.example`)
| Var | Default | Meaning |
|---|---|---|
| `MCP_TOOLS_PORT` | `8082` | HTTP port |
| `ATLAS_MCP_SERVER_NAME` | `atlas-mcp-tools` | MCP `serverInfo.name` |
| `ATLAS_MCP_SERVER_VERSION` | `0.1.0` | MCP `serverInfo.version` |
| `ATLAS_MCP_DB_URL` | `jdbc:postgresql://localhost:5432/atlas` | shared Postgres (agent schema) |
| `ATLAS_MCP_DB_USERNAME` / `_PASSWORD` | `atlas` / `atlas` | **privileged** Flyway/migration identity |
| `ATLAS_MCP_DB_APP_USERNAME` / `_PASSWORD` | `atlas_mcp_app` / — | **least-privilege** runtime identity |

OAuth 2.1 (RFC 8707) audience/issuer/key and the breach-threshold vars are introduced in the tasks that
consume them.
