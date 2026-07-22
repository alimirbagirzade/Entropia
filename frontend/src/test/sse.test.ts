import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";

import { connectEvents, EVENT_QUERY_KEYS, SSE_EVENT_NAMES, type SseStatus } from "@/lib/sse";
import { getSessionInvalidations } from "@/lib/session";
import { resetAuthMode, setAuthMode } from "@/lib/authMode";

// AUTH-11: the client now streams over `fetch` (header-capable), not native
// EventSource. This harness fakes `fetch` with a controllable streaming body so a
// test can drive the handshake outcome (200 stream / 401 envelope / network
// failure), push server SSE frames, and end the stream — then assert the resulting
// query invalidations, status transitions, reconnects, and credential handling.

const TOKEN_KEY = "entropia.sessionToken";

// A minimal ReadableStream double: getReader().read() resolves as frames are pushed
// and reports `done` once ended (a clean server close / EOF). Aborting the fetch
// signal ends it too, so a deliberate teardown drains the pump exactly like a real
// aborted body would.
class FakeStream {
  private queued: Uint8Array[] = [];
  private waiting: Array<(r: ReadableStreamReadResult<Uint8Array>) => void> = [];
  private ended = false;
  private readonly encoder = new TextEncoder();

  getReader() {
    return {
      read: (): Promise<ReadableStreamReadResult<Uint8Array>> =>
        new Promise((resolve) => {
          const next = this.queued.shift();
          if (next !== undefined) resolve({ done: false, value: next });
          else if (this.ended) resolve({ done: true, value: undefined });
          else this.waiting.push(resolve);
        }),
      releaseLock: () => {},
      cancel: () => this.end(),
    };
  }

  push(text: string): void {
    const value = this.encoder.encode(text);
    const waiter = this.waiting.shift();
    if (waiter) waiter({ done: false, value });
    else this.queued.push(value);
  }

  end(): void {
    this.ended = true;
    let waiter: ((r: ReadableStreamReadResult<Uint8Array>) => void) | undefined;
    while ((waiter = this.waiting.shift())) waiter({ done: true, value: undefined });
  }
}

class FakeResponse {
  readonly ok: boolean;
  constructor(
    readonly status: number,
    readonly body: FakeStream | null,
    private readonly errorBody?: unknown,
  ) {
    this.ok = status >= 200 && status < 300;
  }

  async text(): Promise<string> {
    return this.errorBody === undefined ? "" : JSON.stringify(this.errorBody);
  }
}

// One captured fetch attempt: the test decides its outcome after connectEvents (or a
// backoff timer) fires it.
class Conn {
  readonly stream = new FakeStream();
  private resolve!: (r: FakeResponse) => void;
  private reject!: (e: unknown) => void;
  readonly response: Promise<FakeResponse>;

  constructor(
    readonly url: string,
    readonly init: RequestInit,
  ) {
    this.response = new Promise<FakeResponse>((res, rej) => {
      this.resolve = res;
      this.reject = rej;
    });
    const signal = init.signal as AbortSignal | null | undefined;
    signal?.addEventListener("abort", () => {
      this.stream.end();
      this.reject(new DOMException("Aborted", "AbortError"));
    });
  }

  header(name: string): string | undefined {
    const headers = this.init.headers as Record<string, string> | undefined;
    return headers?.[name];
  }

  // Handshake resolves as an authenticated 200 stream.
  open(): void {
    this.resolve(new FakeResponse(200, this.stream));
  }

  // Handshake rejected by the server (e.g. anonymous / dead session).
  reject401(code: string): void {
    this.resolve(new FakeResponse(401, null, { error: { code } }));
  }

  // Network-level failure: no HTTP response at all (the fetch promise rejects).
  fail(): void {
    this.reject(new TypeError("network error"));
  }

  // Server closed the stream after it was open (a drop, NOT a deliberate abort).
  dropServer(): void {
    this.stream.end();
  }
}

const conns: Conn[] = [];
const openConnections: Array<() => void> = [];

function lastConn(): Conn {
  const conn = conns.at(-1);
  if (!conn) throw new Error("connectEvents did not call fetch");
  return conn;
}

// Flush pending microtasks (the fetch/read promise chain) without advancing timers,
// so it is safe under both real and fake timers.
async function flush(): Promise<void> {
  for (let i = 0; i < 6; i += 1) await Promise.resolve();
}

function frame(event: string): string {
  return `event: ${event}\ndata: {}\n\n`;
}

