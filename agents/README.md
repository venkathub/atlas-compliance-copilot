# Atlas :: agents

Agent Orchestrator (P4) — the Python / LangGraph "brain" that turns a grounded answer into a
**governed action**. It plans, retrieves through the P3 Gateway (inheriting RBAC, cost-routing, cache,
PII redaction), evaluates the deterministic breach condition, **pauses for human approval**, and only
then calls the `mcp-tools` `open_draft_sar` action — every run durably checkpointed and traced.

> **Status — P4 task 7.** The planner-executor **graph** is wired: `planner → retrieve → assess →
> (breach? approve : finalize)`. `POST /v1/agent/runs` retrieves through the Gateway (RBAC-inherited),
> deterministically assesses the breach, and pauses at the approval gate (`AWAITING_APPROVAL` + a dry-run
> `proposedAction`). The **HITL `interrupt`/resume + MCP `open_draft_sar` write** (task 8), tracing
> (task 10), and the **agent eval gate** (task 11) land next. `resume`/`get` return `501` until task 8.
>
> The forcing-story agent is **fully deterministic** (owner-confirmed): the breach decision + routing are a
> pure function of retrieved citations — no agent LLM call — so the safety path is unpromptable and the eval
> runs offline. `ATLAS_AGENT_MODEL` is reserved/unused in P4 (see DECISIONS ADR-0042 deviation note).

## Architecture (target, P4)
- **Run API** (`app/api.py`, FastAPI): `POST /v1/agent/runs`, `POST /v1/agent/runs/{id}/resume`,
  `GET /v1/agent/runs/{id}`, `GET /healthz`.
- **Graph** (`app/graph.py`, task 7): `plan → retrieve → assess → (breach?) → approve(interrupt) → act`.
- **Durable checkpointer** (`app/checkpointer.py`): LangGraph `PostgresSaver` over the `agent` schema —
  a run survives interrupt/restart (G8).
- **Clients** (task 7/8): Gateway `/v1/query` for retrieval; MCP Streamable HTTP for the action.

## Run
```bash
# Tests (model-free; the checkpointer IT needs Docker)
uv run --directory agents --group dev pytest -q
ruff check agents

# Local dev server (defaults: port 8083)
uv run --directory agents uvicorn app.api:app --port 8083

# Or via Docker Compose (app profile)
docker compose -f infra/docker-compose.yml --profile app up agents
```

Endpoints:
- `GET /healthz` — liveness + best-effort checkpointer DB connectivity
- `POST /v1/agent/runs` · `POST /v1/agent/runs/{id}/resume` · `GET /v1/agent/runs/{id}` — run API (501 until task 7/8)

## Config (env-swappable — see root `.env.example`)
| Var | Default | Meaning |
|---|---|---|
| `AGENT_PORT` | `8083` | HTTP port |
| `GATEWAY_BASE_URL` | `http://localhost:8080` | P3 Gateway for retrieval |
| `MCP_BASE_URL` | `http://localhost:8082/mcp` | MCP tool server (Streamable HTTP) |
| `ATLAS_AGENT_MODEL` | `qwen2.5:7b-instruct` | reasoning tier (ADR-0042) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | remote model endpoint |
| `AGENT_DB_URL` / `POSTGRES_*` | — / `atlas@localhost:5432/atlas` | checkpointer datasource (`agent` schema) |
| `ATLAS_AGENT_MAX_STEPS` | `12` | step/iteration cap (ASI10) |
| `ATLAS_SAR_REPORTING_THRESHOLD` | `10000` | deterministic breach threshold (ADR-0049, used in task 7) |
