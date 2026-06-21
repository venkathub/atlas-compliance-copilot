"""Prometheus metrics for the agent (P4_SPEC §2.4 — the Grafana agent panel).

Exposes run counts, tool-call rate, approval latency, and failures. Metrics are recorded by the
runner (which sees terminal transitions) so the graph nodes stay pure. Exposed at /metrics.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

RUNS_STARTED = Counter("atlas_agent_runs_started_total", "Agent runs started")

RUNS_TOTAL = Counter(
    "atlas_agent_runs_total", "Agent runs by terminal status", labelnames=("status",)
)

AWAITING_APPROVAL = Counter(
    "atlas_agent_awaiting_approval_total", "Runs that paused at the human-approval gate"
)

TOOL_CALLS = Counter(
    "atlas_agent_tool_calls_total", "Governed tool calls by outcome", labelnames=("outcome",)
)

FAILURES = Counter("atlas_agent_failures_total", "Agent runs that ended in FAILED")

APPROVAL_LATENCY = Histogram(
    "atlas_agent_approval_latency_seconds",
    "Seconds between run start and the human approval decision",
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800),
)
