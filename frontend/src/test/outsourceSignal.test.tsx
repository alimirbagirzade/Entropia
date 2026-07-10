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
