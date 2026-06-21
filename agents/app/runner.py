"""Run orchestration: drive the compiled graph, persist via the checkpointer, and shape the run-API
response (P4_SPEC §2.3). Handles the durable HITL pause/resume and the single-use approval guard.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from langgraph.types import Command

from app.jwt_utils import jwt_sub
from app.models import Citation, ProposedAction, RunResponse

_APPROVE_NODE = "approve"


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
            "trace": [],
            "step_count": 0,
        }
        self._graph.invoke(state_in, self._config(run_id))
        return self._render(run_id)

    def resume(self, run_id: str, approved: bool, note: str | None) -> RunResponse | None:
        snapshot = self._graph.get_state(self._config(run_id))
        if not snapshot.values:
            return None  # unknown run → 404
        # Single-use approval (ASI07): only a run paused at the gate can be resumed; a consumed
        # approval (run already past the gate / terminal) cannot authorize a second/mutated write.
        if _APPROVE_NODE not in snapshot.next:
            return self._render(run_id)  # already resolved — return terminal state, no re-execution
        self._graph.invoke(
            Command(resume={"approved": approved, "note": note}), self._config(run_id)
        )
        return self._render(run_id)

    def get(self, run_id: str) -> RunResponse | None:
        snapshot = self._graph.get_state(self._config(run_id))
        if not snapshot.values:
            return None
        return self._render(run_id)

    def _render(self, run_id: str) -> RunResponse:
        snapshot = self._graph.get_state(self._config(run_id))
        values = snapshot.values
        status = "AWAITING_APPROVAL" if snapshot.next else values.get("status", "COMPLETED")
        return to_response(run_id, values, status)


def to_response(run_id: str, state: dict[str, Any], status: str) -> RunResponse:
    proposed = state.get("proposed_action")
    citations = [
        Citation(**c) for c in state.get("contexts", []) or [] if c.get("n") is not None
    ]
    result = state.get("result") or {}
    return RunResponse(
        runId=run_id,
        status=status,
        answer=state.get("answer"),
        citations=citations,
        proposedAction=ProposedAction(**proposed) if proposed else None,
        action=result.get("action"),
        trace=state.get("trace", []) or [],
    )
