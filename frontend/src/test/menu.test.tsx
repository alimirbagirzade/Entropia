import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { Menu } from "@/app/Layout";
import type { MenuGroup } from "@/app/nav";

// The primary menu bar must be operable by keyboard (WCAG 2.1.1): the trigger is a
// real focusable control with disclosure semantics, ArrowDown/click opens it, and
// Escape closes it — none of which the old hover-only CSS menu provided.
function renderMenu(group: MenuGroup) {
  return render(
    <MemoryRouter>
      <Menu group={group} isAdmin={false} onAbout={() => {}} />
    </MemoryRouter>,
  );
}

const editGroup: MenuGroup = {
  label: "Edit",
  items: [{ label: "Market Data", path: "/market-data" }],
};

describe("primary menu keyboard accessibility", () => {
  it("renders a pathless group as a focusable button with disclosure semantics", () => {
    renderMenu(editGroup);
    const trigger = screen.getByRole("button", { name: "Edit" });
    expect(trigger).toHaveAttribute("aria-haspopup", "true");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("opens on click and closes on Escape", () => {
    renderMenu(editGroup);
    const trigger = screen.getByRole("button", { name: "Edit" });
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("opens with ArrowDown from the keyboard", () => {
    renderMenu(editGroup);
    const trigger = screen.getByRole("button", { name: "Edit" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("exposes a nested submenu trigger as an expandable button", () => {
    renderMenu({
      label: "Edit",
      items: [
        {
          label: "Package Library",
          items: [{ label: "Strategy Packages", path: "/packages/library?type=strategy" }],
        },
      ],
    });
    const sub = screen.getByRole("button", { name: "Package Library" });
    expect(sub).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(sub);
    expect(sub).toHaveAttribute("aria-expanded", "true");
  });
});

// R2-02 (GAP 6): an addIntent menu entry is a dispatcher button, not a route
// link — clicking it navigates to the Mainboard ("/") carrying the intent in
// router state, where the Mainboard runs its own "+ Add" handler.
describe("Mainboard add-intent dispatch (R2-02)", () => {
  function LocationProbe() {
    const location = useLocation();
    const add = (location.state as { add?: string } | null)?.add;
    return <div data-testid="probe">{`${location.pathname}|${add ?? "none"}`}</div>;
  }

  it("navigates to the Mainboard with the intent in router state", () => {
    const group: MenuGroup = {
      label: "Mainboard",
      path: "/",
      items: [{ label: "Add Strategy", addIntent: "strategy" }],
    };
    render(
      <MemoryRouter initialEntries={["/research-data"]}>
        <Menu group={group} isAdmin={false} onAbout={() => {}} />
        <Routes>
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    // The entry renders as a button (no href to /strategy anywhere).
    const item = screen.getByRole("button", { name: "Add Strategy" });
    expect(screen.queryByRole("link", { name: "Add Strategy" })).toBeNull();
    fireEvent.click(item);
    expect(screen.getByTestId("probe").textContent).toBe("/|strategy");
  });
});
