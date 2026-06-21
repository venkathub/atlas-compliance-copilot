"""FastAPI run API for the Atlas Agent Orchestrator (P4_SPEC §1, §2.3).

`POST /v1/agent/runs` drives the planner-executor graph: a no-breach run completes; a breach run
pauses at the durable HITL gate (AWAITING_APPROVAL + a dry-run proposedAction). `POST .../resume`
carries the human decision (single-use); `GET .../{id}` returns the run state from the checkpointer.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, status
from prometheus_client import make_asgi_app

from app.checkpointer import _with_search_path, ensure_schema, ping_db
from app.config import Settings, get_settings
from app.gateway_client import GatewayClient
from app.graph import build_graph
from app.mcp_client import McpClient
from app.models import ResumeRequest, RunRequest, RunResponse
from app.runner import GraphRunner
from app.tracing import setup_tracing

app = FastAPI(title="Atlas Agent Orchestrator", version="0.1.0")

# OTel tracing (opt-in export; fail-soft) + Prometheus metrics endpoint for the Grafana agent panel.
setup_tracing(get_settings())
app.mount("/metrics", make_asgi_app())


@lru_cache
def _default_runner() -> GraphRunner:
    """Build the production runner lazily (durable checkpointer + Gateway + MCP clients)."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    settings = get_settings()
    ensure_schema(settings.db_url(), settings.agent_schema)
    pool = ConnectionPool(
        conninfo=_with_search_path(settings.db_url(), settings.agent_schema),
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=True,
    )
    saver = PostgresSaver(pool)
    saver.setup()
    gateway = GatewayClient(settings.gateway_base_url)
    graph = build_graph(
        gateway,
        settings.sar_reporting_threshold,
        saver,
        mcp_client=McpClient(settings.mcp_base_url),
        token_provider=gateway.resource_token,
        tool_retries=settings.agent_tool_retries,
    )
    return GraphRunner(graph, settings.agent_max_steps)


def get_runner() -> GraphRunner:
    """Run-API dependency (overridable in tests)."""
    return _default_runner()


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return authorization[len("Bearer ") :]


@app.get("/healthz")
def healthz(settings: Settings = Depends(get_settings)) -> dict:
    """Liveness + best-effort checkpointer DB connectivity (never fails liveness)."""
    return {
        "status": "ok",
        "service": "agents",
        "db": "up" if ping_db(settings) else "down",
        "gatewayBaseUrl": settings.gateway_base_url,
        "mcpBaseUrl": settings.mcp_base_url,
    }


@app.post("/v1/agent/runs", response_model=RunResponse)
def start_run(
    request: RunRequest,
    runner: GraphRunner = Depends(get_runner),
    authorization: str | None = Header(default=None),
) -> RunResponse:
    """Start an agent run; forwards the caller's Bearer to the Gateway for RBAC retrieval."""
    bearer = _bearer(authorization)
    return runner.start(request.query, request.account, request.period, bearer)


@app.post("/v1/agent/runs/{run_id}/resume", response_model=RunResponse)
def resume_run(
    run_id: str, request: ResumeRequest, runner: GraphRunner = Depends(get_runner)
) -> RunResponse:
    """Resume a paused run with the human decision (single-use; approval or clarification)."""
    response = runner.resume(
        run_id, approved=request.approved, note=request.note, breach=request.breach
    )
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown run")
    return response


@app.get("/v1/agent/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str, runner: GraphRunner = Depends(get_runner)) -> RunResponse:
    """Fetch a run's current state from the checkpointer."""
    response = runner.get(run_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown run")
    return response
