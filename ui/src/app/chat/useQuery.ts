import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "../../lib/apiClient.ts";
import type { QueryRequest, QueryResponse } from "../../lib/types.ts";

/**
 * useQuery — the RAG chat path (D-P5-1a). Posts to the FROZEN gateway `POST /v1/query`
 * and returns the complete envelope (answer + citations + routing/cache/cost). The
 * backend is synchronous (no SSE), so the "live" feel is a CLIENT-side progressive
 * reveal (useProgressiveReveal) over this completed payload — no backend change.
 */
export function useQueryMutation() {
  return useMutation<QueryResponse, Error, string>({
    mutationFn: (query: string) => {
      const body: QueryRequest = { query };
      return apiFetch<QueryResponse>("/v1/query", { method: "POST", body });
    },
  });
}
