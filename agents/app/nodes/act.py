"""Act node — the governed write, reachable ONLY after the approval gate (ADR-0044/0046).

Mints an aud-scoped (RFC 8707) resource token for the caller via the Gateway, then calls the MCP
`open_draft_sar` tool with the proposed args + the originating run id. Structurally this node has a
single predecessor (the `approve` interrupt gate), so no write happens without a recorded human
approval. An MCP error (e.g., the per-call clearance re-check denying a sub-compliance caller) ends
the run in FAILED with no draft.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def make_act_sar_node(
    mcp_client: Any, token_provider: Callable[[str], str]
) -> Callable[[dict], dict]:
    """Build the act node bound to an MCP client + a resource-token provider (injected)."""

    def act_sar_node(state: dict[str, Any]) -> dict[str, Any]:
        proposed = state["proposed_action"]
        args = proposed["args"]
        trace = state.get("trace", []) + [{"node": "act_sar"}]
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
                    }
                },
                "trace": trace,
                "step_count": state.get("step_count", 0) + 1,
            }
        except Exception as e:  # noqa: BLE001 - any tool/transport failure → FAILED, no write
            return {
                "status": "FAILED",
                "result": {"error": str(e)},
                "trace": trace + [{"node": "act_sar", "error": str(e)}],
                "step_count": state.get("step_count", 0) + 1,
            }

    return act_sar_node
