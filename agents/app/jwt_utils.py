"""Tiny JWT helpers. The agent only needs to *read* the subject from the caller's token to request
a resource-scoped token for the MCP hop — it does not verify the signature (the Gateway already
verified the token at retrieval, and the sim-IdP resource-token endpoint re-looks-up clearance).
"""

from __future__ import annotations

import base64
import json


def jwt_sub(token: str) -> str:
    """Return the `sub` claim from a JWT payload (no signature verification)."""
    try:
        payload_b64 = token.split(".")[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        sub = payload.get("sub")
    except (IndexError, ValueError, TypeError) as e:
        raise ValueError("could not read subject from bearer token") from e
    if not sub:
        raise ValueError("bearer token has no subject")
    return sub
