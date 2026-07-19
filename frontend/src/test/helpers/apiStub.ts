import { vi, type Mock } from "vitest";

type RouteHandler = unknown | ((init?: RequestInit) => unknown);

// Tagged sentinel a route can return to force a non-ok response carrying the
// canonical error envelope, so a test can exercise the ApiError path (e.g. a
// 404 STRATEGY_REVISION_NOT_FOUND) through the same apiClient parsing as prod.
interface ApiErrorRoute {
  readonly __apiError: { status: number; code: string; message: string };
}

export function apiErrorRoute(status: number, code: string, message = code): ApiErrorRoute {
  return { __apiError: { status, code, message } };
}

function isApiErrorRoute(value: unknown): value is ApiErrorRoute {
  return typeof value === "object" && value !== null && "__apiError" in value;
}

// Route-aware fetch double for component tests. Keys are "<METHOD> <path
// fragment>" (e.g. "GET /mainboards/default"); the first entry whose method
// matches and whose fragment is contained in the URL wins. Responses go
// through the same text() -> JSON.parse path the real apiClient uses.
export function stubApi(routes: Record<string, RouteHandler>): Mock {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const entry = Object.entries(routes).find(([key]) => {
      const spaceAt = key.indexOf(" ");
      return key.slice(0, spaceAt) === method && url.includes(key.slice(spaceAt + 1));
    });
    if (!entry) {
      throw new Error(`Unexpected fetch: ${method} ${url}`);
    }
    const handler = entry[1];
    const value = typeof handler === "function" ? (handler as (i?: RequestInit) => unknown)(init) : handler;
    if (isApiErrorRoute(value)) {
      const { status, code, message } = value.__apiError;
      return {
        ok: false,
        status,
        statusText: code,
        text: async () => JSON.stringify({ error: { code, message, details: [] } }),
      };
    }
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      text: async () => JSON.stringify(value),
    };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
