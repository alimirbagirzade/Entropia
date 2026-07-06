import { vi, type Mock } from "vitest";

type RouteHandler = unknown | ((init?: RequestInit) => unknown);

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
