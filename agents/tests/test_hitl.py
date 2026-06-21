"""Human-in-the-loop gate + MCP action tests (MemorySaver + fake MCP/token — no DB, no server).

Covers the P4 safety invariants: breach → pause; approve → exactly one governed write; reject → no
write; single-use approval (no duplicate write on replay); and the structural guarantee that act_sar
is only reachable through the approve gate.
"""

import base64
import json

from langgraph.checkpoint.memory import MemorySaver

from app.graph import build_graph
from app.runner import GraphRunner

THRESHOLD = 10_000.0

BREACH_PAYLOAD = {
    "answer": "1 open AML exception for Northwind; amount $12,500.00",
    "citations": [
        {"n": 1, "documentId": "l2-nw", "clearance": "compliance", "snippet": "$12,500.00"}
    ],
}


def fake_jwt(sub="priya"):
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"hdr.{payload}.sig"


class StubGateway:
    def query(self, query, top_k, bearer):
        return BREACH_PAYLOAD


class FakeMcp:
    def __init__(self):
        self.calls = []

    def open_draft_sar(self, bearer, run_id, account, period, rationale, citations):
        self.calls.append(
            {
                "bearer": bearer,
                "run_id": run_id,
                "account": account,
                "period": period,
                "rationale": rationale,
                "citations": citations,
            }
        )
        return {
            "draftRef": "SAR-2026-000001",
            "status": "DRAFT",
            "createdAt": "2026-06-21T10:00:00Z",
        }


def _runner(mcp):
    graph = build_graph(
        StubGateway(),
        THRESHOLD,
        MemorySaver(),
        mcp_client=mcp,
        token_provider=lambda user: f"aud-tok-for-{user}",
    )
    return GraphRunner(graph, max_steps=12)


def test_approve_writes_exactly_once_with_grounded_args():
    mcp = FakeMcp()
    runner = _runner(mcp)
    start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt("priya"))
    assert start.status == "AWAITING_APPROVAL"

    final = runner.resume(start.runId, approved=True, note="reviewed")
    assert final.status == "COMPLETED"
    assert final.action["draftRef"] == "SAR-2026-000001"
    assert len(mcp.calls) == 1
    call = mcp.calls[0]
    assert call["run_id"] == start.runId
    assert call["account"] == "Northwind"
    assert call["period"] == "2026-Q2"
    assert call["citations"] == [1]
    assert call["bearer"] == "aud-tok-for-priya"  # aud-scoped token minted for the caller


def test_reject_performs_no_write():
    mcp = FakeMcp()
    runner = _runner(mcp)
    start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt())
    final = runner.resume(start.runId, approved=False, note="not warranted")
    assert final.status == "REJECTED"
    assert mcp.calls == []


def test_single_use_approval_no_duplicate_write():
    mcp = FakeMcp()
    runner = _runner(mcp)
    start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt())
    runner.resume(start.runId, approved=True, note=None)
    # Replay the approval: a consumed approval must not authorize a second write (ASI07).
    again = runner.resume(start.runId, approved=True, note=None)
    assert again.status == "COMPLETED"
    assert len(mcp.calls) == 1


def test_get_returns_awaiting_then_completed():
    mcp = FakeMcp()
    runner = _runner(mcp)
    start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt())
    assert runner.get(start.runId).status == "AWAITING_APPROVAL"
    runner.resume(start.runId, approved=True, note=None)
    assert runner.get(start.runId).status == "COMPLETED"


def test_unknown_run_resume_and_get_return_none():
    runner = _runner(FakeMcp())
    assert runner.resume("run_missing", approved=True, note=None) is None
    assert runner.get("run_missing") is None


def test_act_sar_is_only_reachable_through_the_approve_gate():
    graph = build_graph(StubGateway(), THRESHOLD, MemorySaver())
    edges = graph.get_graph().edges
    predecessors = {e.source for e in edges if e.target == "act_sar"}
    assert predecessors == {"approve"}, predecessors
