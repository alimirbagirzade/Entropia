import { useQuery } from "@tanstack/react-query";
import { api } from "./apiClient";
import type { Meta, ReadyResponse } from "./types";

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
