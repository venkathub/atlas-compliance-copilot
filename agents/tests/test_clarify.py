"""Tests for the ambiguous-input clarify / mid-task field-confirmation path (D-P4-4 elicitation)."""

import base64
import json

from langgraph.checkpoint.memory import MemorySaver

from app.graph import build_graph
from app.runner import GraphRunner

THRESHOLD = 10_000.0
# Money context present ($) but no parseable amount → ambiguous → clarify.
AMBIGUOUS = {
    "answer": "an exception was flagged; amount $ (pending)",
    "citations": [{"n": 1, "documentId": "d", "clearance": "compliance", "snippet": "amount $ —"}],
}


def fake_jwt(sub="priya"):
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"hdr.{payload}.sig"


class StubGateway:
    def query(self, query, top_k, bearer):
        return AMBIGUOUS


class FakeMcp:
    def __init__(self):
        self.calls = []

    def open_draft_sar(self, bearer, run_id, account, period, rationale, citations):
        self.calls.append({"run_id": run_id, "citations": citations})
        return {"draftRef": "SAR-1", "status": "DRAFT", "createdAt": "t", "auditRef": "audit_1"}


def _runner(mcp):
    graph = build_graph(
        StubGateway(), THRESHOLD, MemorySaver(), mcp_client=mcp, token_provider=lambda u: "tok"
    )
    return GraphRunner(graph, max_steps=12)


def test_ambiguous_input_pauses_for_clarification():
    runner = _runner(FakeMcp())
    start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt())
    assert start.status == "AWAITING_CLARIFICATION"
    assert start.proposedAction is None  # nothing proposed until the fact is confirmed


def test_clarify_confirm_breach_then_approve_writes():
    mcp = FakeMcp()
    runner = _runner(mcp)
    start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt())

    # Confirm the breach → now at the write-approval gate, with a grounded proposedAction.
    after_clarify = runner.resume(start.runId, breach=True)
    assert after_clarify.status == "AWAITING_APPROVAL"
    assert after_clarify.proposedAction is not None
    assert mcp.calls == []  # still no write

    # Approve → governed write.
    final = runner.resume(start.runId, approved=True)
    assert final.status == "COMPLETED"
    assert final.action["draftRef"] == "SAR-1"
    assert final.auditRef == "audit_1"
    assert len(mcp.calls) == 1


def test_clarify_no_breach_completes_without_write():
    mcp = FakeMcp()
    runner = _runner(mcp)
    start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt())
    final = runner.resume(start.runId, breach=False)
    assert final.status == "COMPLETED"
    assert mcp.calls == []
