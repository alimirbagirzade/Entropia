import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./apiClient";
import { parseMetricsSummary, type MetricsSummary } from "./metrics";
import type { Me, Meta, ReadyResponse } from "./types";

// Forward-only opaque keyset cursors (server contract): Prev replays the
// cursor stack, the client never re-orders or fabricates a page. Drives the
// shared <Pager> component.
export function useCursorStack() {
  const [stack, setStack] = useState<string[]>([]);
  const cursor = stack.length > 0 ? stack[stack.length - 1] : null;
  return {
    cursor,
    canPrev: stack.length > 0,
    next: (nextCursor: string) => setStack((prev) => [...prev, nextCursor]),
    prev: () => setStack((prev) => prev.slice(0, -1)),
    reset: () => setStack([]),
  };
}

export function useMeta() {
  return useQuery({
    queryKey: ["meta"],
    queryFn: () => api.get<Meta>("/meta"),
    staleTime: 5 * 60_000,
  });
}

export function useReadiness() {
  return useQuery({
    queryKey: ["health", "ready"],
    queryFn: () => api.get<ReadyResponse>("/health/ready"),
    refetchInterval: 15_000,
  });
}


// R2-10 (GAP madde 14): app-shell "API reachable" probe. /health/live is the
// cheapest endpoint (no dependency checks, auth-exempt). Modest 30s interval and
// no automatic retry — a dead backend must not generate a request storm; the
// shell's Retry action refetches on demand.
export function useApiHealth() {
  return useQuery({
    queryKey: ["health", "live"],
    queryFn: () => api.get<{ status: string }>("/health/live"),
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<Me>("/me"),
    staleTime: 60_000,
  });
}

// Operational metrics (Stage 8b): GET /v1/metrics returns Prometheus text, which we
// parse into a derived summary. Polled on an interval so the dashboard stays live;
// the ["metrics"] key is also caught by the SSE `resource.changed` full refresh.
export function useMetrics() {
  return useQuery<MetricsSummary>({
    queryKey: ["metrics"],
    queryFn: async () => parseMetricsSummary(await api.getText("/metrics")),
    refetchInterval: 5_000,
  });
}
