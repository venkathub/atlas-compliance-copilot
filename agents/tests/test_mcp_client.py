"""MCP Streamable-HTTP client tests (httpx MockTransport — no live server)."""

import json

import httpx
import pytest

from app.mcp_client import McpClient, McpError


def _make_client(handler):
    return McpClient("http://mcp/mcp", transport=httpx.MockTransport(handler))


def _ok_handler(record):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        record.append((body["method"], dict(request.headers)))
        if body["method"] == "initialize":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"serverInfo": {"name": "atlas-mcp-tools"}},
                },
                headers={"Mcp-Session-Id": "sess-1"},
            )
        # tools/call
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "structuredContent": {
                        "draftRef": "SAR-2026-000001",
                        "status": "DRAFT",
                        "createdAt": "2026-06-21T10:00:00Z",
                    },
                    "isError": False,
                },
            },
        )

    return handler


def test_open_draft_sar_handshake_and_structured_result():
    record = []
    client = _make_client(_ok_handler(record))
    result = client.open_draft_sar(
        bearer="aud-tok",
        run_id="run_1",
        account="Northwind",
        period="2026-Q2",
        rationale="exceeds",
        citations=[1, 2],
    )
    assert result["draftRef"] == "SAR-2026-000001"
    methods = [m for m, _ in record]
    assert methods == ["initialize", "tools/call"]
    # The aud-scoped Bearer + the session id are sent on the tool call.
    _, call_headers = record[1]
    assert call_headers["authorization"] == "Bearer aud-tok"
    assert call_headers["mcp-session-id"] == "sess-1"


def test_tool_error_raises_mcp_error():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}},
                                  headers={"Mcp-Session-Id": "s"})
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"isError": True, "content": [{"type": "text", "text": "DENIED"}]},
            },
        )

    client = _make_client(handler)
    with pytest.raises(McpError, match="DENIED"):
        client.open_draft_sar("t", "run_1", "Northwind", "2026-Q2", "r", [1])


def test_missing_session_id_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        # No Mcp-Session-Id header on the initialize response.
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})

    client = _make_client(handler)
    with pytest.raises(McpError, match="session"):
        client.open_draft_sar("t", "run_1", "Northwind", "2026-Q2", "r", [1])
