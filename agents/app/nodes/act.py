"""Act node — the governed write, reachable ONLY after the approval gate (ADR-0044/0046).

Mints an aud-scoped (RFC 8707) resource token for the caller via the Gateway, then calls the MCP
`open_draft_sar` tool with the proposed args + the originating run id. Structurally this node has a
single predecessor (the `approve` interrupt gate), so no write happens without a recorded human
approval. An MCP error (e.g., the per-call clearance re-check denying a sub-compliance caller) ends
the run in FAILED with no draft.

Bounded retries (ASI10 / §2.5) cover only `httpx.ConnectError` — i.e. the connection was never
established, so the server cannot have processed a write — which makes the retry safe against
duplicate SARs. Any failure *after* a connection (timeout/read/MCP error) is NOT retried, since the
write may have landed; the run ends FAILED instead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx


def make_act_sar_node(
    mcp_client: Any, token_provider: Callable[[str], str], retries: int = 2
) -> Callable[[dict], dict]:
    """Build the act node bound to an MCP client + a resource-token provider (injected)."""

    def _failed(state: dict[str, Any], trace: list, error: str) -> dict[str, Any]:
        return {
            "status": "FAILED",
            "result": {"error": error},
            "trace": trace + [{"node": "act_sar", "error": error}],
            "step_count": state.get("step_count", 0) + 1,
        }

    def act_sar_node(state: dict[str, Any]) -> dict[str, Any]:
        proposed = state["proposed_action"]
        args = proposed["args"]
        trace = state.get("trace", []) + [{"node": "act_sar"}]
        last_error: str | None = None

        for _attempt in range(max(1, retries + 1)):
            try:
                token = token_provider(state["caller"])
                result = mcp_client.open_draft_sar(
                    bearer=token,
                    run_id=state["run_id"],
                    account=args["account"],
                    period=args["period"],
                    rationale=args["rationale"],
                    citations=args["citations"],
                )
                return {
                    "status": "COMPLETED",
                    "result": {
                        "action": {
                            "tool": "open_draft_sar",
                            "draftRef": result.get("draftRef"),
                            "status": result.get("status", "DRAFT"),
                            "auditRef": result.get("auditRef"),
                        }
                    },
                    "trace": trace,
                    "step_count": state.get("step_count", 0) + 1,
                }
            except httpx.ConnectError as e:
                # Connection never established → no server-side write → safe to retry.
                last_error = f"connect error: {e}"
                continue
            except Exception as e:  # noqa: BLE001 - response/other failure → FAILED, do not retry
                return _failed(state, trace, str(e))

        return _failed(state, trace, last_error or "tool call failed after retries")

    return act_sar_node
