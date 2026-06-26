import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Citation } from "../src/app/chat/Citation.tsx";
import type { Citation as CitationType } from "../src/lib/types.ts";

const CITATION: CitationType = {
  n: 1,
  documentId: "l2-northwind-amlexc-q2",
  clearance: "compliance",
  snippet: "Wire of $12,400 flagged.",
};

describe("Citation chip + popover", () => {
  it("hides the popover until the chip is clicked", () => {
    render(<Citation citation={CITATION} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("reveals documentId, clearance, and snippet on click", async () => {
    const user = userEvent.setup();
    render(<Citation citation={CITATION} />);
    await user.click(screen.getByRole("button", { name: "[1]" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("l2-northwind-amlexc-q2");
    expect(dialog).toHaveTextContent("Compliance");
    expect(dialog).toHaveTextContent("Wire of $12,400 flagged.");
  });

  it("renders an XSS-laden snippet inert (as text, no script)", async () => {
    const user = userEvent.setup();
    const evil: CitationType = {
      ...CITATION,
      snippet: "<script>alert('x')</script><img src=x onerror=alert(1)>",
    };
    const { container } = render(<Citation citation={evil} />);
    await user.click(screen.getByRole("button", { name: "[1]" }));

    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.innerHTML.toLowerCase()).not.toContain("onerror");
  });
});
