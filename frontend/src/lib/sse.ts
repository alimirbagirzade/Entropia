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

// Reconnect backoff: the browser's EventSource auto-retries only while it can
// (readyState CONNECTING). When the server closes the stream non-retryably or the
// initial handshake fails, readyState lands on CLOSED and native retry STOPS — the
// dashboard would then sit SSE-blind, missing every live invalidation until a full
// reload. So on a CLOSED error we drive our own exponential backoff (capped) until
// the stream comes back; a successful reopen triggers the same gap full-refresh as
// a native reconnect (INF-11 loss-tolerance).
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export function connectEvents(
  queryClient: QueryClient,
  onStatus?: (status: SseStatus) => void,
): () => void {
  let hasOpened = false;
  let disposed = false;
  let attempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  // Teardown for the CURRENT EventSource (detach listeners + close). Replaced on
  // every (re)open so a reconnect never leaks the prior connection's handlers.
  let teardownSource: (() => void) | null = null;

  function scheduleReconnect(): void {
    if (disposed || reconnectTimer !== null) return;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempt, RECONNECT_MAX_MS);
    attempt += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      openSource();
    }, delay);
  }

  function openSource(): void {
    if (disposed) return;
    teardownSource?.();

    const source = new EventSource(`${BASE_URL}/events`);
    const handlers: Array<[string, () => void]> = [];
    const on = (type: string, handler: () => void): void => {
      source.addEventListener(type, handler);
      handlers.push([type, handler]);
    };

    source.onopen = () => {
      attempt = 0; // healthy again — reset the backoff ramp
      if (hasOpened) {
        // Reconnected after a drop (native OR our backoff): events emitted during
        // the gap were missed, so refetch all authoritative state.
        void queryClient.invalidateQueries();
      }
      hasOpened = true;
      onStatus?.("open");
    };
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        // Native retry has given up — take over with our own backoff.
        onStatus?.("connecting");
        scheduleReconnect();
      } else {
        // readyState CONNECTING: the browser is auto-retrying. Stay observable as
        // "connecting" rather than falsely reporting a dead connection.
        onStatus?.("connecting");
      }
    };

    // Heartbeat keeps the connection observable; no cache effect.
    on("heartbeat", () => {});
    // Map each domain event onto its query-key invalidations.
    for (const name of SSE_EVENT_NAMES) {
      on(name, () => invalidateForEvent(queryClient, name));
    }

    teardownSource = () => {
      for (const [type, handler] of handlers) {
        source.removeEventListener(type, handler);
      }
      source.close();
    };
  }

  // A full-page navigation (or a back/forward-cache freeze) never runs React's
  // effect cleanup, so without an unload hook the active EventSource lingers and
  // keeps holding one of the browser's ~6 per-host HTTP/1.1 connection slots — one
  // leaked slot per bfcached page until eviction — which can starve every later
  // same-host request (the next GET queues indefinitely). `pagehide` fires for both
  // real unload and bfcache freeze, so release the stream (and any pending backoff
  // timer) there; `pageshow` reopens it if the page is later restored from bfcache.
  // (beforeunload is intentionally avoided: registering one can disqualify a page
  // from bfcache in some browsers, defeating the point.)
  function closeCurrentSource(): void {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    teardownSource?.();
    teardownSource = null;
    onStatus?.("closed");
  }
  function reopenOnRestore(event: PageTransitionEvent): void {
    // Only a bfcache restore (persisted) needs a fresh stream; the initial-load
    // pageshow (persisted === false) is a no-op. The reopen's onopen full-refresh
    // heals any gap missed while frozen (hasOpened is still true from before).
    if (disposed || !event.persisted) return;
    onStatus?.("connecting");
    openSource();
  }
  window.addEventListener("pagehide", closeCurrentSource);
  window.addEventListener("pageshow", reopenOnRestore);

  onStatus?.("connecting");
  openSource();

  return () => {
    disposed = true;
    window.removeEventListener("pagehide", closeCurrentSource);
    window.removeEventListener("pageshow", reopenOnRestore);
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    teardownSource?.();
    teardownSource = null;
    onStatus?.("closed");
  };
}
