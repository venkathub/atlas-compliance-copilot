# Atlas :: mcp-tools

Governed **MCP Tool Server** (P4) — the Java/Spring "moat." It exposes a single state-changing
enterprise action over **MCP Streamable HTTP** (spec `2025-11-25`), with production-grade governance
around the write: OAuth 2.1 resource-server auth (RFC 8707), a per-call clearance re-check, a
transactional draft-SAR write, and an append-only, tamper-evident audit log.

> **Status — P4 task 4.** The MCP server exposes the governed `open_draft_sar` tool over Streamable HTTP,
> backed by the append-only hash-chained audit log (`agent.tool_audit`, ADR-0048) and a transactional
> `agent.sar_draft` write (ADR-0049), and the `/mcp` endpoint is now an **OAuth 2.1 resource server**
> (RFC 8707 audience-restricted JWT) with a **per-call clearance re-check** (ADR-0046, LLM06). Still to
> come: the single-use, graph-bound approval precondition (task 5) and the sim-IdP minting aud-scoped
> tokens (task 5) — see `docs/phases/P4_SPEC.md`.

## Purpose
Turn an answer into a **governed action**: when the agent (`/agents`) decides an AML exception breaches
the reporting threshold and a human approves, it calls this server's `open_draft_sar` tool to create a
DRAFT Suspicious Activity Report for review — never auto-filed, fully audited.

## `open_draft_sar` (ADR-0049) — the one governed write
- **Contract:** `open_draft_sar(account, period, rationale, citations, runId)` → structured output
  `{draftRef, status, createdAt}`. `period` must match `^[0-9]{4}-Q[1-4]$`; `rationale` ≤ 2000 chars;
  `citations` a non-empty integer array. Exposed via the annotation model (`@McpTool`/`@McpToolParam`),
  auto-discovered by the MCP server; a record return type yields **structured** tool output.
- **Atomic, audited write:** the tool records an `ATTEMPT` audit row, then `SarDraftService` writes the
  `sar_draft` row (status `DRAFT`) **and** the `SUCCESS` audit row in **one transaction** — a failure rolls
  back both (no orphan draft, no missing audit). Validation failures yield an `ERROR` audit row and no write.
- **Governance seam:** caller + clearance come from `ToolCallerContext` (task-3 default: configured identity);
  task 4 replaces it with the token-derived identity + the per-call clearance re-check, and task 5 adds the
  single-use approval precondition. The authoritative human-in-the-loop gate is the agent graph (task 8).

## OAuth 2.1 resource server (ADR-0046) — RFC 8707 + per-call clearance re-check
- **`/mcp` requires an audience-restricted Bearer JWT.** Spring Security validates **signature (HS256), `exp`,
  `iss`, and `aud`** (the `aud` must name this server — RFC 8707 resource indicator). Missing / expired /
  forged / wrong-`aud` / wrong-`iss` tokens get **401** before reaching the tool. `/actuator/**` stays open.
- **Per-call clearance re-check (LLM06 / ASI03).** `ToolCallerContext` derives the caller + clearance from the
  validated JWT (via the security context); `ClearanceRecheck` refuses anything below `compliance` →
  `InsufficientClearanceException` → an MCP tool error + a **`DENIED`** audit row (not a 401). This is
  defense-in-depth, independent of P1 RBAC and the token's validity.
- The HMAC signing key is shared with the sim-IdP (gateway), which mints the aud-scoped tokens in task 5.

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
| `ATLAS_MCP_TOKEN_SIGNING_KEY` | `change-me-locally` | HMAC secret shared with the sim-IdP (HS256) |
| `ATLAS_MCP_TOKEN_ISSUER` | `atlas-sim-idp` | expected token `iss` |
| `ATLAS_MCP_TOKEN_AUDIENCE` | `atlas-mcp-tools` | expected token `aud` (RFC 8707) |
| `ATLAS_MCP_REQUIRED_CLEARANCE` | `compliance` | minimum clearance for the per-call re-check |

OAuth 2.1 (RFC 8707) audience/issuer/key and the breach-threshold vars are introduced in the tasks that
consume them.
