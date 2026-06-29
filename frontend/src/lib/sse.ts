// Central SSE client (Module 20 §10). SSE is a refresh signal, not state.
// On each domain event we invalidate the relevant query keys so the UI refetches
// authoritative state from the server. Stage 0 wires the connection + heartbeat.

import type { QueryClient } from "@tanstack/react-query";
import { BASE_URL } from "./apiClient";

export type SseStatus = "connecting" | "open" | "closed";

export function connectEvents(
  queryClient: QueryClient,
  onStatus?: (status: SseStatus) => void,
): () => void {
  onStatus?.("connecting");
  const source = new EventSource(`${BASE_URL}/events`);

  source.onopen = () => onStatus?.("open");
  source.onerror = () => onStatus?.("closed");

  // Heartbeat keeps the connection observable; no cache effect.
  source.addEventListener("heartbeat", () => {});

  // `queryClient` is reserved for Stage 1+: domain events map to query
  // invalidations here, e.g.
  //   source.addEventListener("resource.changed", () => queryClient.invalidateQueries());
  void queryClient;

  return () => {
    source.close();
    onStatus?.("closed");
  };
}
