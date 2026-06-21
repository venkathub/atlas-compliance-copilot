"""HTTP client for the P3 Gateway query path (the agent's only retrieval route).

The agent calls the Gateway `POST /v1/query` with the *caller's* Bearer JWT — never rag-engine
directly, never a clearance header — so RBAC, cost-routing, semantic cache, and PII redaction are
all inherited (ADR-0034 / ADR-0045).
"""

from __future__ import annotations

from typing import Any

import httpx


class GatewayClient:
    """Minimal Gateway client (synchronous; the WebMVC graph runs on the request thread)."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def query(self, query: str, top_k: int, bearer: str) -> dict[str, Any]:
        """POST a query through the Gateway with the caller's Bearer; return the JSON body."""
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {bearer}"}
        body = {"query": query, "topK": top_k, "includeContexts": True}
        resp = httpx.post(
            f"{self._base_url}/v1/query", json=body, headers=headers, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()
