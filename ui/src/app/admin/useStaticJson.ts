import { useQuery } from "@tanstack/react-query";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

/**
 * Fetch a committed static JSON asset (served same-origin, e.g. the eval/cost summary
 * snapshots). Read-only; the UI never recomputes these — it renders the committed
 * gate artifact (P5 D-P5-3 / ADR-0053).
 */
export function useStaticJson<T>(path: string, key: string) {
  return useQuery<T>({
    queryKey: [key],
    queryFn: async () => {
      const res = await fetch(`${BASE}${path}`);
      if (!res.ok) {
        throw new Error(`${path} unavailable (${res.status})`);
      }
      return (await res.json()) as T;
    },
    retry: false,
  });
}
