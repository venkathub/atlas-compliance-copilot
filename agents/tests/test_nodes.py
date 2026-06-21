"""Unit tests for the deterministic assess node + the planner + retrieve nodes."""

from app.nodes.assess import make_assess_node
from app.nodes.planner import PLAN, planner_node
from app.nodes.retrieve import make_retrieve_node

THRESHOLD = 10_000.0


class StubGateway:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def query(self, query, top_k, bearer):
        self.calls.append((query, top_k, bearer))
        return self.payload


def _state(account="Northwind", period="2026-Q2", **extra):
    base = {"account": account, "period": period, "trace": [], "step_count": 0}
    base.update(extra)
    return base


def test_planner_lays_out_fixed_plan():
    out = planner_node(_state(query="q"))
    assert out["plan"] == PLAN
    assert out["plan"][0] == "retrieve"


def test_retrieve_forwards_bearer_and_extracts_amounts():
    gw = StubGateway(
        {
            "answer": "1 exception of $12,500.00 for Northwind",
            "citations": [
                {
                    "n": 1,
                    "documentId": "d1",
                    "clearance": "compliance",
                    "snippet": "amount $12,500.00",
                },
            ],
        }
    )
    node = make_retrieve_node(gw, top_k=6)
    out = node(_state(query="aml?", bearer="tok-123"))
    assert gw.calls == [("aml?", 6, "tok-123")]
    assert len(out["contexts"]) == 1
    assert 12500.0 in out["amounts"]


def test_assess_flags_breach_when_amount_exceeds_threshold():
    state = _state(
        contexts=[{"n": 2, "snippet": "exception #2 amount $12,500.00"}],
        amounts=[12500.0],
    )
    out = make_assess_node(THRESHOLD)(state)
    assert out["breach"] is True
    assert out["breach_amount"] == 12500.0
    assert out["proposed_action"]["tool"] == "open_draft_sar"
    assert out["proposed_action"]["args"]["citations"] == [2]
    assert "exceeds" in out["proposed_action"]["args"]["rationale"]


def test_assess_no_breach_below_threshold():
    state = _state(
        contexts=[{"n": 1, "snippet": "small $250 item"}],
        amounts=[250.0],
    )
    out = make_assess_node(THRESHOLD)(state)
    assert out["breach"] is False
    assert out["proposed_action"] is None


def test_assess_at_threshold_is_a_breach():
    out = make_assess_node(THRESHOLD)(_state(contexts=[], amounts=[10_000.0]))
    assert out["breach"] is True
