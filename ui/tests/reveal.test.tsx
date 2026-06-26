import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useProgressiveReveal } from "../src/app/chat/useProgressiveReveal.ts";

describe("useProgressiveReveal", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: true, // prefers-reduced-motion
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it("reveals the full text immediately when reduced motion is preferred", () => {
    const full = "There are 3 open AML exceptions.";
    const { result } = renderHook(() => useProgressiveReveal(full));
    expect(result.current.text).toBe(full);
    expect(result.current.done).toBe(true);
  });
});
