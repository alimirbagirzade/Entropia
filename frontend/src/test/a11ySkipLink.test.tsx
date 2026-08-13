import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Layout } from "@/app/Layout";
import { stubApi } from "./helpers/apiStub";

// A-08 precheck K-2 (WCAG 2.4.1 Bypass Blocks). Before ADIM 48 the first
// tabbable node on all 23 routes was the shell's "Log out" button, so every
// route started by tabbing the whole menu bar.
//
// This pin lives at the unit level ON PURPOSE. The e2e probe that MEASURED K-2
// (e2e/specs/20-a11y-prechecks.spec.ts) reports it as an ADVISORY — it is not a
// gate, so it cannot stop a regression; and it only runs against a full Compose
// stack. This runs in the ordinary vitest suite on every change to the shell.
//
// The tabbable selector below is copied VERBATIM from that probe so the two
// agree on what "first tabbable" means. Do not "improve" it here in isolation —
// if it changes, change it in both places or the advisory and the gate will
// disagree about the same DOM.
const TABBABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

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

function renderShell(): HTMLElement {
  vi.stubGlobal("EventSource", FakeEventSource);
  stubApi({
    "GET /me": { is_authenticated: true, is_admin: true, role: "admin" },
    "GET /meta": { name: "Entropia V18", version: "0", environment: "local", api_base_path: "/v1" },
    "GET /health/live": { status: "ok" },
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { container } = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Layout />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return container;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("shell skip link (A-08 precheck K-2 / WCAG 2.4.1)", () => {
  it("is the FIRST tabbable node in the shell, ahead of the auth control and the menu bar", async () => {
    const container = renderShell();

    // Wait for the shell to SETTLE before reading the tab order: the topbar's
    // identity badge is the last thing the shell paints, and the auth control
    // that used to hold first place mounts before it. Reading the order early
    // would pass for the wrong reason.
    await screen.findByText("admin");

    const tabbables = Array.from(container.querySelectorAll<HTMLElement>(TABBABLE));
    const first = tabbables[0];
    expect(first, "the shell renders no tabbable node at all").toBeTruthy();
    expect(first.tagName.toLowerCase()).toBe("a");
    expect(first.getAttribute("href")).toBe("#main-content");

    // And it is genuinely AHEAD of the chrome, not merely present: the next
    // tabbable is still inside the banner (the auth control), and the menu bar
    // comes after that. That ordering is the whole point of K-2.
    expect(tabbables.length, "shell has no chrome after the skip link").toBeGreaterThan(1);
    expect(container.querySelector("header")?.contains(tabbables[1])).toBe(true);
  });

  it("points at a <main> that can actually take focus and stays out of the tab order", async () => {
    const container = renderShell();
    await screen.findByText("admin");

    const link = container.querySelector<HTMLAnchorElement>('a[href="#main-content"]');
    expect(link).toBeTruthy();

    const main = container.querySelector("main");
    expect(main).toBeTruthy();
    // The href must resolve to a real element, or the link scrolls nowhere.
    expect(main?.id).toBe("main-content");
    // tabindex="-1" is what lets the browser MOVE focus into <main>; without it
    // focus stays on the link and the next Tab re-enters the menu bar.
    expect(main?.getAttribute("tabindex")).toBe("-1");
    // -1, not 0: <main> itself must not become a tab stop.
    expect(Array.from(container.querySelectorAll<HTMLElement>(TABBABLE))).not.toContain(main);
  });

  it("keeps the link reachable — hidden by CSS, never by hidden/aria-hidden/display", async () => {
    const container = renderShell();
    await waitFor(() => expect(container.querySelector('a[href="#main-content"]')).toBeTruthy());

    const link = container.querySelector<HTMLAnchorElement>('a[href="#main-content"]')!;
    // The visual hiding is the .skip-link clip/1px pattern in global.css (which
    // jsdom does not evaluate). What this asserts is that the markup does not
    // ALSO hide it in a way that would remove it from the tab order and from
    // the accessibility tree, which is the usual way a skip link dies.
    expect(link.hasAttribute("hidden")).toBe(false);
    expect(link.getAttribute("aria-hidden")).toBeNull();
    expect(link.getAttribute("tabindex")).toBeNull();
    expect(link.textContent?.trim().length).toBeGreaterThan(0);
  });
});
