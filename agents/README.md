# Atlas :: agents

Agent Orchestrator (P4) — the Python / LangGraph "brain" that turns a grounded answer into a
**governed action**. It plans, retrieves through the P3 Gateway (inheriting RBAC, cost-routing, cache,
PII redaction), evaluates the deterministic breach condition, **pauses for human approval**, and only
then calls the `mcp-tools` `open_draft_sar` action — every run durably checkpointed and traced.

> **Status — P4 task 8.** The full forcing-story agent works: breach → durable **HITL interrupt**
> (run pauses, state checkpointed) → human **resume** → governed **`open_draft_sar`** write over MCP
> (aud-scoped Bearer from the Gateway resource-token endpoint). `resume` is **single-use** (ASI07) and
> survives **process restart** (durable Postgres checkpointer, G8); `act_sar` is structurally reachable
> only via the approval gate. An end-to-end IT (`tests/test_e2e_forcing_story.py`, Testcontainers
> Postgres) exercises the full lifecycle through the real graph + checkpointer + real Gateway/MCP
> clients (HTTP boundary faked), asserting the safety hard gates. Runs are **traced** (OTel → Langfuse,
> opt-in) and **metered** (Prometheus `/metrics` → Grafana agent panel). A **merge-blocking agent eval
> gate** (`app/eval/`, 12 scenarios) is wired into CI — offline, no GPU.
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
| `OTEL_TRACES_EXPORT_ENABLED` | `false` | opt-in span export to Langfuse (OTLP); fail-soft |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Langfuse OTLP URL | trace export endpoint |
| `LANGFUSE_OTEL_AUTH_HEADER` | — | `Authorization` header for the OTLP export |

### Observability (task 10)
- **Tracing (ADR-0030):** root `agent.run` span + child `agent.node.*` spans (planner/retrieve/assess/
  approve/act_sar), `run_id` attribute. Export is opt-in (`OTEL_TRACES_EXPORT_ENABLED`) and fail-soft;
  off by default so tests/CI never reach Langfuse. Metadata-only (no chunk text / PII).
- **Metrics:** Prometheus at `/metrics` — `atlas_agent_runs_total{status}`, `_runs_started_total`,
  `_awaiting_approval_total`, `_tool_calls_total{outcome}`, `_failures_total`, `_approval_latency_seconds`.
  Grafana dashboard: `infra/grafana/dashboards/atlas-agents.json`.
- **Structured logging + correlation (P6, ADR-0062):** stdlib JSON logs (no extra dependency) via
  `app/logging_config.py`, selected by `ATLAS_LOG_FORMAT` (`plain` dev / `json`|`ecs` prod) at
  `ATLAS_LOG_LEVEL`. A FastAPI middleware establishes an `X-Request-Id` per request (reuse a well-formed
  inbound id from the gateway, else mint a UUID — validated against a strict allow-list, anti log-injection),
  binds it to every log line via a contextvar, echoes it on the response, and **forwards it to the
  gateway/MCP hops** so a run stitches across services in logs and traces.


### Agent eval gate (task 11, merge-blocking)
A versioned scenario set (`app/eval/scenarios.py`, 12 scenarios: forcing story, no-breach,
wrong-clearance, injection-in-source, rejection, at-threshold, multi-exception, tool-deny, …) scored
**trajectory-first** (`app/eval/agent_scorer.py`: task-success, tool-selection, argument-correctness,
step-efficiency, plan-adherence + the **HITL-respected** and **authorization-respected** hard gates).
Because the agent is deterministic, the gate runs **fully offline (no GPU, no cassettes)** against the
real graph with a stubbed Gateway/MCP. Thresholds live in `data/agent-baseline.json`.

```bash
uv run --directory agents python -m app.eval.agent_gate   # prints AGENT GATE: PASS/FAIL; non-zero blocks merge
```
