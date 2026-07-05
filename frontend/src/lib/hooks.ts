import { useQuery } from "@tanstack/react-query";
import { api } from "./apiClient";
import { parseMetricsSummary, type MetricsSummary } from "./metrics";
import type { Me, Meta, ReadyResponse } from "./types";

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
