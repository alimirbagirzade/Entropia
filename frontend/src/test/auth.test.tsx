import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/apiClient";
import { clearSession, getSessionToken, getStoredUser, setSession, subscribe } from "@/lib/session";
import { Login } from "@/pages/Login";
import type { AuthUser } from "@/lib/types";

const USER: AuthUser = { user_id: "u1", username: "alice", display_name: "Alice", role: "user" };

type FetchFn = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function okFetch(body: unknown) {
  return vi.fn<FetchFn>(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      statusText: "OK",
      text: () => Promise.resolve(JSON.stringify(body)),
    } as unknown as Response),
  );
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("session store", () => {
  it("round-trips token and user, then clears", () => {
    expect(getSessionToken()).toBeNull();
    setSession({ token: "tok_abc", user: USER, expiresAt: null });
    expect(getSessionToken()).toBe("tok_abc");
    expect(getStoredUser()).toEqual(USER);
    clearSession();
    expect(getSessionToken()).toBeNull();
    expect(getStoredUser()).toBeNull();
  });

  it("notifies subscribers on set and clear", () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    setSession({ token: "t", user: USER, expiresAt: null });
    clearSession();
    expect(listener).toHaveBeenCalledTimes(2);
    unsubscribe();
    setSession({ token: "t2", user: USER, expiresAt: null });
    expect(listener).toHaveBeenCalledTimes(2);
  });
});

describe("apiClient auth header", () => {
  it("attaches Authorization: Bearer when a session token is present", async () => {
    setSession({ token: "tok_xyz", user: USER, expiresAt: null });
    const fetchMock = okFetch({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await api.get("/me");
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer tok_xyz");
  });

  it("omits Authorization when no session token is present", async () => {
    const fetchMock = okFetch({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await api.get("/me");
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });
});

describe("Login page", () => {
  function renderLogin() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/login"]}>
          <Login />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("logs in and stores the returned session token", async () => {
    const fetchMock = okFetch({ token: "tok_login", session_id: "s1", expires_at: null, user: USER });
    vi.stubGlobal("fetch", fetchMock);
    renderLogin();

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(getSessionToken()).toBe("tok_login"));
    expect(String(fetchMock.mock.calls[0][0])).toContain("/auth/login");
  });

  it("blocks submit and shows a hint when required fields are empty", async () => {
    const fetchMock = okFetch({});
    vi.stubGlobal("fetch", fetchMock);
    renderLogin();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(screen.getByText("Username is required")).toBeInTheDocument());
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
