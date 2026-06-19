"""Gateway-path client for the eval harness (P3 task 10, R2).

Talks to the **Gateway** (`POST /v1/auth/token` → `POST /v1/query`) instead of rag-engine directly,
so the reused RAGAS gate proves quality holds *through* auth + routing + cache + redaction. It has
the same ``query(question, clearance, ...)`` surface as
:class:`atlas_evals.client.AtlasRagClient`, so it drops into
:class:`atlas_evals.client.CassettingClient` unchanged — in REPLAY the cassettes (keyed by
question/clearance/fingerprint, not client path) are served identically, so the CI gate is offline;
the live calibration lane re-records through the real Gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from atlas_evals.client import Transport, _urllib_transport

# The simulated-IdP dev users (gateway/dev/clearance-users.json) keyed by their clearance.
_USER_BY_CLEARANCE = {
    "public": "guest-public",
    "analyst": "analyst-bob",
    "compliance": "priya",
    "restricted": "bsa-admin",
}


@dataclass
class GatewayRagClient:
    """Client for the Gateway-fronted query path (mints a JWT, then calls ``/v1/query``)."""

    base_url: str
    timeout_s: float = 60.0
    transport: Transport | None = None
    _tokens: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def _transport(self) -> Transport:
        return self.transport or _urllib_transport(self.timeout_s)

    def _token(self, clearance: str) -> str:
        if clearance not in self._tokens:
            user = _USER_BY_CLEARANCE.get(clearance)
            if user is None:
                raise ValueError(f"no simulated-IdP dev user for clearance '{clearance}'")
            import json

            body = json.dumps({"user": user}).encode("utf-8")
            url = self.base_url.rstrip("/") + "/v1/auth/token"
            resp = self._transport()("POST", url, {"Content-Type": "application/json"}, body)
            self._tokens[clearance] = resp["token"]
        return self._tokens[clearance]

    def query(
        self,
        question: str,
        clearance: str,
        *,
        user: str | None = None,  # ignored: the IdP derives the user from clearance
        top_k: int | None = None,
        include_contexts: bool = True,
    ) -> dict:
        """Mint a clearance token (cached) and POST a query through the Gateway."""
        import json

        token = self._token(clearance)
        payload: dict = {"query": question, "includeContexts": include_contexts}
        if top_k is not None:
            payload["topK"] = top_k
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        body = json.dumps(payload).encode("utf-8")
        url = self.base_url.rstrip("/") + "/v1/query"
        return self._transport()("POST", url, headers, body)
