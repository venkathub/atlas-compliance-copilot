"""The planner-executor StateGraph (ADR-0041, ADR-0044).

Topology is fixed code (not an LLM loop), which is what makes the conditional and the HITL gate
*real graph structure*:

    planner → retrieve → assess → (breach? approve : finalize)
                                      approve → (approved? act_sar : rejected)

`approve` is a durable `interrupt()` — the run pauses (state checkpointed) until a human resumes
with `Command(resume={"approved": ...})`. `act_sar` (the governed write) is reachable ONLY from
`approve`, so no write occurs without a recorded approval.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.nodes.act import make_act_sar_node
from app.nodes.assess import make_assess_node
from app.nodes.planner import planner_node
from app.nodes.retrieve import make_retrieve_node
from app.state import AgentState
from app.tracing import instrument_node


def _approve_node(state: dict[str, Any]) -> dict[str, Any]:
    # Durable HITL gate: pause with a dry-run preview; resume value carries the human decision.
    decision = interrupt(
        {
            "proposedAction": state.get("proposed_action"),
            "breachDetail": state.get("breach_detail"),
            "citations": state.get("contexts", []),
        }
    )
    approved = bool(decision.get("approved"))
    trace = state.get("trace", []) + [{"node": "approve", "approved": approved}]
    return {"approval": decision, "trace": trace, "step_count": state.get("step_count", 0) + 1}


def _clarify_node(state: dict[str, Any]) -> dict[str, Any]:
    # Mid-task field confirmation (D-P4-4 "elicitation/clarify"): the breach amount wasn't
    # machine-readable, so pause and ask the human to confirm whether a breach occurred. Uses
    # the same durable graph interrupt as the approval gate (the authoritative HITL mechanism).
    decision = interrupt(
        {
            "clarify": "Could not determine the exception amount from the cited context; "
            "confirm whether a reporting-threshold breach occurred.",
            "citations": state.get("contexts", []),
        }
    )
    breach = bool(decision.get("breach"))
    trace = state.get("trace", []) + [{"node": "clarify", "breach": breach}]
    if not breach:
        return {"breach": False, "trace": trace, "step_count": state.get("step_count", 0) + 1}
    detail = "Human-confirmed breach (amount not machine-readable in the source)"
    contexts = state.get("contexts", [])
    proposed = {
        "tool": "open_draft_sar",
        "args": {
            "account": state["account"],
            "period": state["period"],
            "rationale": detail,
            "citations": sorted({c.get("n") for c in contexts if c.get("n") is not None}),
        },
    }
    return {
        "breach": True,
        "breach_detail": detail,
        "proposed_action": proposed,
        "trace": trace,
        "step_count": state.get("step_count", 0) + 1,
    }


def _rejected_node(state: dict[str, Any]) -> dict[str, Any]:
    note = (state.get("approval") or {}).get("note")
    trace = state.get("trace", []) + [{"node": "rejected"}]
    return {
        "status": "REJECTED",
        "result": {"note": note} if note else None,
        "trace": trace,
        "step_count": state.get("step_count", 0) + 1,
    }


def _finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    trace = state.get("trace", []) + [{"node": "finalize"}]
    return {"status": "COMPLETED", "trace": trace, "step_count": state.get("step_count", 0) + 1}


def _breach_branch(state: dict[str, Any]) -> str:
    """Deterministic conditional edge: breach → approval gate; ambiguous → clarify; else end."""
    if state.get("breach"):
        return "approve"
    if state.get("ambiguous"):
        return "clarify"
    return "finalize"


def _clarify_branch(state: dict[str, Any]) -> str:
    """After clarification: a confirmed breach still needs the approval gate; else finalize."""
    return "approve" if state.get("proposed_action") else "finalize"


def _approval_branch(state: dict[str, Any]) -> str:
    """Route the resumed run: approved → governed write, else → rejected (no write)."""
    return "act_sar" if (state.get("approval") or {}).get("approved") else "rejected"


def build_graph(
    gateway: Any,
    threshold: float,
    checkpointer: Any,
    mcp_client: Any = None,
    token_provider: Any = None,
    top_k: int = 6,
    tool_retries: int = 2,
):
    """Compile the planner-executor graph with injected Gateway, MCP client + token provider."""
    builder = StateGraph(AgentState)
    builder.add_node("planner", instrument_node("planner", planner_node))
    builder.add_node("retrieve", instrument_node("retrieve", make_retrieve_node(gateway, top_k)))
    builder.add_node("assess", instrument_node("assess", make_assess_node(threshold)))
    builder.add_node("approve", instrument_node("approve", _approve_node))
    builder.add_node("clarify", instrument_node("clarify", _clarify_node))
    builder.add_node(
        "act_sar",
        instrument_node("act_sar", make_act_sar_node(mcp_client, token_provider, tool_retries)),
    )
    builder.add_node("rejected", instrument_node("rejected", _rejected_node))
    builder.add_node("finalize", instrument_node("finalize", _finalize_node))

    builder.set_entry_point("planner")
    builder.add_edge("planner", "retrieve")
    builder.add_edge("retrieve", "assess")
    builder.add_conditional_edges(
        "assess",
        _breach_branch,
        {"approve": "approve", "clarify": "clarify", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "clarify", _clarify_branch, {"approve": "approve", "finalize": "finalize"}
    )
    builder.add_conditional_edges(
        "approve", _approval_branch, {"act_sar": "act_sar", "rejected": "rejected"}
    )
    builder.add_edge("act_sar", END)
    builder.add_edge("rejected", END)
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
