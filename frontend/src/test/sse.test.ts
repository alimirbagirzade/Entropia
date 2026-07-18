import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";

import {
  connectEvents,
  EVENT_QUERY_KEYS,
  SSE_EVENT_NAMES,
  type SseStatus,
} from "@/lib/sse";

type Listener = (event: MessageEvent) => void;

// Minimal in-memory EventSource double: records listeners so a test can dispatch
// server frames and assert the resulting query invalidations. `readyState` mirrors
// the DOM contract (CONNECTING = auto-retrying, CLOSED = native retry gave up) so a
// test can steer the reconnect path.
class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static last: FakeEventSource | null = null;
  static constructed = 0;
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  readyState = FakeEventSource.CONNECTING;
  private listeners = new Map<string, Set<Listener>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
    FakeEventSource.constructed += 1;
  }

  addEventListener(type: string, cb: Listener): void {
    const set = this.listeners.get(type) ?? new Set<Listener>();
    set.add(cb);
    this.listeners.set(type, set);
  }

  removeEventListener(type: string, cb: Listener): void {
    this.listeners.get(type)?.delete(cb);
  }

  close(): void {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  // --- test helpers ---
  emit(type: string, data = "{}"): void {
    for (const cb of this.listeners.get(type) ?? []) {
      cb(new MessageEvent(type, { data }));
    }
  }

  open(): void {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.();
  }

  // Simulate a connection error at a given readyState: CONNECTING = the browser is
  // auto-retrying; CLOSED = native retry has given up (drives our own backoff).
  error(readyState: number): void {
    this.readyState = readyState;
    this.onerror?.();
  }

  listenerCount(type: string): number {
    return this.listeners.get(type)?.size ?? 0;
  }
}

// connectEvents registers window pagehide/pageshow listeners; a test that does not
// dispose would leak them across cases (a later window.dispatchEvent would fire the
// stale handlers and skew the construction count). Track every instance and dispose
// them all in afterEach.
let disposers: Array<() => void> = [];

function setup() {
  const queryClient = new QueryClient();
  const spy = vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined);
  const statuses: SseStatus[] = [];
  const dispose = connectEvents(queryClient, (s) => statuses.push(s));
  disposers.push(dispose);
  const src = FakeEventSource.last;
  if (!src) throw new Error("connectEvents did not construct an EventSource");
  return { spy, src, dispose, statuses };
}

function persistedPageShow(): Event {
  const event = new Event("pageshow");
  Object.defineProperty(event, "persisted", { value: true });
  return event;
}