function setup() {
  const queryClient = new QueryClient();
  const spy = vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined);
  const statuses: SseStatus[] = [];
  const dispose = connectEvents(queryClient, (s) => statuses.push(s));
  openConnections.push(dispose);
  return { spy, statuses, dispose };
}

// Open the (latest) handshake and let the pump start.
async function openAndSettle(): Promise<Conn> {
  const conn = lastConn();
  conn.open();
  await flush();
  return conn;
}

describe("connectEvents SSE live-invalidation over fetch", () => {
  beforeEach(() => {
    conns.length = 0;
    localStorage.clear();
    resetAuthMode();
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      const conn = new Conn(url, init);
      conns.push(conn);
      return conn.response;
    });
  });

  afterEach(() => {
    while (openConnections.length) openConnections.pop()?.();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
    resetAuthMode();
  });

  // --- credential handling (AUTH-11) ---

  it("streams to /events with no token in the URL", () => {
    setup();
    const conn = lastConn();
    expect(conn.url).toMatch(/\/api\/v1\/events$/);
    expect(conn.url).not.toContain("token");
    expect(conn.url).not.toContain("?"); // no query string at all
    expect(conn.init.method).toBe("GET");
  });

  it("attaches the shared mode-aware credential as a header (session mode)", () => {
    setAuthMode("session");
    localStorage.setItem(TOKEN_KEY, "tok_secret_123");
    setup();
    const conn = lastConn();
    expect(conn.header("Authorization")).toBe("Bearer tok_secret_123");
    // The credential is header-only — it never appears in the request URL.
    expect(conn.url).not.toContain("tok_secret_123");
  });

  it("attaches the dev actor header in dev mode", () => {
    setAuthMode("dev");
    localStorage.setItem("entropia.devActorId", "user_dev_1");
    setup();
    expect(lastConn().header("X-Actor-Id")).toBe("user_dev_1");
  });

  it("triggers the one-shot invalid-session flow on a SESSION_INVALID handshake", async () => {
    setAuthMode("session");
    localStorage.setItem(TOKEN_KEY, "tok_dead");
    const before = getSessionInvalidations();
    setup();
    lastConn().reject401("SESSION_INVALID");
    await flush();
    expect(getSessionInvalidations()).toBe(before + 1);
    // The dead token was cleared by the global flow — no credential lingers.
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("does NOT clear the session on a non-session error (403)", async () => {
    setAuthMode("session");
    localStorage.setItem(TOKEN_KEY, "tok_live");
    const before = getSessionInvalidations();
    setup();
    lastConn().reject401("ACCESS_DENIED"); // 401-shaped double, but a non-session code
    await flush();
    expect(getSessionInvalidations()).toBe(before);
    expect(localStorage.getItem(TOKEN_KEY)).toBe("tok_live");
  });

  // --- taxonomy dispatch ---

  it("maps each specialized event to its query-key prefix", async () => {
    const { spy } = setup();
    const conn = await openAndSettle();
    for (const name of SSE_EVENT_NAMES) {
      const keys = EVENT_QUERY_KEYS[name];
      if (keys.length === 0) continue; // catch-all is covered separately
      spy.mockClear();
      conn.stream.push(frame(name));
      await flush();
      for (const queryKey of keys) {
        expect(spy).toHaveBeenCalledWith({ queryKey });
      }
      expect(spy).toHaveBeenCalledTimes(keys.length);
    }
  });

  it("treats resource.changed as a full refresh (no query key)", async () => {
    const { spy } = setup();
    const conn = await openAndSettle();
    spy.mockClear();
    conn.stream.push(frame("resource.changed"));
    await flush();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith();
  });

  it("ignores heartbeat frames — no cache effect", async () => {
    const { spy } = setup();
    const conn = await openAndSettle();
    spy.mockClear();
    conn.stream.push(frame("heartbeat"));
    await flush();
    expect(spy).not.toHaveBeenCalled();
  });

  it("ignores an unknown event name — no cache effect", async () => {
    const { spy } = setup();
    const conn = await openAndSettle();
    spy.mockClear();
    conn.stream.push(frame("some.future.event"));
    await flush();
    expect(spy).not.toHaveBeenCalled();
  });

  it("reassembles a frame split across two chunks", async () => {
    const { spy } = setup();
    const conn = await openAndSettle();
    spy.mockClear();
    conn.stream.push("event: job.up");
    await flush();
    expect(spy).not.toHaveBeenCalled(); // incomplete frame stays buffered
    conn.stream.push("dated\ndata: {}\n\n");
    await flush();
    expect(spy).toHaveBeenCalledWith({ queryKey: ["jobs"] });
  });

  // --- open / reconnect refresh semantics ---

  it("does not refetch on first open but full-refreshes on reconnect", async () => {
    vi.useFakeTimers();
    try {
      const { spy } = setup();
      await openAndSettle(); // first successful connection
      expect(spy).not.toHaveBeenCalled();
      spy.mockClear();
      lastConn().dropServer(); // server closed the stream
      await flush();
      await vi.advanceTimersByTimeAsync(1000); // backoff fires a fresh handshake
      await openAndSettle(); // reconnected
      expect(spy).toHaveBeenCalledWith(); // gap full-refresh
    } finally {
      vi.useRealTimers();
    }
  });

  it("reports connecting -> open status transitions", async () => {
    const { statuses } = setup();
    await openAndSettle();
    expect(statuses).toEqual(["connecting", "open"]);
  });

  it("closes the stream and reports closed on dispose", async () => {
    const { dispose, statuses } = setup();
    await openAndSettle();
    dispose();
    await flush();
    expect(statuses.at(-1)).toBe("closed");
  });

  // --- reconnect resilience (connection-drop self-heal) ---

  it("reconnects with backoff after a dropped stream", async () => {
    vi.useFakeTimers();
    try {
      const { statuses } = setup();
      await openAndSettle();
      expect(conns.length).toBe(1);
      lastConn().dropServer();
      await flush();
      expect(statuses.at(-1)).toBe("connecting");
      expect(conns.length).toBe(1); // waiting on backoff, not yet
      await vi.advanceTimersByTimeAsync(1000); // RECONNECT_BASE_MS
      expect(conns.length).toBe(2); // backoff opened a fresh handshake
      await openAndSettle();
      expect(statuses.at(-1)).toBe("open");
    } finally {
      vi.useRealTimers();
    }
  });

  it("reconnects with backoff after a network failure at handshake", async () => {
    vi.useFakeTimers();
    try {
      const { statuses } = setup();
      lastConn().fail(); // fetch rejects — no response at all
      await flush();
      expect(statuses.at(-1)).toBe("connecting");
      await vi.advanceTimersByTimeAsync(1000);
      expect(conns.length).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("cancels a pending backoff reconnect on dispose", async () => {
    vi.useFakeTimers();
    try {
      const { dispose, statuses } = setup();
      await openAndSettle();
      lastConn().dropServer(); // schedules a backoff reconnect
      await flush();
      dispose();
      expect(statuses.at(-1)).toBe("closed");
      await vi.advanceTimersByTimeAsync(60000);
      // Disposed before the timer fired — no reconnect attempt is made.
      expect(conns.length).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  // --- unload / bfcache resilience (connection-slot leak prevention) ---

  it("closes the stream and cancels a pending reconnect on pagehide", async () => {
    vi.useFakeTimers();
    try {
      const { statuses } = setup();
      await openAndSettle();
      lastConn().dropServer(); // schedules a backoff reconnect
      await flush();
      window.dispatchEvent(new Event("pagehide"));
      expect(statuses.at(-1)).toBe("closed");
      await vi.advanceTimersByTimeAsync(60000);
      // The pending backoff was cancelled — a hidden page never reopens the stream.
      expect(conns.length).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("reopens the stream when the page is restored from bfcache", async () => {
    const { spy } = setup();
    await openAndSettle(); // healthy once (hasOpened = true)
    window.dispatchEvent(new Event("pagehide")); // frozen into bfcache
    spy.mockClear();

    const restore = new Event("pageshow");
    Object.defineProperty(restore, "persisted", { value: true });
    window.dispatchEvent(restore);
    await flush();
    expect(conns.length).toBe(2); // a fresh stream is opened
    await openAndSettle();
    // Reopening after the frozen gap full-refreshes authoritative state (INF-11).
    expect(spy).toHaveBeenCalledWith();
  });

  it("ignores the initial-load pageshow (not a bfcache restore)", async () => {
    setup();
    await openAndSettle();
    const restore = new Event("pageshow");
    Object.defineProperty(restore, "persisted", { value: false });
    window.dispatchEvent(restore);
    await flush();
    // persisted === false is the normal first load — no extra stream is opened.
    expect(conns.length).toBe(1);
  });
});
