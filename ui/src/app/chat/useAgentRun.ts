import { useCallback, useRef, useState } from "react";
import { apiFetch, ApiError } from "../../lib/apiClient.ts";
import type { AgentRun, ResumeRequest, RunRequest } from "../../lib/types.ts";

/** Map an agent-run failure to a calm, user-facing message. */
function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 404:
        return "That run was not found.";
      case 422:
        return "Invalid run request (check account and period, e.g. 2026-Q2).";
      case 402:
        return "Daily budget exceeded — the cost cap was hit. Try again later.";
      case 503:
        return "The agent service is temporarily unavailable. Please retry shortly.";
      default:
        return `Agent request failed (${err.status}).`;
    }
  }
  return "Network error — is the agent service running?";
}

const POLL_MS = 600;
const MAX_POLLS = 30;

/**
 * useAgentRun — drives one HITL agent run against the FROZEN P4 API.
 *
 *   start(req)          → POST /v1/agent/runs        (Bearer; → AWAITING_APPROVAL | …)
 *   resume(approved,..) → POST …/{id}/resume         (forwards the HUMAN decision only)
 *   (internal) poll     → GET  …/{id}                (animates the trace while RUNNING)
 *
 * The UI is the *trigger*, never the *authority*: the act_sar write is server-side
 * unreachable until resume({approved:true}). This hook NEVER constructs a write call;
 * it only forwards the human's Approve/Reject to the agent (LLM06 / ADR HITL).
 */
export function useAgentRun() {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const cancelled = useRef(false);

  const pollUntilSettled = useCallback(async (current: AgentRun) => {
    let latest = current;
    for (let i = 0; i < MAX_POLLS && latest.status === "RUNNING" && !cancelled.current; i++) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      if (cancelled.current) return;
      latest = await apiFetch<AgentRun>(`/v1/agent/runs/${latest.runId}`);
      setRun(latest);
    }
  }, []);

  const start = useCallback(
    async (req: RunRequest) => {
      cancelled.current = false;
      setError(null);
      setBusy(true);
      setRun(null);
      try {
        const r = await apiFetch<AgentRun>("/v1/agent/runs", { method: "POST", body: req });
        setRun(r);
        await pollUntilSettled(r);
      } catch (err) {
        setError(friendlyError(err));
      } finally {
        setBusy(false);
      }
    },
    [pollUntilSettled],
  );

  const resume = useCallback(
    async (approved: boolean, note?: string) => {
      if (!run) return;
      setError(null);
      setBusy(true);
      try {
        const body: ResumeRequest = { approved, ...(note ? { note } : {}) };
        const r = await apiFetch<AgentRun>(`/v1/agent/runs/${run.runId}/resume`, {
          method: "POST",
          body,
        });
        setRun(r);
        await pollUntilSettled(r);
      } catch (err) {
        setError(friendlyError(err));
      } finally {
        setBusy(false);
      }
    },
    [run, pollUntilSettled],
  );

  return { run, error, busy, start, resume };
}
