import type { Clearance } from "../../lib/types.ts";

/**
 * Clearance ordering — mirrors the FROZEN gateway `Clearance` enum
 * (public < analyst < compliance < restricted). Used ONLY for UI gating
 * (which tabs/buttons render). This is UX convenience, NOT a security boundary:
 * every backend independently re-enforces clearance, so a tampered client cannot
 * reach data above its level.
 */
export const CLEARANCE_RANK: Record<Clearance, number> = {
  public: 0,
  analyst: 1,
  compliance: 2,
  restricted: 3,
};

/** True when `actual` clearance is at least `required` (>= in the ordering). */
export function atLeast(actual: Clearance, required: Clearance): boolean {
  return CLEARANCE_RANK[actual] >= CLEARANCE_RANK[required];
}

/** Human-friendly label for a clearance level (UI display). */
export function clearanceLabel(clearance: Clearance): string {
  return clearance.charAt(0).toUpperCase() + clearance.slice(1);
}
