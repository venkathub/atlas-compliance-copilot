"""MCP Streamable-HTTP client for the governed `open_draft_sar` action (P4_SPEC §2.4).

A minimal synchronous JSON-RPC client (matching the deterministic sync graph): it performs the MCP
handshake (`initialize` → `Mcp-Session-Id`) and a `tools/call`, attaching an aud-scoped (RFC 8707)
Bearer token the MCP server validates as an OAuth 2.1 resource server. Responses may be plain JSON
or SSE `data:` frames — both are handled. (The official async MCP SDK is an alternative; raw httpx
keeps the call sync + dependency-light.)
"""

from __future__ import annotations

import json
from typing import Any

import httpx

_PROTOCOL_VERSION = "2025-11-25"


class McpError(RuntimeError):
    """Raised when the MCP server returns a JSON-RPC error or an isError tool result."""


class McpClient:
    def __init__(
        self, base_url: str, timeout: float = 30.0, transport: httpx.BaseTransport | None = None
    ):
        self._url = base_url
        self._timeout = timeout
        self._transport = transport

    def open_draft_sar(
        self,
        bearer: str,
        run_id: str,
        account: str,
        period: str,
        rationale: str,
        citations: list[int],
    ) -> dict[str, Any]:
        """Initialize a session, then call open_draft_sar; return its structured output."""
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            session_id = self._initialize(client, bearer)
            result = self._rpc(
                client,
                bearer,
                session_id,
                method="tools/call",
                params={
                    "name": "open_draft_sar",
                    "arguments": {
                        "account": account,
                        "period": period,
                        "rationale": rationale,
                        "citations": citations,
                        "runId": run_id,
                    },
                },
            )
            if result.get("isError"):
                raise McpError(_first_text(result) or "open_draft_sar returned an error")
            structured = result.get("structuredContent")
            if structured:
                return structured
            text = _first_text(result)
            return json.loads(text) if text else {}

    def _initialize(self, client: httpx.Client, bearer: str) -> str:
        headers = self._headers(bearer, None)
        body = self._envelope(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "atlas-agents", "version": "0.1.0"},
            },
        )
        resp = client.post(self._url, json=body, headers=headers)
        resp.raise_for_status()
        session_id = resp.headers.get("Mcp-Session-Id")
        if not session_id:
            raise McpError("MCP server did not issue a session id on initialize")
        return session_id

    def _rpc(self, client, bearer, session_id, method, params) -> dict[str, Any]:
        resp = client.post(
            self._url,
            json=self._envelope(method, params),
            headers=self._headers(bearer, session_id),
        )
        resp.raise_for_status()
        message = _parse_jsonrpc(resp.text)
        if "error" in message:
            raise McpError(str(message["error"]))
        return message.get("result", {})

    @staticmethod
    def _headers(bearer: str, session_id: str | None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {bearer}",
        }
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        return headers

    @staticmethod
    def _envelope(method: str, params: dict) -> dict:
        return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


def _parse_jsonrpc(body: str) -> dict[str, Any]:
    """Parse a JSON-RPC message from a plain-JSON or SSE (`data:` framed) response body."""
    text = body
    if "data:" in text:
        frames = [
            line[len("data:") :].strip()
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        text = frames[-1] if frames else text
    return json.loads(text)


def _first_text(result: dict[str, Any]) -> str | None:
    for item in result.get("content", []) or []:
        if item.get("type") == "text":
            return item.get("text")
    return None
