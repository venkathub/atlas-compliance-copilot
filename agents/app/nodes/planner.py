"""Planner node — lays out the (fixed) plan for the forcing query (ADR-0041).

The plan is deterministic graph structure, not LLM whim: retrieve grounded context,
deterministically assess the breach condition, and — only on a breach and only after human
approval — open a draft SAR.
"""

from __future__ import annotations

from typing import Any

PLAN = ["retrieve", "assess", "conditional-sar"]


def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    trace = state.get("trace", []) + [{"node": "planner", "plan": PLAN}]
    return {"plan": PLAN, "trace": trace, "step_count": state.get("step_count", 0) + 1}
