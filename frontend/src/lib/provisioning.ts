// First-Admin provisioning onboarding signal (post-V1 TIER 2). The backend
// GET /auth/bootstrap-status is anonymous, read-only and booleans-only (no PII):
// the first Admin is not yet authenticated, so the Provisioning page must be
// readable before any session exists. There is no dedicated SSE event for
// provisioning state — the ["auth"] key is swept by the `resource.changed`
// full refresh (lib/sse.ts EVENT_QUERY_KEYS) and refetched on mount/focus.

import { useQuery } from "@tanstack/react-query";

import { api } from "./apiClient";

export interface BootstrapStatus {
  // Operator opt-in: ENTROPIA_BOOTSTRAP_ADMIN_EMAIL is set to a non-empty value.
  bootstrap_configured: boolean;
  // At least one active Admin exists -> the bootstrap window is CLOSED.
  active_admin_exists: boolean;
}

const BOOTSTRAP_STATUS_STALE_MS = 30_000;

export function useBootstrapStatus() {
  return useQuery({
    queryKey: ["auth", "bootstrap-status"],
    queryFn: () => api.get<BootstrapStatus>("/auth/bootstrap-status"),
    staleTime: BOOTSTRAP_STATUS_STALE_MS,
  });
}
