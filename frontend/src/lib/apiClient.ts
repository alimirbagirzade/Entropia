// Thin fetch wrapper. The backend is the source of truth; this client never
// computes domain state. It surfaces the canonical error envelope as ApiError.

import { getDevActorId } from "./devActor";
import { getSessionToken } from "./session";
import type { ApiErrorResponse } from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

// R2-10 (GAP madde 14): every request carries a visible timeout so a dead
// backend surfaces as a typed error instead of an infinite pending promise
// (react-query would otherwise sit in isLoading forever → endless spinner).
export const REQUEST_TIMEOUT_MS = 15_000;

// Transport-level failure code (timeout / connection refused / DNS). ADDITIVE to
// the canonical envelope codes: status 0 marks "no HTTP response at all". Status
// 0 falls under the queryClient "no retry below 500" rule, so a dead backend
// never triggers an automatic retry storm — Retry stays a user action.
export const NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Array<Record<string, unknown>>;

  constructor(status: number, code: string, message: string, details: Array<Record<string, unknown>> = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

const WRITE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

// In-flight write requests, keyed by the LOGICAL operation (method + path +
// body) — deliberately NOT the headers, so GAP-13's fresh-per-attempt
// Idempotency-Key does not defeat the dedup. A same-tick double-submit (two
// clicks land before React re-renders and disables the button — a button
// `disabled={isPending}` guard only applies after a render) fires two mutate()
// calls; without this they would carry two distinct keys and the backend would
// apply two side effects: a duplicate revision / work object / run. Collapsing
// identical concurrent writes onto ONE promise means a single request and a
// single effect. The entry is dropped the moment the request settles, so a
// genuine retry after completion or failure fires fresh (a new attempt, a new
// key). Distinct payloads produce distinct signatures and are never merged.
const inFlightWrites = new Map<string, Promise<unknown>>();

function writeSignature(method: string, path: string, body: unknown): string | null {
  try {
    return `${method} ${path} ${body === undefined ? "" : JSON.stringify(body)}`;
  } catch {
    // A body that cannot be serialized (never produced by this client, whose
    // bodies always go out as JSON.stringify below) is treated as its own
    // request and never shared.
    return null;
  }
}

export function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  // Reads are safe to fire twice (react-query already dedups queries); only
  // writes carry a duplicate side effect, so the single-flight guard is scoped
  // to them.
  if (!WRITE_METHODS.has(method)) {
    return executeRequest<T>(path, options);
  }
  const signature = writeSignature(method, path, options.body);
  if (signature === null) {
    return executeRequest<T>(path, options);
  }
  const existing = inFlightWrites.get(signature);
  if (existing) {
    return existing as Promise<T>;
  }
  const pending = executeRequest<T>(path, options).finally(() => {
    inFlightWrites.delete(signature);
  });
  inFlightWrites.set(signature, pending);
  return pending;
}

// Runs fetch under an AbortController-armed deadline and maps the two
// no-response outcomes (deadline hit, socket-level failure) onto ONE typed
// ApiError so every caller's existing `error.code: error.message` render shows
// a human-readable transport failure instead of a raw DOMException.
async function fetchWithTimeout(input: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  // A caller-supplied signal (react-query cancellation) still aborts the shared
  // controller, so both cancel paths flow through one fetch signal.
  const outer = init.signal;
  const forwardAbort = () => controller.abort(outer?.reason);
  if (outer) {
    if (outer.aborted) forwardAbort();
    else outer.addEventListener("abort", forwardAbort, { once: true });
  }
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (cause) {
    if (outer?.aborted) throw cause; // caller cancelled — not a backend failure
    const timedOut = cause instanceof DOMException && cause.name === "AbortError";
    const networkFailure = cause instanceof TypeError; // fetch's connection-level failure
    // Anything else (including test doubles throwing domain errors) is not a
    // transport failure — rethrow untouched so messages surface verbatim.
    if (!timedOut && !networkFailure) throw cause;
    throw new ApiError(
      0,
      NETWORK_UNAVAILABLE,
      timedOut
        ? `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s — backend unreachable at ${BASE_URL}`
        : `Network error — backend unreachable at ${BASE_URL}`,
    );
  } finally {
    clearTimeout(timer);
    outer?.removeEventListener("abort", forwardAbort);
  }
}

async function executeRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const devActorId = getDevActorId();
  const sessionToken = getSessionToken();
  const response = await fetchWithTimeout(`${BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      // Real auth (AUTH_MODE=session): humans present an opaque Bearer session token.
      ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
      // Dev mode (AUTH_MODE=dev): pick which principal to act as. Both headers may
      // be sent — the server honours only the one its AUTH_MODE trusts, so a stale
      // dev header never spoofs a real session and vice-versa.
      ...(devActorId ? { "X-Actor-Id": devActorId } : {}),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const payload = text ? JSON.parse(text) : undefined;

  if (!response.ok) {
    const err = (payload as ApiErrorResponse | undefined)?.error;
    throw new ApiError(
      response.status,
      err?.code ?? "UNKNOWN",
      err?.message ?? response.statusText,
      err?.details ?? [],
    );
  }
  return payload as T;
}

// Error bodies stay JSON even on text endpoints; fall back to the raw body when
// the response is not the canonical envelope.
function textError(status: number, statusText: string, body: string): ApiError {
  if (body) {
    try {
      const payload = JSON.parse(body) as ApiErrorResponse;
      const err = payload?.error;
      if (err?.code) {
        return new ApiError(status, err.code, err.message ?? statusText, err.details ?? []);
      }
    } catch {
      // Not the JSON envelope (a plain-text error) — fall through to the raw body.
    }
  }
  return new ApiError(status, "UNKNOWN", body || statusText);
}

// Raw text GET for non-JSON endpoints: GET /v1/metrics returns the Prometheus text
// exposition, not the JSON envelope. Auth headers mirror apiRequest.
export async function apiGetText(path: string): Promise<string> {
  const devActorId = getDevActorId();
  const sessionToken = getSessionToken();
  const response = await fetchWithTimeout(`${BASE_URL}${path}`, {
    method: "GET",
    headers: {
      Accept: "text/plain",
      ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
      ...(devActorId ? { "X-Actor-Id": devActorId } : {}),
    },
  });
  const text = await response.text();
  if (!response.ok) {
    throw textError(response.status, response.statusText, text);
  }
  return text;
}

export const api = {
  get: <T>(path: string) => apiRequest<T>(path, { method: "GET" }),
  getText: (path: string) => apiGetText(path),
  post: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => apiRequest<T>(path, { method: "DELETE" }),
};

export { BASE_URL };
