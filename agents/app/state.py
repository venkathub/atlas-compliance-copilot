"""Typed agent state for the LangGraph planner-executor graph (P4_SPEC §2.2).

The forcing-story graph is deliberately deterministic (ADR-0041 + the owner-confirmed "fully
deterministic agent" decision): the breach decision and routing are a function of retrieved
citations, never free-LLM judgement — which is what makes the safety invariants testable and
unpromptable.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # --- inputs ---
    query: str
    account: str
    period: str
    bearer: str  # the caller's JWT, forwarded to the Gateway (verified-clearance, ADR-0034)
    run_id: str  # the originating run (thread) id — used as open_draft_sar's runId
    caller: str  # the caller's subject (from the bearer) — used to mint the aud-scoped MCP token

    # --- planner ---
    plan: list[str]

    # --- retrieve (via the Gateway) ---
    answer: str
    contexts: list[dict[str, Any]]  # cited contexts: {n, documentId, clearance, snippet}
    amounts: list[float]  # currency amounts extracted from the answer + citation snippets

    # --- assess (deterministic breach check) ---
    breach: bool
    breach_amount: float | None
    breach_detail: str | None
    proposed_action: dict[str, Any] | None  # {tool, args} dry-run preview shown at the gate

    # --- human-in-the-loop (task 8) ---
    approval: dict[str, Any] | None

    # --- outcome ---
    status: str  # AWAITING_APPROVAL | COMPLETED | REJECTED | FAILED
    result: dict[str, Any] | None

    # --- observability / caps ---
    trace: list[dict[str, Any]]
    step_count: int
