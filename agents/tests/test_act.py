"""Unit tests for the act node: bounded connect-retries (no duplicate write) + auditRef."""

import httpx

from app.mcp_client import McpError
from app.nodes.act import make_act_sar_node

STATE = {
    "proposed_action": {
        "tool": "open_draft_sar",
        "args": {"account": "Northwind", "period": "2026-Q2", "rationale": "r", "citations": [1]},
    },
    "caller": "priya",
    "run_id": "run_1",
    "trace": [],
    "step_count": 0,
}


class FlakyMcp:
    """Raises ConnectError for the first `fail` calls, then succeeds."""

    def __init__(self, fail: int):
        self.fail = fail
        self.calls = 0

    def open_draft_sar(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail:
            raise httpx.ConnectError("connection refused")
        return {"draftRef": "SAR-1", "status": "DRAFT", "createdAt": "t", "auditRef": "audit_7"}


class ErroringMcp:
    def __init__(self, exc):
        self.exc = exc
        self.calls = 0

    def open_draft_sar(self, **kwargs):
        self.calls += 1
        raise self.exc


def test_retries_on_connect_error_then_succeeds_with_auditref():
    mcp = FlakyMcp(fail=1)
    node = make_act_sar_node(mcp, token_provider=lambda u: "tok", retries=2)
    out = node(dict(STATE))
    assert out["status"] == "COMPLETED"
    assert out["result"]["action"]["auditRef"] == "audit_7"
    assert mcp.calls == 2  # one retry after the connect error


def test_connect_errors_exhaust_retries_then_failed():
    mcp = FlakyMcp(fail=5)
    node = make_act_sar_node(mcp, token_provider=lambda u: "tok", retries=2)
    out = node(dict(STATE))
    assert out["status"] == "FAILED"
    assert mcp.calls == 3  # initial + 2 retries


def test_does_not_retry_after_a_response_error_no_duplicate_write():
    # An MCP error means the server responded → a write may have landed → must NOT retry.
    mcp = ErroringMcp(McpError("DENIED"))
    node = make_act_sar_node(mcp, token_provider=lambda u: "tok", retries=2)
    out = node(dict(STATE))
    assert out["status"] == "FAILED"
    assert mcp.calls == 1
