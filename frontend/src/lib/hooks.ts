import { useQuery } from "@tanstack/react-query";
import { api } from "./apiClient";
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
