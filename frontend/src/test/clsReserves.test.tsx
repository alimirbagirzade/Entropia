import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import { CreatePackage } from "@/pages/CreatePackage";
import { FutureDev } from "@/pages/FutureDev";
import { Library } from "@/pages/Library";
import { stubApi } from "./helpers/apiStub";

// ADIM 151 — the logged-in CLS guards, one per route the signed-in Lighthouse
// run flagged (panel-management has its own guard in panelManagement.test.tsx).
// The Lighthouse ratchet CANNOT protect any of this: every floor was frozen
// BELOW the post-fix score (do_not_tighten forbids raising them), so reverting
// a reserve would drop CLS back to 0.059-0.096 and the gate would stay green.
// A structural assertion is the only thing that notices — the ADIM 148 lesson,
// now applied to the three other routes the signed-in run made visible.

const VIEWER_PERMISSIONS = {
  can_view: true,
  can_use: true,
  can_derive: true,
  can_create_revision: false,
  can_request_approval: false,
  can_approve_publish: false,
  can_deprecate: false,
  can_soft_delete: false,
  can_export: true,
};

const PERFORMANCE_NA = {
  net_profit: "not_applicable",
  max_drawdown: "not_applicable",
  romad: "not_applicable",
  win_rate: "not_applicable",
  trade_count: "not_applicable",
  out_of_sample: "not_applicable",
};

const INDICATOR_ROW = {
  entity_id: "pkg_1",
  package_kind: "indicator",
  name: "RSI Bundle",
  current_revision_id: "rev_11",
  revision_no: 3,
  lifecycle_state: "active",
  validation_state: "passed",
  approval_state: "approved",
  visibility_scope: "published",
  market_scope: "multi",
  timeframe_scope: "multi",
  rationale_family: { id: "fam_1", name: "Momentum" },
  output_kinds: ["directional_signal"],
  derived_from_revision_id: null,
  owner_principal_id: "u_1",
  row_version: 7,
  content_hash: "sha256:abc",
  created_at: "2026-07-01T10:00:00+00:00",
  permissions: VIEWER_PERMISSIONS,
  performance: PERFORMANCE_NA,
};

const FAMILIES_PAGE = {
  data: [{ entity_id: "fam_1", display_name: "Momentum" }],
  meta: { cursor: null, has_more: false },
};

const ACTIVE_CAP = {
  capability_key: "backtest_review",
  title: "Backtest Review",
  menu_path: "Future Dev > AI Operations > Backtest Review",
  lifecycle_state: "active",
  is_operational: true,
  ui_surface_version: "v18-placeholder",
  domain_contract_version: "v1",
  registry_version: 6,
  enabled_at: "2026-07-01T09:00:00+00:00",
  retirement_at: null,
  status_message: "Active capability — operational commands enabled.",
};

const ME_ADMIN = {
  principal_id: "hu_admin",
  principal_type: "human",
  role: "admin",
  is_admin: true,
  is_authenticated: true,
};

function renderWith(ui: React.ReactElement, path: string): QueryClient {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

describe("logged-in CLS reserves (ADIM 151)", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("reserves the Library catalog pool height while the list is in flight", async () => {
    stubApi({
      "GET /rationale-families": FAMILIES_PAGE,
      "GET /library": { data: [INDICATOR_ROW], meta: { cursor: null, has_more: false } },
    });
    renderWith(<Library />, "/packages/library");

    // First paint: the pool region reserves its measured signed-in settled
    // height so the Import card below it does not get shoved off the fold.
    const reserved = document.querySelector(".panel-card-async--library-pool");
    expect(reserved).not.toBeNull();
    expect(reserved?.textContent).toMatch(/Loading catalog/);

    // Loading-only: once settled the real pool sets the height.
    expect(await screen.findByText("RSI Bundle")).toBeInTheDocument();
    expect(document.querySelector(".panel-card-async--library-pool")).toBeNull();
  });

  it("reserves the Future Dev capability registry height while it is in flight", async () => {
    stubApi({
      "GET /capabilities": { capabilities: [ACTIVE_CAP], count: 1 },
      "GET /analysis-artifacts": {
        data: [],
        meta: { cursor: null, has_more: false, limit: 20, artifact_type: null },
      },
      "GET /me": ME_ADMIN,
    });
    renderWith(<FutureDev />, "/future-dev");

    const reserved = document.querySelector(".panel-card-async--capabilities");
    expect(reserved).not.toBeNull();
    expect(reserved?.textContent).toMatch(/Loading capability registry/);

    expect(await screen.findByText("Backtest Review")).toBeInTheDocument();
    expect(document.querySelector(".panel-card-async--capabilities")).toBeNull();
  });

  it("keeps the Create Package request strip one line tall while it is in flight", async () => {
    stubApi({
      "GET /create-package/requests": { data: [], meta: { cursor: null, has_more: false } },
      "GET /rationale-families": FAMILIES_PAGE,
      "GET /library": { data: [], meta: { cursor: null, has_more: false } },
    });
    renderWith(<CreatePackage />, "/packages/create");

    // The strip sits ABOVE the whole workspace, and its settled shape in the
    // gate's seeded world is a one-line note — so its loading state must be a
    // one-line status, NOT the ~168px spinner block that pulled the page up.
    const status = screen.getByRole("status");
    expect(status.textContent).toMatch(/Loading requests/);
    expect(status.classList.contains("cp-note")).toBe(true);
    // The spinner block must not render inside the switcher strip.
    const strip = status.closest("section");
    expect(strip?.querySelector(".state")).toBeNull();

    expect(await screen.findByText(/No requests yet/)).toBeInTheDocument();
  });

  // Source-level on purpose: jsdom never applies global.css, so the DOM
  // assertions above can only see that a class is PRESENT — a reserve whose
  // min-height quietly changed (or vanished from the stylesheet) would leave
  // every render green while the measured geometry regressed. The values are
  // measured constants (signed-in seeded settled heights, ADIM 151); anyone
  // re-measuring updates the stylesheet and this pin together, deliberately.
  it("pins the measured per-surface reserve values in global.css", async () => {
    // Read the stylesheet as TEXT, not through the bundler: vitest's css
    // pipeline turns any .css import (even `?raw`) into an empty module here —
    // measured: the first version of this pin matched against "" and was red in
    // BOTH worlds, i.e. not a control at all. vitest itself executes in Node,
    // but the src tsconfig deliberately carries no Node types, so the computed
    // specifier + narrow cast keep @types/node out of the app's type surface.
    const fs = (await import("node" + ":fs")) as {
      readFileSync: (path: string, encoding: "utf8") => string;
    };
    // Not import.meta.url: under the jsdom environment that is an http://
    // URL (measured: "The URL must be of scheme file"). vitest's cwd is
    // frontend/, the same root the `@` alias resolves from.
    const cwd = (globalThis as { process?: { cwd(): string } }).process?.cwd() ?? "";
    const css = fs.readFileSync(`${cwd}/src/styles/global.css`, "utf8");
    const reserves: Array<[string, number]> = [
      ["users", 112],
      ["actors", 56],
      ["matrix", 175],
      ["capabilities", 322],
      ["library-pool", 610],
    ];
    for (const [modifier, px] of reserves) {
      expect(css).toMatch(
        new RegExp(
          `\\.panel-card-async--${modifier}\\s*\\{\\s*min-height:\\s*${px}px;\\s*\\}`,
        ),
      );
    }
  });
});
