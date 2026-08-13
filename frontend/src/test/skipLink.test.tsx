import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Layout } from "@/app/Layout";
import { stubApi } from "./helpers/apiStub";

// K-2 (RC §6.5, PO decision 2026-08-12). The regression this pins is not "a link
// exists" — it is the THREE-part contract that makes the link do anything:
//   1. it comes FIRST in the shell, before the menu bar (the whole point is not
//      tabbing the menu on every route),
//   2. its href resolves to a real element (a skip link to a missing id sends
//      focus nowhere and reads as working),
//   3. that element is the main landmark and is programmatically focusable, so
//      the jump moves focus rather than only scrolling.
// A test that asserted only (1) would stay green through a rename of the target.

class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readyState = FakeEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  addEventListener(): void {}
  removeEventListener(): void {}
  close(): void {}
}

function renderLayout() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Layout />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("K-2 — skip link", () => {
  it("is the shell's first element and jumps to the focusable main landmark", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    stubApi({
      "GET /me": { is_authenticated: true, is_admin: true, role: "Admin" },
      "GET /meta": { name: "Entropia V18", version: "0", environment: "local", api_base_path: "/v1" },
      "GET /health/live": { status: "ok" },
    });
    renderLayout();

    const link = await screen.findByRole("link", { name: "Skip to main content" });

    // (1) first — nothing tabbable may precede it inside the shell.
    const shell = link.closest(".app-shell");
    expect(shell?.firstElementChild).toBe(link);

    // (2) the href resolves.
    const href = link.getAttribute("href") ?? "";
    expect(href.startsWith("#")).toBe(true);
    const target = document.getElementById(href.slice(1));
    expect(target, `skip link points at ${href}, which no element carries`).not.toBeNull();

    // (3) the target IS main, and can hold focus.
    expect(target?.tagName.toLowerCase()).toBe("main");
    expect(target?.getAttribute("tabindex")).toBe("-1");
  });
});
