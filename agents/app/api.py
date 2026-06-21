"""FastAPI run API for the Atlas Agent Orchestrator (P4_SPEC §1, §2.3).

P4 task 6 ships the module skeleton: liveness/health, the run-API surface (request/response
contracts + routes), and the durable Postgres checkpointer wired against the `agent` schema. The
planner->executor graph that services a run is task 7; the human-in-the-loop resume is task 8.
Until then the run endpoints return 501 with a clear message — the contract is fixed, the brains
are not yet wired.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from app.checkpointer import ping_db
from app.config import get_settings
from app.models import ResumeRequest, RunRequest, RunResponse

app = FastAPI(title="Atlas Agent Orchestrator", version="0.1.0")

_NOT_WIRED = "agent graph not wired yet (P4 task 7/8)"


@app.get("/healthz")
def healthz() -> dict:
    """Liveness + best-effort checkpointer DB connectivity (never fails liveness)."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": "agents",
        "db": "up" if ping_db(settings) else "down",
        "gatewayBaseUrl": settings.gateway_base_url,
        "mcpBaseUrl": settings.mcp_base_url,
    }


@app.post("/v1/agent/runs", response_model=RunResponse)
def start_run(request: RunRequest) -> RunResponse:
    """Start an agent run (validated here; serviced by the graph in task 7)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_WIRED)


@app.post("/v1/agent/runs/{run_id}/resume", response_model=RunResponse)
def resume_run(run_id: str, request: ResumeRequest) -> RunResponse:
    """Resume a paused run with the human approval decision (task 8)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_WIRED)


@app.get("/v1/agent/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    """Fetch a run's current state (task 7+)."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_WIRED)
