"""Thin HTTP client for the rag-engine `POST /v1/query` (the eval harness's view of the SUT).

The harness talks to rag-engine over HTTP exactly as a real evaluator would — never importing
Java internals (the clean seam, P2 §2.1). The transport is injectable so request shaping is
unit-tested offline and so Task 6 can drop in cassette record/replay without touching callers.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from atlas_evals.cassettes import CassetteStore, cassette_key

# transport: (method, url, headers, body_bytes|None) -> parsed JSON dict
Transport = Callable[[str, str, dict, bytes | None], dict]


def _urllib_transport(timeout_s: float) -> Transport:
    def _call(method: str, url: str, headers: dict, body: bytes | None) -> dict:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw)

    return _call


@dataclass
class AtlasRagClient:
    """Client for `POST /v1/query`. Sends the P1 clearance-shim headers (ADR-0016)."""

    base_url: str
    header_clearance: str = "X-Atlas-Clearance"
    header_user: str = "X-Atlas-User"
    timeout_s: float = 60.0
    transport: Transport | None = None

    def query(
        self,
        question: str,
        clearance: str,
        *,
        user: str | None = None,
        top_k: int | None = None,
        include_contexts: bool = True,
    ) -> dict:
        """POST a query at the given clearance; returns the parsed `/v1/query` response."""
        payload: dict = {"query": question, "includeContexts": include_contexts}
        if top_k is not None:
            payload["topK"] = top_k
        headers = {"Content-Type": "application/json", self.header_clearance: clearance}
        if user:
            headers[self.header_user] = user
        body = json.dumps(payload).encode("utf-8")
        url = self.base_url.rstrip("/") + "/v1/query"
        transport = self.transport or _urllib_transport(self.timeout_s)
        return transport("POST", url, headers, body)


@dataclass
class CassettingClient:
    """Wraps ``AtlasRagClient`` so ``/v1/query`` responses are recorded/replayed.

    The cassette key includes a ``fingerprint`` (corpus + RAG/embed model tags) so a model or
    corpus change busts the cassette (a miss in REPLAY then fails loudly rather than scoring stale
    answers). This is the RAG-side half of the offline gate (judge side is cassetted separately).
    """

    client: AtlasRagClient
    store: CassetteStore
    fingerprint: str = ""

    def query(
        self,
        question: str,
        clearance: str,
        *,
        user: str | None = None,
        top_k: int | None = None,
        include_contexts: bool = True,
    ) -> dict:
        key = cassette_key(
            "v1/query", self.fingerprint, question, clearance, top_k, include_contexts
        )
        return self.store.record_or_replay(
            key,
            lambda: self.client.query(
                question, clearance, user=user, top_k=top_k, include_contexts=include_contexts
            ),
            meta={"question": question, "clearance": clearance},
        )
