import { useAuth } from "./AuthContext.tsx";
import { atLeast } from "./clearance.ts";
import type { Clearance } from "../../lib/types.ts";

/**
 * useClearance — decode the current session's clearance for UI gating.
 *
 * REMINDER: this gates which tabs/controls render (UX only). It is NOT a security
 * boundary — every backend re-enforces clearance (RBAC at retrieval, OAuth re-check
 * at the tool, refuse-`<compliance` on /v1/audit). A tampered client that forces an
 * admin tab still cannot read protected data.
 */
export function useClearance(): {
  clearance: Clearance | null;
  hasAtLeast: (required: Clearance) => boolean;
} {
  const { session } = useAuth();
  const clearance = session?.clearance ?? null;
  return {
    clearance,
    hasAtLeast: (required: Clearance) => (clearance ? atLeast(clearance, required) : false),
  };
}
