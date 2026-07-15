import { defineConfig, devices } from "@playwright/test";

// Entropia V18 — F-23 real-browser E2E suite.
//
// Targets the Docker Compose stack (real API + Postgres + Redis + MinIO +
// workers), never a mocked fetch — see frontend/e2e/README.md for how to
// bring the stack up locally and in CI. Base URL / actor credentials are
// injected via env so the same suite runs unmodified in CI and on a laptop.
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:8080";

export default defineConfig({
  testDir: "./specs",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  // The suite drives one shared Docker stack (one Postgres) end to end —
  // journeys create their own uniquely-named entities, but running workers
  // in parallel would still contend for the same backend/worker capacity,
  // so we keep this deliberately serial and let CI parallelize by sharding
  // instead if it ever needs to.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  outputDir: "test-results",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
