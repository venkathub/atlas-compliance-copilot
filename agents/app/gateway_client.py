"""HTTP client for the P3 Gateway query path (the agent's only retrieval route).

The agent calls the Gateway `POST /v1/query` with the *caller's* Bearer JWT — never rag-engine
directly, never a clearance header — so RBAC, cost-routing, semantic cache, and PII redaction are
all inherited (ADR-0034 / ADR-0045). It also mints aud-scoped (RFC 8707) tokens for the MCP hop via
`POST /v1/auth/resource-token` (ADR-0046).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.logging_config import REQUEST_ID_HEADER, current_request_id


def _correlation_headers() -> dict[str, str]:
    """Forward the current request's correlation id downstream so traces/logs stitch (P6 Task 3)."""
    request_id = current_request_id()
    return {REQUEST_ID_HEADER: request_id} if request_id else {}


class GatewayClient:
    """Minimal Gateway client (synchronous; the WebMVC graph runs on the request thread)."""

    def __init__(
        self, base_url: str, timeout: float = 30.0, transport: httpx.BaseTransport | None = None
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def query(self, query: str, top_k: int, bearer: str) -> dict[str, Any]:
        """POST a query through the Gateway with the caller's Bearer; return the JSON body."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer}",
            **_correlation_headers(),
        }
        body = {"query": query, "topK": top_k, "includeContexts": True}
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            resp = client.post(f"{self._base_url}/v1/query", json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def resource_token(self, user: str) -> str:
        """Mint an aud-scoped (RFC 8707) resource token for the MCP hop (ADR-0046)."""
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            resp = client.post(
                f"{self._base_url}/v1/auth/resource-token",
                json={"user": user},
                headers={"Content-Type": "application/json", **_correlation_headers()},
            )
            resp.raise_for_status()
            return resp.json()["token"]
