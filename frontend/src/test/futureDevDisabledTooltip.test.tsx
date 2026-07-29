import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { Menu } from "@/app/Layout";
import { MENU_BAR } from "@/app/nav";

// doc 22 §7 `futureDevDisabled.tooltip` — the exact catalog text, quoted from
// docs/spec/22_Entropia_V18_Future_Dev_Page_Documentation_v1_1.md.
const DOC22_DISABLED_TOOLTIP =
  "This capability is planned but not active in Production V1. No operational command is available.";

const futureDev = MENU_BAR.find((group) => group.label === "Future Dev")!;

function openFutureDev() {
  render(
    <MemoryRouter>
      <Menu group={futureDev} isAdmin={false} onAbout={() => {}} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Future Dev" }));
}

// doc 22 §4/§5: Live Trade is a visible menu label with NO clickable handler —
// its visibility must never read as an available execution action (FD-12).
describe("Future Dev disabled menu item (doc 22 §7 futureDevDisabled.tooltip)", () => {
  it("renders Live Trade as a non-interactive, aria-disabled placeholder", () => {
    openFutureDev();
    const liveTrade = screen.getByText("Live Trade");
    expect(liveTrade.tagName).toBe("SPAN");
    expect(liveTrade).toHaveAttribute("aria-disabled", "true");
    // No route target and no button role: the item dispatches no command.
    expect(liveTrade.closest("a")).toBeNull();
    expect(liveTrade.closest("button")).toBeNull();
  });

  it("carries the doc 22 §7 disabled tooltip verbatim", () => {
    openFutureDev();
    expect(screen.getByText("Live Trade")).toHaveAttribute("title", DOC22_DISABLED_TOOLTIP);
  });

  it("leaves every navigable Future Dev target clickable", () => {
    openFutureDev();
    // Graphic View is the one V18 clickable placeholder route (doc 22 §4).
    expect(screen.getByRole("link", { name: "Graphic View" })).toHaveAttribute(
      "href",
      "/future-dev/graphic-view",
    );
  });
});
