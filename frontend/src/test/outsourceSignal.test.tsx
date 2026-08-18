// Add Outsource Signal type chooser (doc 03).
//
// Acceptance (doc 03 §14): AOS-01 (the parent item exposes exactly Trading Signal
// and Trade Log), AOS-02 (no default type is preselected and the §6.2 helper text
// is rendered verbatim) and the §7.1 no-mutation rule — rendering or choosing a
// type issues zero network traffic, so no root/revision/item can exist yet
// (the persisted-side of AOS-04/AOS-05 lives in mainboard.test.tsx).

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { OutsourceSignal } from "@/pages/OutsourceSignal";

// The chooser needs no QueryClientProvider: it binds no hooks and must issue
// no network traffic (doc 03 §7.1 — type choice is transient UI state only).
function renderChooser() {
  render(
    <MemoryRouter initialEntries={["/outsource-signal"]}>
      <Routes>
        <Route path="/outsource-signal" element={<OutsourceSignal />} />
        <Route path="/trading-signal" element={<div>TS WORKBENCH PROBE</div>} />
        <Route path="/trade-log" element={<div>TL WORKBENCH PROBE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

// jsdom implements no sequential focus navigation, so the tab order is derived
// from the DOM the way a browser derives it: natively focusable elements plus
// anything carrying an explicit tabindex, minus whatever a negative value takes
// back out of the sequence.
const TABBABLE_SELECTOR = "a[href], button, input, select, textarea, summary, [tabindex]";

function tabStopsWithin(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(TABBABLE_SELECTOR)).filter(
    (el) => el.tabIndex >= 0 && !el.hasAttribute("disabled"),
  );
}

describe("Add Outsource Signal chooser", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("exposes exactly the two canonical choices with their workbench targets (AOS-01)", () => {
    renderChooser();
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Trading Signal" })).toHaveAttribute(
      "href",
      "/trading-signal",
    );
    expect(screen.getByRole("link", { name: "Trade Log" })).toHaveAttribute("href", "/trade-log");
  });

  // AOS-01.c2 — "keyboard navigation of the chooser matches pointer behaviour".
  //
  // The membership test above proves the two choices are links; it says nothing
  // about the keyboard, and stays green if a choice is taken out of the tab
  // order (`tabIndex={-1}` leaves role, name and href untouched while making the
  // chooser mouse-only). So the assertion here is about the SEQUENCE: inside the
  // chooser the keyboard is offered exactly the stops the pointer has, in the
  // same order — no choice missing, no stop the pointer cannot see.
  //
  // Honest boundary: jsdom has no native anchor activation, so pressing Enter
  // cannot be simulated here. What activation depends on IS asserted — each stop
  // is an <a href> carrying the same target the pointer path navigates to (the
  // two "choosing …" tests below drive that path) — but the keystroke itself is
  // the browser's, and this test does not pretend to press it.
  it("offers the keyboard exactly the pointer's two stops, in the same order (AOS-01)", () => {
    renderChooser();
    const chooser = screen.getByRole("region", { name: "Choose the external object type" });
    expect(tabStopsWithin(chooser)).toEqual([
      screen.getByRole("link", { name: "Trading Signal" }),
      screen.getByRole("link", { name: "Trade Log" }),
    ]);
  });

  it("renders the doc 03 §6.2 chooser and per-choice helpers verbatim", () => {
    renderChooser();
    expect(
      screen.getByText(
        "Choose what the external source represents. Trading Signal is an actionable external event stream; Trade Log is completed historical trade data.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/time-safe event availability/)).toBeInTheDocument();
    expect(screen.getByText(/attached as a usable Mainboard item/)).toBeInTheDocument();
    expect(
      screen.getByText("This source is an external working object, not a Package Library package."),
    ).toBeInTheDocument();
  });

  it("renders the three §6.1 ⓘ panels with their final text", () => {
    renderChooser();
    expect(screen.getByText("ⓘ Add Outsource Signal")).toBeInTheDocument();
    expect(screen.getByText("ⓘ Trading Signal mi, Trade Log mu?")).toBeInTheDocument();
    expect(screen.getByText("ⓘ Unsaved External Draft")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Buradan Package Libraryye yeni bir package eklemezsiniz. Dış kaynaklı bir çalışma nesnesi başlatırsınız.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Kaydetmeden bu taslak Ready Checke, Portfolio Allocationa veya RUN/),
    ).toBeInTheDocument();
  });

  it("choosing Trading Signal navigates to the Trading Signal workbench", () => {
    renderChooser();
    fireEvent.click(screen.getByRole("link", { name: "Trading Signal" }));
    expect(screen.getByText("TS WORKBENCH PROBE")).toBeInTheDocument();
  });

  it("choosing Trade Log navigates to the Trade Log workbench", () => {
    renderChooser();
    fireEvent.click(screen.getByRole("link", { name: "Trade Log" }));
    expect(screen.getByText("TL WORKBENCH PROBE")).toBeInTheDocument();
  });

  it("performs no backend call — rendering and choosing never touch fetch (§7.1)", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    renderChooser();
    fireEvent.click(screen.getByRole("link", { name: "Trade Log" }));
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
