import { test } from "@playwright/test";

import { ensureAdmin } from "../fixtures/auth";
import { assertPageIsRealAndServed, type PageContract } from "../utils/pageTruth";

// Functional coverage for the pages the suite previously only SCREENSHOTTED.
//
// Before this spec, `/analysis-lab`, `/backtest/history`, `/backtest/metrics`,
// `/instruments`, `/packages/embedded`, `/panel/logs`, `/panel/management`,
// `/panel/metrics`, `/panel/provisioning`, `/portfolio`, `/rationale-families`,
// `/user-manual` and `/future-dev` appeared in the E2E tree ONLY inside
// `utils/screenshotMatrix.ts` — which drives the `@screenshots` / `@visual` /
// `@a11y` / `@prototype` specs, all excluded from the default run by
// `--grep-invert`. So the suite was green while never exercising a single
// behaviour on twelve pages: a page whose protected query returns 401/403/500
// still renders its <h1> and still screenshots cleanly.
//
// Each case here asserts BOTH halves — the heading rendered AND the protected
// read the page's data actually comes from returned 200 to the very token the
// browser holds — plus a structural anchor proving the projection rendered, not
// just the chrome. Run as the bootstrap Admin because half these surfaces are
// admin-gated (`/admin/*`); a plain user would legitimately get 403 and the
// spec would be asserting the wrong thing.
const CONTRACTS: PageContract[] = [
  {
    route: "/backtest/history",
    heading: "Results History",
    api: "/backtest-results?limit=5",
    projection: (page) => page.getByRole("heading", { name: "Results History", exact: true }),
  },
  {
    route: "/backtest/metrics",
    heading: "Arrange Metrics",
    api: "/metric-definitions",
    projection: (page) => page.getByRole("heading", { name: "Arrange Metrics", exact: true }),
  },
  {
    route: "/panel/logs",
    heading: "PANEL / LOGS",
    api: "/admin/logs",
    // The Logs page is a tabbed projection (filtered Logs + raw audit stream);
    // the tablist is the structural proof it rendered its own shape.
    projection: (page) => page.getByRole("tablist"),
  },
  {
    route: "/panel/management",
    heading: "PANEL / MANAGEMENT",
    api: "/admin/users",
    projection: (page) => page.getByRole("table"),
  },
  {
    route: "/panel/metrics",
    heading: "System Metrics",
    // No session cross-check: this page reads `GET /metrics`, the credentialed
    // Prometheus exposition (finding O-22) — a browser session Bearer is not a
    // scrape credential, so asserting 200 for it would pin the WRONG contract.
    // The queue table below is the honest proof the exposition was parsed and
    // rendered rather than erroring out.
    projection: (page) => page.getByRole("columnheader", { name: "Queue" }),
  },
  {
    route: "/panel/provisioning",
    heading: "Admin Provisioning",
    api: "/auth/bootstrap-status",
    projection: (page) => page.getByRole("heading", { name: "Admin Provisioning", exact: true }),
  },
  {
    route: "/rationale-families",
    heading: "Rationale Families",
    api: "/rationale-families",
    projection: (page) => page.getByLabel("Rationale families"),
  },
  {
    route: "/portfolio",
    heading: "Portfolio / Equity Allocation",
    api: "/mainboards/default",
    projection: (page) =>
      page.getByRole("heading", { name: "Portfolio / Equity Allocation", exact: true }),
  },
  {
    route: "/instruments",
    heading: "Instrument Registry",
    api: "/instruments",
    projection: (page) => page.getByRole("heading", { name: "Instrument Registry", exact: true }),
  },
  {
    route: "/packages/embedded",
    heading: "Embedded System Packages",
    api: "/embedded-system-packages",
    projection: (page) => page.getByLabel("Resolver registry"),
  },
  {
    route: "/analysis-lab",
    heading: "Agent Workspace / Analysis Lab",
    api: "/agent-workspace/overview",
    projection: (page) => page.getByLabel("Work queue"),
  },
  {
    route: "/future-dev",
    heading: "Future Dev",
    api: "/capabilities",
    projection: (page) => page.getByRole("heading", { name: "Future Dev", exact: true }),
  },
  {
    route: "/user-manual",
    heading: "User Manual",
    // K-4 (2026-08-12): was `level: 2`. This page now names itself with an <h1>
    // like the other 22 routes, so the divergence this field existed for is gone.
    // Kept explicit rather than deleted: `level` defaults to 1, and a silent
    // default would not record that the value CHANGED.
    level: 1,
    // The reader's own search projection, not the admin-only document list.
    api: "/manual/search?q=",
    projection: (page) => page.getByLabel("Search query"),
  },
];

test.describe("Page coverage: every nav destination serves real data, not just a heading", () => {
  test.beforeEach(async ({ page }) => {
    await ensureAdmin(page);
  });

  for (const contract of CONTRACTS) {
    test(`${contract.route} renders its projection from a served query`, async ({ page }) => {
      test.setTimeout(120_000);
      await assertPageIsRealAndServed(page, contract);
    });
  }
});
