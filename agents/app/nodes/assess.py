"""Assess node — the deterministic breach decision (ADR-0049 Q5).

`breach = max(amount in retrieved citations) >= configured threshold`. Pure function of the
retrieved citations (no LLM), so it is testable and cannot be steered by injected instructions in
source docs (ASI01). On a breach it builds the `open_draft_sar` proposed-action preview, grounded in
the breaching citations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.amounts import extract_amounts


def make_assess_node(threshold: float) -> Callable[[dict], dict]:
    """Build the assess node bound to the reporting threshold (injected for testability)."""

    def assess_node(state: dict[str, Any]) -> dict[str, Any]:
        contexts = state.get("contexts", [])
        per_citation = [
            (c.get("n"), amt)
            for c in contexts
            for amt in extract_amounts(c.get("snippet"))
        ]
        amounts = state.get("amounts", []) or []
        breach_amount = max(amounts) if amounts else None
        breach = breach_amount is not None and breach_amount >= threshold

        # Ambiguous: a money context is present (a `$` in answer/snippets) but no amount could be
        # parsed — the agent must ask for mid-task field confirmation (clarify) rather than guess.
        ambiguous = False
        if not breach and not amounts:
            text = (state.get("answer") or "") + " ".join(
                c.get("snippet") or "" for c in contexts
            )
            ambiguous = "$" in text

        breaching = sorted({n for (n, amt) in per_citation if amt >= threshold and n is not None})
        if breach and not breaching:
            # Amount only in the free answer (not attributable to a citation) → cite all contexts.
            breaching = sorted({c.get("n") for c in contexts if c.get("n") is not None})

        detail = None
        proposed = None
        if breach:
            detail = f"${breach_amount:,.2f} exceeds the ${threshold:,.2f} reporting threshold"
            proposed = {
                "tool": "open_draft_sar",
                "args": {
                    "account": state["account"],
                    "period": state["period"],
                    "rationale": detail,
                    "citations": breaching,
                },
            }

        trace = state.get("trace", []) + [
            {"node": "assess", "breach": breach, "ambiguous": ambiguous}
        ]
        return {
            "breach": breach,
            "breach_amount": breach_amount,
            "breach_detail": detail,
            "ambiguous": ambiguous,
            "proposed_action": proposed,
            "trace": trace,
            "step_count": state.get("step_count", 0) + 1,
        }

    return assess_node
