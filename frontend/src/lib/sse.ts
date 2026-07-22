// Central SSE client (Module 20 §10). SSE is a refresh signal, NOT state: on each
// domain event we invalidate the matching query keys so the UI refetches
// authoritative state from the server. Delivery is loss-tolerant (INF-11) — a
// missed event self-heals on the next refetch, and a reconnect triggers a full
// refresh so no view is left stale across a connection gap.
//
// AUTH-11: the stream is a PROTECTED channel. The native `EventSource` cannot send
// a `Bearer` / `X-Actor-Id` header, so this client streams over `fetch` instead —
// it carries the exact same one credential the active AUTH_MODE trusts, via the
// shared selector (`apiClient.authHeaders`). The credential rides in a HEADER only:
// it is never placed in the URL query string and never logged. The server sends a
// minimal invalidation envelope (an event NAME, empty body), so this client reads
// only the event type and never a domain/audit payload.

import type { QueryClient, QueryKey } from "@tanstack/react-query";
import { authHeaders, BASE_URL, SESSION_INVALID } from "./apiClient";
import { noteSessionInvalid } from "./session";

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

const EVENT_NAME_SET = new Set<string>(SSE_EVENT_NAMES);

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

// Reconnect backoff: unlike native EventSource, a fetch stream does not auto-retry
// at all — when the connection drops (network error, server close, EOF) or the
// handshake fails, we must reopen it ourselves or the dashboard sits SSE-blind,
// missing every live invalidation until a full reload. So every non-deliberate
// close drives an exponential backoff (capped); a successful reopen triggers the
// same gap full-refresh as a reconnect (INF-11 loss-tolerance).
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

// Read the canonical error envelope from a failed handshake to detect a rejected
// Bearer session. Only the invalid-session code may clear the local session, and
// it does so exactly once (noteSessionInvalid is guarded on a stored token), so a
// backoff loop of anonymous retries never re-fires the redirect. Never logs the
// body — it could echo request context; the token itself is header-only anyway.
async function noteIfSessionInvalid(response: Response): Promise<void> {
  let code = "";
  try {
    const text = await response.text();
    if (text) {
      const payload = JSON.parse(text) as { error?: { code?: string } };
      code = payload.error?.code ?? "";
    }
  } catch {
    // A non-JSON / unreadable error body carries no code to act on — ignore it.
  }
  if (code === SESSION_INVALID) noteSessionInvalid();
}

export function connectEvents(
  queryClient: QueryClient,
  onStatus?: (status: SseStatus) => void,
): () => void {
  let disposed = false;
  let hasOpened = false;
  let attempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  // The AbortController for the CURRENT fetch stream. Replaced on every (re)open;
  // aborting it is how we deliberately tear a stream down (dispose / pagehide /
  // superseding reopen) WITHOUT that abort being mistaken for a connection drop.
  let controller: AbortController | null = null;

  function scheduleReconnect(): void {
    if (disposed || reconnectTimer !== null) return;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempt, RECONNECT_MAX_MS);
    attempt += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      void openStream();
    }, delay);
  }

  // A drop that was NOT a deliberate abort: report connecting and ramp the backoff.
  function onDrop(local: AbortController): void {
    if (disposed || local.signal.aborted || controller !== local) return;
    onStatus?.("connecting");
    scheduleReconnect();
  }

  // Parse SSE wire frames (separated by a blank line) out of the streamed body and
  // dispatch each by its event NAME. The minimal server envelope carries no data we
  // read, so only the `event:` field matters; heartbeat and unknown names are no-ops.
  async function pump(body: ReadableStream<Uint8Array>, local: AbortController): Promise<void> {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) return;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          if (local.signal.aborted) return;
          dispatchFrame(frame);
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  function dispatchFrame(frame: string): void {
    for (const line of frame.split(/\r?\n/)) {
      if (!line.startsWith("event:")) continue;
      const name = line.slice("event:".length).trim();
      if (EVENT_NAME_SET.has(name)) invalidateForEvent(queryClient, name as SseEventName);
      // "heartbeat" and any unrecognized event keep the stream observable but have
      // no cache effect — a single `event:` line per frame, so stop scanning.
      return;
    }
  }

  async function openStream(): Promise<void> {
    if (disposed) return;
    controller?.abort();
    const local = new AbortController();
    controller = local;

    try {
      const response = await fetch(`${BASE_URL}/events`, {
        method: "GET",
        // Header-only credential (AUTH-11): the shared mode-aware selector attaches
        // exactly the one credential the active AUTH_MODE trusts. Never a query param.
        headers: { Accept: "text/event-stream", ...authHeaders() },
        signal: local.signal,
      });
      if (local.signal.aborted || controller !== local) return;

      if (!response.ok || response.body === null) {
        // A rejected handshake: surface an invalid session to the global one-shot
        // flow, then treat it as a drop and retry on the capped backoff.
        await noteIfSessionInvalid(response);
        onDrop(local);
        return;
      }

      // Connected. Reset the backoff ramp; a reconnect (native drop OR our backoff)
      // means events emitted during the gap were missed — refetch all state.
      attempt = 0;
      if (hasOpened) void queryClient.invalidateQueries();
      hasOpened = true;
      onStatus?.("open");

      await pump(response.body, local);
      onDrop(local); // stream ended (server close / EOF) — reopen unless disposed
    } catch {
      // A deliberate abort lands here too; onDrop filters it out via signal.aborted.
      onDrop(local);
    }
  }

  // A full-page navigation (or a back/forward-cache freeze) never runs React's
  // effect cleanup, so without an unload hook the active stream lingers and keeps
  // holding one of the browser's per-host HTTP connection slots — one leaked slot
  // per bfcached page until eviction — which can starve later same-host requests.
  // `pagehide` fires for both real unload and bfcache freeze, so release the stream
  // (and any pending backoff timer) there; `pageshow` reopens it if the page is
  // later restored from bfcache. (beforeunload is intentionally avoided: registering
  // one can disqualify a page from bfcache in some browsers, defeating the point.)
  function closeCurrentStream(): void {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    controller?.abort();
    controller = null;
    onStatus?.("closed");
  }
  function reopenOnRestore(event: PageTransitionEvent): void {
    // Only a bfcache restore (persisted) needs a fresh stream; the initial-load
    // pageshow (persisted === false) is a no-op. The reopen's open full-refresh
    // heals any gap missed while frozen (hasOpened is still true from before).
    if (disposed || !event.persisted) return;
    onStatus?.("connecting");
    void openStream();
  }
  window.addEventListener("pagehide", closeCurrentStream);
  window.addEventListener("pageshow", reopenOnRestore);

  onStatus?.("connecting");
  void openStream();

  return () => {
    disposed = true;
    window.removeEventListener("pagehide", closeCurrentStream);
    window.removeEventListener("pageshow", reopenOnRestore);
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    controller?.abort();
    controller = null;
    onStatus?.("closed");
  };
}
