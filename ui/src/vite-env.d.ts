/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public base URL for backend calls. Empty = same-origin (reverse proxy routes /v1/*). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
