import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Answer } from "../src/app/chat/Answer.tsx";
import type { Citation } from "../src/lib/types.ts";

const CITATIONS: Citation[] = [
  {
    marker: 1,
    documentId: "uuid-1",
    docId: "l2-northwind-amlexc-q2",
    clearance: "compliance",
    snippet: "Exception over $10k.",
  },
];

describe("Answer (LLM05 render boundary)", () => {
  it("renders sanitized markdown", () => {
    const { container } = render(<Answer markdown="**3 open AML exceptions**" citations={[]} />);
    expect(container.querySelector("strong")).toHaveTextContent("3 open AML exceptions");
  });

  it("renders an XSS-laden answer INERT (no script element, no onerror)", () => {
    const malicious = "Result <script>window.__pwned=1</script> <img src=x onerror=alert(1)>";
    const { container } = render(<Answer markdown={malicious} citations={[]} />);
    expect(container.querySelector("script")).toBeNull();
    const img = container.querySelector("img");
    if (img) {
      expect(img.getAttribute("onerror")).toBeNull();
    }
    expect(container.innerHTML.toLowerCase()).not.toContain("onerror");
  });

  it("renders citation chips when citations are present", () => {
    render(<Answer markdown="See [1]." citations={CITATIONS} />);
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "[1]" })).toBeInTheDocument();
  });
});
