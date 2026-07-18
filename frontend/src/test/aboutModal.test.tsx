import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { Layout } from "@/app/Layout";
import { stubApi } from "./helpers/apiStub";

// GAP a11y — the Help ▸ About dialog must manage focus like every other modal.
// It now renders onto the shared <Modal> chrome, so Escape closes it and focus is
// restored to the invoking Help ▸ About button (accessibility.md: "Support Escape
// to close modals … Restore focus to trigger element on close"). The Ready-Check
// modal already used the shared Modal; migrating About onto it retires the last
// raw-markup dialog in the app.

// jsdom has no EventSource, and Layout's SSE effect constructs one on mount. A
// minimal inert double lets the shell render without touching the network.
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

describe("Help ▸ About dialog focus management", () => {
  it("opens onto the shared Modal, closes on Escape, and restores focus to the trigger", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    stubApi({
      "GET /me": { is_authenticated: false, is_admin: false, role: "anonymous" },
      "GET /meta": { environment: "test" },
    });
    renderLayout();

    // The Help ▸ About menu leaf is a real <button> (its dropdown is CSS-hidden,
    // but the node is present in the DOM — CSS is disabled under Vitest). Focus it
    // as a keyboard user would before activating, so it is the recorded trigger.
    const trigger = screen.getByRole("button", { name: "About" });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    fireEvent.click(trigger);

    // The dialog opened, is labelled by its visible heading, and focus moved into
    // it (onto the Close button — the first focusable inside the card).
    const dialog = screen.getByRole("dialog", { name: "Entropia V18" });
    expect(dialog).toBeTruthy();
    const close = screen.getByRole("button", { name: "Close" });
    expect(document.activeElement).toBe(close);

    // Escape closes the dialog and returns focus to the Help ▸ About trigger.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
