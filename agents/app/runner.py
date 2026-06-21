"""Run orchestration: drive the compiled graph, persist via the checkpointer, and shape the run-API
response (P4_SPEC §2.3). Handles the durable HITL pause/resume, the single-use approval guard, and
the observability hooks (root run span + Prometheus metrics).
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from app import metrics
from app.jwt_utils import jwt_sub
from app.models import Citation, ProposedAction, RunResponse
from app.tracing import run_span

_RESUMABLE = {"approve", "clarify"}
_TERMINAL = {"COMPLETED", "REJECTED", "FAILED"}


class GraphRunner:
    """Starts, resumes, and reads agent runs against the compiled graph."""

    def __init__(self, graph: Any, max_steps: int):
        self._graph = graph
        self._max_steps = max_steps

    def _config(self, run_id: str) -> dict:
        return {
            "configurable": {"thread_id": run_id},
            # Step/iteration cap (ASI10) — DAG depth is fixed; the floor protects legit runs.
            "recursion_limit": max(self._max_steps, 8),
        }

    def start(self, query: str, account: str, period: str, bearer: str) -> RunResponse:
        run_id = "run_" + uuid4().hex[:12]
        state_in = {
            "query": query,
            "account": account,
            "period": period,
            "bearer": bearer,
            "run_id": run_id,
            "caller": jwt_sub(bearer),
            "created_at": time.time(),
            "trace": [],
            "step_count": 0,
        }
        metrics.RUNS_STARTED.inc()
        with run_span(run_id, account=account):
            self._graph.invoke(state_in, self._config(run_id))
        response = self._render(run_id)
        if response.status in _TERMINAL:
            self._record_terminal(response)
        elif response.status == "AWAITING_APPROVAL":
            metrics.AWAITING_APPROVAL.inc()
        return response

    def resume(
        self, run_id: str, approved: bool | None = None, note: str | None = None,
        breach: bool | None = None,
    ) -> RunResponse | None:
        snapshot = self._graph.get_state(self._config(run_id))
        if not snapshot.values:
            return None  # unknown run → 404
        # Single-use approval (ASI07): only a run paused at a gate (approve/clarify) can resume; a
        # consumed decision (run past the gate / terminal) cannot authorize a 2nd/mutated write.
        if not (_RESUMABLE & set(snapshot.next)):
            return self._render(run_id)  # already resolved — return terminal state, no re-execution
        created_at = snapshot.values.get("created_at")
        payload = {"approved": approved, "note": note, "breach": breach}
        with run_span(run_id, account=snapshot.values.get("account"), approved=approved):
            self._graph.invoke(Command(resume=payload), self._config(run_id))
        response = self._render(run_id)
        if created_at is not None and response.status in _TERMINAL:
            metrics.APPROVAL_LATENCY.observe(max(0.0, time.time() - created_at))
        if response.status in _TERMINAL:
            self._record_terminal(response)
        return response

    def get(self, run_id: str) -> RunResponse | None:
        snapshot = self._graph.get_state(self._config(run_id))
        if not snapshot.values:
            return None
        return self._render(run_id)

    @staticmethod
    def _record_terminal(response: RunResponse) -> None:
        if response.status not in _TERMINAL:
            return
        metrics.RUNS_TOTAL.labels(status=response.status).inc()
        if response.status == "COMPLETED" and response.action is not None:
            metrics.TOOL_CALLS.labels(outcome="ok").inc()
        if response.status == "FAILED":
            metrics.TOOL_CALLS.labels(outcome="error").inc()
            metrics.FAILURES.inc()

    def _render(self, run_id: str) -> RunResponse:
        snapshot = self._graph.get_state(self._config(run_id))
        values = snapshot.values
        if "clarify" in snapshot.next:
            status = "AWAITING_CLARIFICATION"
        elif "approve" in snapshot.next:
            status = "AWAITING_APPROVAL"
        elif snapshot.next:
            status = "RUNNING"
        else:
            status = values.get("status", "COMPLETED")
        return to_response(run_id, values, status)


def to_response(run_id: str, state: dict[str, Any], status: str) -> RunResponse:
    proposed = state.get("proposed_action")
    citations = [
        Citation(**c) for c in state.get("contexts", []) or [] if c.get("n") is not None
    ]
    result = state.get("result") or {}
    action = result.get("action")
    return RunResponse(
        runId=run_id,
        status=status,
        answer=state.get("answer"),
        citations=citations,
        proposedAction=ProposedAction(**proposed) if proposed else None,
        action=action,
        auditRef=action.get("auditRef") if action else None,
        trace=state.get("trace", []) or [],
    )
