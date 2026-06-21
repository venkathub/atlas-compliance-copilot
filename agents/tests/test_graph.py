"""Graph-structure + routing tests (LangGraph MemorySaver; stubbed Gateway — no DB, no model)."""

from langgraph.checkpoint.memory import MemorySaver

from app.graph import build_graph
from app.runner import GraphRunner, to_response

THRESHOLD = 10_000.0


class StubGateway:
    def __init__(self, payload):
        self.payload = payload

    def query(self, query, top_k, bearer):
        return self.payload


def _runner(payload):
    graph = build_graph(StubGateway(payload), THRESHOLD, MemorySaver())
    return GraphRunner(graph, max_steps=12)


BREACH_PAYLOAD = {
    "answer": "1 open AML exception for Northwind; amount $12,500.00",
    "citations": [
        {"n": 1, "documentId": "l2-nw", "clearance": "compliance", "snippet": "$12,500.00"}
    ],
}
NO_BREACH_PAYLOAD = {
    "answer": "exceptions all under threshold; largest $250.00",
    "citations": [{"n": 1, "documentId": "l2-nw", "clearance": "compliance", "snippet": "$250.00"}],
}


def test_graph_has_expected_nodes():
    graph = build_graph(StubGateway(NO_BREACH_PAYLOAD), THRESHOLD, MemorySaver())
    nodes = set(graph.get_graph().nodes)
    for expected in {"planner", "retrieve", "assess", "approve", "finalize"}:
        assert expected in nodes


def test_breach_run_pauses_at_approval_gate():
    resp = _runner(BREACH_PAYLOAD).start("aml?", "Northwind", "2026-Q2", "tok")
    assert resp.status == "AWAITING_APPROVAL"
    assert resp.proposedAction is not None
    assert resp.proposedAction.tool == "open_draft_sar"
    assert resp.proposedAction.args["citations"] == [1]
    # The trace shows the deterministic path through the approval gate.
    visited = [t.get("node") for t in resp.trace]
    assert visited == ["planner", "retrieve", "assess", "approve"]


def test_no_breach_run_completes_without_action():
    resp = _runner(NO_BREACH_PAYLOAD).start("aml?", "Northwind", "2026-Q2", "tok")
    assert resp.status == "COMPLETED"
    assert resp.proposedAction is None
    visited = [t.get("node") for t in resp.trace]
    assert visited == ["planner", "retrieve", "assess", "finalize"]


def test_step_cap_is_respected_dag_completes_within_limit():
    # The graph is a DAG; the configured step cap (recursion_limit) is a safety ceiling never hit by
    # a legitimate run (no unbounded loop, ASI10).
    graph = build_graph(StubGateway(NO_BREACH_PAYLOAD), THRESHOLD, MemorySaver())
    runner = GraphRunner(graph, max_steps=12)
    resp = runner.start("aml?", "Northwind", "2026-Q2", "tok")
    assert resp.status == "COMPLETED"


def test_to_response_maps_citations():
    state = {
        "status": "COMPLETED",
        "answer": "ok",
        "contexts": [{"n": 1, "documentId": "d", "clearance": "compliance", "snippet": "s"}],
        "trace": [],
    }
    resp = to_response("run_x", state)
    assert resp.runId == "run_x"
    assert resp.citations[0].n == 1
