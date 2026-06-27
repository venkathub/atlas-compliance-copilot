import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../../lib/apiClient.ts";
import type { AuditPage } from "../../lib/types.ts";

/**
 * useAuditLog — paginated read of the compliance-gated `GET /v1/audit` (the mcp-tools
 * read-only endpoint). The apiClient attaches the Bearer token; a 401 routes to login.
 */
export function useAuditLog(page: number, size = 25) {
  return useQuery<AuditPage>({
    queryKey: ["audit", page, size],
    queryFn: () => apiFetch<AuditPage>(`/v1/audit?page=${page}&size=${size}`),
    retry: false,
  });
}
