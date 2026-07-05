// Central SSE client (Module 20 §10). SSE is a refresh signal, NOT state: on each
// domain event we invalidate the matching query keys so the UI refetches
// authoritative state from the server. Delivery is loss-tolerant (INF-11) — a
// missed event self-heals on the next refetch, and a reconnect triggers a full
// refresh so no view is left stale across a connection gap.

import type { QueryClient, QueryKey } from "@tanstack/react-query";
import { BASE_URL } from "./apiClient";

export type SseStatus = "connecting" | "open" | "closed";

// The backend SSE taxonomy (apps/api/sse.py::sse_event_name). Consumed, not owned;
// this union must stay in lockstep with that server-side projection.
export type SseEventName =
  | "backtest.run.updated"
  | "job.updated"
  | "agent.task.updated"
  | "audit.event.created"
  | "resource.changed";

// Each domain event marks a set of query-key prefixes stale. react-query matches
// by prefix, so ["backtests"] also invalidates ["backtests", runId, …] once the
// RUN / History / Metrics pages bind those keys. An empty list means "no single
// key fits": the unspecialized `resource.changed` catch-all triggers a full
// refresh instead. Invalidating a key no live query uses yet is a harmless no-op,
// so this mapping is the forward contract the Stage 5/6 pages bind to as they land.
export const EVENT_QUERY_KEYS: Record<SseEventName, readonly QueryKey[]> = {
  "backtest.run.updated": [["backtests"]],
  "job.updated": [["jobs"]],
  "agent.task.updated": [["agent-tasks"]],
  "audit.event.created": [["audit"]],
  "resource.changed": [],
};

export const SSE_EVENT_NAMES = Object.keys(EVENT_QUERY_KEYS) as SseEventName[];

function invalidateForEvent(queryClient: QueryClient, name: SseEventName): void {
  const keys = EVENT_QUERY_KEYS[name];
  if (keys.length === 0) {
    // Catch-all bucket (strategies, packages, market/research data, portfolio …):
    // no single key fits, so refetch every mounted query.
    void queryClient.invalidateQueries();
    return;
  }
  for (const queryKey of keys) {
    void queryClient.invalidateQueries({ queryKey });
  }
}

export function connectEvents(
  queryClient: QueryClient,
  onStatus?: (status: SseStatus) => void,
): () => void {
  onStatus?.("connecting");
  const source = new EventSource(`${BASE_URL}/events`);

  let hasOpened = false;
  source.onopen = () => {
    if (hasOpened) {
      // Reconnected after a drop: events emitted during the gap were missed, so
      // refetch all authoritative state (INF-11 loss-tolerance).
      void queryClient.invalidateQueries();
    }
    hasOpened = true;
    onStatus?.("open");
  };
  source.onerror = () => onStatus?.("closed");

  // Heartbeat keeps the connection observable; no cache effect.
  source.addEventListener("heartbeat", () => {});

  // Map each domain event onto its query-key invalidations.
  const handlers = SSE_EVENT_NAMES.map((name): [SseEventName, () => void] => {
    const handler = () => invalidateForEvent(queryClient, name);
    source.addEventListener(name, handler);
    return [name, handler];
  });

  return () => {
    for (const [name, handler] of handlers) {
      source.removeEventListener(name, handler);
    }
    source.close();
    onStatus?.("closed");
  };
}
