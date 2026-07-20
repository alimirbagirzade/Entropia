import { ApiError } from "./apiClient";
import { useApprovedBundle, type ApprovedBundle } from "./marketData";

// R2-06 (GAP item 8) — the server-truth Approved Market Data dependency
// projection Research Data derives its workflow lock from. Fail-closed: only a
// confirmed `ready` verdict unlocks anything; loading/stale re-checks, a 404
// (no active approved revision), a 403 (no access) and an unknown error all
// keep the lock. Server envelopes are surfaced verbatim.

export type MarketDependencyStatus =
  | { kind: "none" }
  | { kind: "checking" }
  | { kind: "ready"; bundle: ApprovedBundle }
  | { kind: "denied"; message: string }
  | { kind: "blocked"; message: string };

export function probeErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  return error instanceof Error ? error.message : "Dependency check failed.";
}

// Resolve the selected root against the server: which exact APPROVED revision
// would a Research Data version pin right now? `checking` also covers the stale
// window (a refetch after invalidation) — the lock re-engages until the server
// re-confirms, so a deprecated/revoked link never stays visually "ready".
export function useMarketDependency(entityId: string | null): MarketDependencyStatus {
  const probe = useApprovedBundle(entityId, entityId !== null);
  if (entityId === null) return { kind: "none" };
  if (probe.isLoading || probe.isFetching) return { kind: "checking" };
  if (probe.isError) {
    const message = probeErrorMessage(probe.error);
    if (probe.error instanceof ApiError && probe.error.status === 403) {
      return { kind: "denied", message };
    }
    return { kind: "blocked", message };
  }
  if (probe.data !== undefined) return { kind: "ready", bundle: probe.data };
  return { kind: "checking" };
}
