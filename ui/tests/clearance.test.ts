import { describe, it, expect } from "vitest";
import { atLeast, clearanceLabel, CLEARANCE_RANK } from "../src/app/auth/clearance.ts";

describe("clearance ordering (mirrors the frozen gateway enum)", () => {
  it("ranks public < analyst < compliance < restricted", () => {
    expect(CLEARANCE_RANK.public).toBeLessThan(CLEARANCE_RANK.analyst);
    expect(CLEARANCE_RANK.analyst).toBeLessThan(CLEARANCE_RANK.compliance);
    expect(CLEARANCE_RANK.compliance).toBeLessThan(CLEARANCE_RANK.restricted);
  });

  it("atLeast is inclusive and respects the ordering", () => {
    expect(atLeast("compliance", "compliance")).toBe(true);
    expect(atLeast("restricted", "compliance")).toBe(true);
    expect(atLeast("analyst", "compliance")).toBe(false);
    expect(atLeast("public", "analyst")).toBe(false);
  });

  it("labels are capitalized for display", () => {
    expect(clearanceLabel("compliance")).toBe("Compliance");
    expect(clearanceLabel("restricted")).toBe("Restricted");
  });
});