describe("connectEvents SSE live-invalidation", () => {
  beforeEach(() => {
    FakeEventSource.last = null;
    FakeEventSource.constructed = 0;
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    for (const dispose of disposers) dispose();
    disposers = [];
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("subscribes to every taxonomy event plus heartbeat", () => {
    const { src } = setup();
    expect(src.listenerCount("heartbeat")).toBe(1);
    for (const name of SSE_EVENT_NAMES) {
      expect(src.listenerCount(name)).toBe(1);
    }
  });

  it("maps each specialized event to its query-key prefix", () => {
    const { src, spy } = setup();
    for (const name of SSE_EVENT_NAMES) {
      const keys = EVENT_QUERY_KEYS[name];
      if (keys.length === 0) continue; // catch-all is covered separately
      spy.mockClear();
      src.emit(name);
      for (const queryKey of keys) {
        expect(spy).toHaveBeenCalledWith({ queryKey });
      }
      expect(spy).toHaveBeenCalledTimes(keys.length);
    }
  });

  it("treats resource.changed as a full refresh (no query key)", () => {
    const { src, spy } = setup();
    spy.mockClear();
    src.emit("resource.changed");
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith();
  });

  it("ignores heartbeat frames — no cache effect", () => {
    const { src, spy } = setup();
    spy.mockClear();
    src.emit("heartbeat");
    expect(spy).not.toHaveBeenCalled();
  });

  it("does not refetch on first open but full-refreshes on reconnect", () => {
    const { src, spy } = setup();
    spy.mockClear();
    src.open(); // first successful connection
    expect(spy).not.toHaveBeenCalled();
    src.open(); // reconnect after a drop
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith();
  });

  it("reports connecting -> open status transitions", () => {
    const { src, statuses } = setup();
    src.open();
    expect(statuses).toEqual(["connecting", "open"]);
  });

  it("closes the source and detaches listeners on dispose", () => {
    const { src, dispose, statuses } = setup();
    dispose();
    expect(src.closed).toBe(true);
    for (const name of SSE_EVENT_NAMES) {
      expect(src.listenerCount(name)).toBe(0);
    }
    expect(statuses.at(-1)).toBe("closed");
  });

  // --- reconnect resilience (connection-drop self-heal) ---

  it("stays connecting on a transient error and does not self-reconnect", () => {
    vi.useFakeTimers();
    try {
      const { src, statuses } = setup();
      src.open();
      // readyState CONNECTING: the browser is auto-retrying on its own.
      src.error(FakeEventSource.CONNECTING);
      expect(statuses.at(-1)).toBe("connecting");
      const before = FakeEventSource.constructed;
      vi.advanceTimersByTime(60000);
      // No backoff timer scheduled — native retry owns this case.
      expect(FakeEventSource.constructed).toBe(before);
    } finally {
      vi.useRealTimers();
    }
  });

  it("reconnects with backoff after a fatal error and full-refreshes on reopen", () => {
    vi.useFakeTimers();
    try {
      const { src, spy, statuses } = setup();
      src.open(); // first healthy connection (hasOpened = true)
      spy.mockClear();
      // readyState CLOSED: native retry gave up — our backoff must take over.
      src.error(FakeEventSource.CLOSED);
      expect(statuses.at(-1)).toBe("connecting");
      expect(FakeEventSource.constructed).toBe(1); // waiting on backoff, not yet
      vi.advanceTimersByTime(1000); // RECONNECT_BASE_MS
      expect(FakeEventSource.constructed).toBe(2); // backoff fired a fresh stream
      const next = FakeEventSource.last;
      if (!next) throw new Error("backoff did not construct a new EventSource");
      expect(next).not.toBe(src);
      next.open(); // reconnected
      expect(statuses.at(-1)).toBe("open");
      // Gap full-refresh (INF-11): reopening after a drop refetches everything.
      expect(spy).toHaveBeenCalledWith();
    } finally {
      vi.useRealTimers();
    }
  });

  it("cancels a pending backoff reconnect on dispose", () => {
    vi.useFakeTimers();
    try {
      const { src, dispose, statuses } = setup();
      src.open();
      src.error(FakeEventSource.CLOSED); // schedules a backoff reconnect
      dispose();
      expect(statuses.at(-1)).toBe("closed");
      vi.advanceTimersByTime(60000);
      // Disposed before the timer fired — no reconnect attempt is made.
      expect(FakeEventSource.constructed).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  // --- unload / bfcache lifecycle (connection-leak guard) ---

  it("closes the stream on pagehide and reopens on a bfcache restore", () => {
    const { src } = setup();
    // A full-document navigation / bfcache freeze never runs the dispose cleanup,
    // so the stream must proactively close on pagehide to release its connection.
    window.dispatchEvent(new Event("pagehide"));
    expect(src.closed).toBe(true);

    // A persisted (bfcache) pageshow reopens a fresh stream so the page stays live.
    const before = FakeEventSource.constructed;
    window.dispatchEvent(persistedPageShow());
    expect(FakeEventSource.constructed).toBe(before + 1);
  });

  it("does not reopen on a non-persisted pageshow", () => {
    setup();
    window.dispatchEvent(new Event("pagehide"));
    const before = FakeEventSource.constructed;
    // A normal (non-bfcache) load already opened the stream at mount — a plain
    // pageshow must not spawn a duplicate.
    window.dispatchEvent(new Event("pageshow"));
    expect(FakeEventSource.constructed).toBe(before);
  });

  it("cancels a pending backoff reconnect on pagehide", () => {
    vi.useFakeTimers();
    try {
      const { src } = setup();
      src.open();
      src.error(FakeEventSource.CLOSED); // schedules a backoff reconnect
      window.dispatchEvent(new Event("pagehide"));
      const before = FakeEventSource.constructed;
      vi.advanceTimersByTime(60000);
      // The pending backoff timer was cancelled with the stream.
      expect(FakeEventSource.constructed).toBe(before);
    } finally {
      vi.useRealTimers();
    }
  });

  it("detaches the pagehide/pageshow listeners on dispose", () => {
    const { dispose } = setup();
    dispose();
    const before = FakeEventSource.constructed;
    // After dispose nothing should react to page lifecycle events.
    window.dispatchEvent(persistedPageShow());
    window.dispatchEvent(new Event("pagehide"));
    expect(FakeEventSource.constructed).toBe(before);
  });
});
