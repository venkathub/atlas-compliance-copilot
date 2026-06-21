"""Run orchestration: drive the compiled graph and shape the run API response (P4_SPEC §2.3)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.models import Citation, ProposedAction, RunResponse


class GraphRunner:
    """Starts agent runs against the compiled graph. Resume (task 8) extends this."""

    def __init__(self, graph: Any, max_steps: int):
        self._graph = graph
        self._max_steps = max_steps

    def start(self, query: str, account: str, period: str, bearer: str) -> RunResponse:
        run_id = "run_" + uuid4().hex[:12]
        config = {
            "configurable": {"thread_id": run_id},
            # Step/iteration cap (ASI10) — the graph is a DAG, so this ceiling is never reached;
            # the floor keeps a misconfigured low value from breaking a legitimate run.
            "recursion_limit": max(self._max_steps, 8),
        }
        state_in = {
            "query": query,
            "account": account,
            "period": period,
            "bearer": bearer,
            "trace": [],
            "step_count": 0,
        }
        final = self._graph.invoke(state_in, config)
        return to_response(run_id, final)


def to_response(run_id: str, state: dict[str, Any]) -> RunResponse:
    proposed = state.get("proposed_action")
    citations = [
        Citation(**c) for c in state.get("contexts", []) or [] if c.get("n") is not None
    ]
    return RunResponse(
        runId=run_id,
        status=state.get("status", "COMPLETED"),
        answer=state.get("answer"),
        citations=citations,
        proposedAction=ProposedAction(**proposed) if proposed else None,
        trace=state.get("trace", []) or [],
    )
