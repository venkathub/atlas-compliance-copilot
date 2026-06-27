/**
 * apiClient — the single fetch wrapper for every backend call.
 *
 * Responsibilities (Task 0 skeleton; auth wiring lands in Task 1):
 *  - resolve the base URL from public env (VITE_API_BASE_URL); default "" so the
 *    app talks to its OWN origin and the reverse proxy (dev: Vite proxy; prod:
 *    Caddy) path-routes /v1/* — kills CORS, hides backend topology (D-P5-2).
 *  - attach `Authorization: Bearer <jwt>` when a token provider is registered.
 *  - surface a typed ApiError; signal 401 so the app can route to login.
 *
 * NO secret ever lives here or in the bundle: only the public base URL is read.
 * Clearance/authorization is ALWAYS re-enforced server-side — this client is a
 * convenience, not a security boundary.
 */

// Public, build-time-injected base URL. Empty string = same-origin (proxy routes).
const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

type TokenProvider = () => string | null;
type UnauthorizedHandler = () => void;

let tokenProvider: TokenProvider = () => null;
let onUnauthorized: UnauthorizedHandler = () => {};

/** Register how the client obtains the current in-memory JWT (set by AuthContext, Task 1). */
export function setTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
}

/** Register what happens on a 401 (e.g. route to login + clear token, Task 1). */
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  onUnauthorized = handler;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  /** Extra headers (e.g. Accept: text/event-stream for the optional SSE stretch). */
  headers?: Record<string, string>;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...options.headers,
  };

  const token = tokenProvider();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });

  if (res.status === 401) {
    onUnauthorized();
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => undefined);
    }
    throw new ApiError(res.status, `Request failed: ${res.status}`, body);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
