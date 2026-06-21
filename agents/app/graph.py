"""The planner-executor StateGraph (ADR-0041).

Topology is fixed code (not an LLM loop), which is what makes the conditional and the HITL gate
*real graph structure*: `planner → retrieve → assess → (breach? approve : finalize)`. In P4 task 7
the `approve` branch just marks AWAITING_APPROVAL and ends; task 8 turns `approve` into a durable
`interrupt` and adds the `act_sar` node after the human resumes — so no write is reachable without
passing the approval gate.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.nodes.assess import make_assess_node
from app.nodes.planner import planner_node
from app.nodes.retrieve import make_retrieve_node
from app.state import AgentState


def _approve_node(state: dict[str, Any]) -> dict[str, Any]:
    # Task 7 placeholder for the approval gate (task 8: interrupt() → resume → act_sar).
    trace = state.get("trace", []) + [{"node": "approve"}]
    return {
        "status": "AWAITING_APPROVAL",
        "trace": trace,
        "step_count": state.get("step_count", 0) + 1,
    }


def _finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    trace = state.get("trace", []) + [{"node": "finalize"}]
    return {"status": "COMPLETED", "trace": trace, "step_count": state.get("step_count", 0) + 1}


def _branch(state: dict[str, Any]) -> str:
    """Deterministic conditional edge: breach → approval gate, else finalize."""
    return "approve" if state.get("breach") else "finalize"


def build_graph(gateway: Any, threshold: float, checkpointer: Any, top_k: int = 6):
    """Compile the planner-executor graph with an injected Gateway client + checkpointer."""
    builder = StateGraph(AgentState)
    builder.add_node("planner", planner_node)
    builder.add_node("retrieve", make_retrieve_node(gateway, top_k))
    builder.add_node("assess", make_assess_node(threshold))
    builder.add_node("approve", _approve_node)
    builder.add_node("finalize", _finalize_node)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "retrieve")
    builder.add_edge("retrieve", "assess")
    builder.add_conditional_edges("assess", _branch, {"approve": "approve", "finalize": "finalize"})
    builder.add_edge("approve", END)
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
