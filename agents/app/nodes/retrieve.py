"""Retrieve node — fetches grounded, RBAC-filtered context through the P3 Gateway (ADR-0045).

Calls the Gateway with the caller's Bearer (so clearance is enforced upstream), captures the cited
contexts + answer, and extracts candidate currency amounts for the deterministic assess step.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.amounts import extract_amounts


def make_retrieve_node(gateway: Any, top_k: int = 6) -> Callable[[dict], dict]:
    """Build the retrieve node bound to a Gateway client (injected for testability)."""

    def retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
        resp = gateway.query(state["query"], top_k, state["bearer"])
        answer = resp.get("answer", "") or ""
        citations = resp.get("citations", []) or []
        contexts = [
            {
                "n": c.get("n"),
                "documentId": c.get("documentId"),
                "clearance": c.get("clearance"),
                "snippet": c.get("snippet"),
            }
            for c in citations
        ]
        amounts = extract_amounts(answer)
        for c in contexts:
            amounts += extract_amounts(c.get("snippet"))
        trace = state.get("trace", []) + [{"node": "retrieve", "citations": len(contexts)}]
        return {
            "answer": answer,
            "contexts": contexts,
            "amounts": amounts,
            "trace": trace,
            "step_count": state.get("step_count", 0) + 1,
        }

    return retrieve_node
