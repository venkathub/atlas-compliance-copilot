/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Vite + React + Tailwind v4 (CSS-first config, no tailwind.config.js).
// The dev server proxies the backend HTTP contracts to a single origin so the
// browser never needs CORS and never learns the backend topology — mirroring the
// production Caddy reverse proxy (D-P5-2). Targets are env-driven (never hardcoded):
//   VITE_DEV_GATEWAY_TARGET  -> /v1/*        (Gateway: auth, query, metrics)
//   VITE_DEV_AGENTS_TARGET   -> /v1/agent/*  (Agents: runs, resume, poll)
//   VITE_DEV_MCP_TARGET      -> /v1/audit    (mcp-tools: read-only audit)
// In the browser bundle, only the VITE_-prefixed, public base URL is exposed.
const gatewayTarget = process.env.VITE_DEV_GATEWAY_TARGET ?? "http://localhost:8080";
const agentsTarget = process.env.VITE_DEV_AGENTS_TARGET ?? "http://localhost:8083";
const mcpTarget = process.env.VITE_DEV_MCP_TARGET ?? "http://localhost:8082";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/v1/agent": { target: agentsTarget, changeOrigin: true },
      "/v1/audit": { target: mcpTarget, changeOrigin: true },
      "/v1": { target: gatewayTarget, changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.{test,spec}.{ts,tsx}", "src/**/*.{test,spec}.{ts,tsx}"],
    css: true,
  },
});
