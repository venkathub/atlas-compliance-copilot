import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "../src/App.tsx";

// Task 0 skeleton smoke test: proves the toolchain (Vite + React + TS + Tailwind +
// Vitest/RTL) renders the app shell. Real auth/chat/admin tests arrive in later tasks.
describe("App shell", () => {
  it("renders the Atlas heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /atlas/i })).toBeInTheDocument();
  });
});
