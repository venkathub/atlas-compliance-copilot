/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public base URL for backend calls. Empty = same-origin (reverse proxy routes /v1/*). */
  readonly VITE_API_BASE_URL?: string;
  /** Public Grafana base URL for the embedded cost dashboard (e.g. http://localhost:3001). */
  readonly VITE_GRAFANA_URL?: string;
  /** Grafana dashboard uid for the cost/latency panels (default atlas-cost-p3). */
  readonly VITE_GRAFANA_COST_DASHBOARD_UID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
