"""FastAPI run API for the Atlas Agent Orchestrator (P4_SPEC §1, §2.3).

Task 7 wires `POST /v1/agent/runs` to the planner-executor graph: a no-breach run completes; a
breach run pauses at the approval gate (AWAITING_APPROVAL + a dry-run proposedAction). The
human-in-the-loop resume and the MCP write land in task 8 (resume/get remain 501 until then).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, status

from app.checkpointer import _with_search_path, ensure_schema, ping_db
from app.config import Settings, get_settings
from app.gateway_client import GatewayClient
from app.graph import build_graph
from app.models import ResumeRequest, RunRequest, RunResponse
from app.runner import GraphRunner

app = FastAPI(title="Atlas Agent Orchestrator", version="0.1.0")

_NOT_WIRED = "not implemented yet (P4 task 8)"


@lru_cache
def _default_runner() -> GraphRunner:
    """Build the production runner lazily (durable Postgres checkpointer + Gateway client)."""
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
    graph = build_graph(
        GatewayClient(settings.gateway_base_url), settings.sar_reporting_threshold, saver
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
def resume_run(run_id: str, request: ResumeRequest) -> RunResponse:
    """Resume a paused run with the human approval decision (task 8)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_WIRED)


@app.get("/v1/agent/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    """Fetch a run's current state (task 8)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_WIRED)
