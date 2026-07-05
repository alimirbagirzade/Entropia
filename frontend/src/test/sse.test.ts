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
// server frames and assert the resulting query invalidations.
class FakeEventSource {
  static last: FakeEventSource | null = null;
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  private listeners = new Map<string, Set<Listener>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
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
  }

  // --- test helpers ---
  emit(type: string, data = "{}"): void {
    for (const cb of this.listeners.get(type) ?? []) {
      cb(new MessageEvent(type, { data }));
    }
  }

  open(): void {
    this.onopen?.();
  }

  listenerCount(type: string): number {
    return this.listeners.get(type)?.size ?? 0;
  }
}

function setup() {
  const queryClient = new QueryClient();
  const spy = vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined);
  const statuses: SseStatus[] = [];
  const dispose = connectEvents(queryClient, (s) => statuses.push(s));
  const src = FakeEventSource.last;
  if (!src) throw new Error("connectEvents did not construct an EventSource");
  return { spy, src, dispose, statuses };
}

describe("connectEvents SSE live-invalidation", () => {
  beforeEach(() => {
    FakeEventSource.last = null;
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
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
});
