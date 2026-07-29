import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Node 22+ defines a native `localStorage` global that throws/returns undefined
// without --localstorage-file; vitest's jsdom setup only overrides globals absent
// from `global`, so this broken native one wins over jsdom's working shim. Disable
// it in test workers, but only when the running Node recognizes the flag (Node 20,
// still used in CI, treats it as a fatal unrecognized option).
const testExecArgv = process.allowedNodeEnvironmentFlags.has("--no-experimental-webstorage")
  ? ["--no-experimental-webstorage"]
  : [];

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    host: true,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    execArgv: testExecArgv,
    // v8 coverage instrumentation slows jsdom + Testing Library renders enough
    // that a single test can run past 2.5 s, so the 5 s default is uncomfortably
    // close. Set here rather than as a `--testTimeout` flag on the coverage
    // script alone: `npm test` and `npm run coverage` must share one timing
    // regime, and this has to stay above the 5 s `asyncUtilTimeout` configured
    // in src/test/setup.ts so a stuck query reports as a Testing Library error
    // (which dumps the DOM) instead of a bare "test timed out".
    testTimeout: 20000,
    // e2e/ is a standalone Playwright package (its own package.json, no
    // @playwright/test in this workspace's node_modules) — exclude it from
    // Vitest's default *.spec.ts discovery alongside Vitest's own defaults.
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/cypress/**",
      "**/.{idea,git,cache,output,temp}/**",
      "**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*",
      "e2e/**",
    ],
    coverage: {
      provider: "v8",
      reporter: ["text-summary", "lcov", "json-summary"],
      // Vitest skips the report entirely when any test fails (default false),
      // losing the coverage signal on exactly the runs where it helps diagnosis.
      reportOnFailure: true,
      // Measure the app, not the harness or generated mirrors: `src/test/**` is
      // the suite itself, `main.tsx` is the DOM bootstrap, `*.d.ts` are
      // declarations, and `*.generated.ts` mirrors the backend capability matrix
      // (its source of truth is tested on the backend side).
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/test/**", "src/main.tsx", "src/**/*.d.ts", "src/**/*.generated.ts"],
      // A gate, not a report: `npm run coverage` fails below these numbers.
      //
      // Calibrated from a FULLY GREEN run (61 files, 641 tests, 0 failures):
      // lines 84.67, statements 82.29, functions 75.09, branches 71.96 — recorded
      // with the per-file breakdown in docs/audit/coverage_baseline.md. These
      // replace the first set, which came from a run whose suite was not green and
      // was therefore only a lower bound (lines 83.2 / statements 80.9 /
      // functions 73.4 / branches 70.7).
      //
      // Each threshold sits ~2 points under its measured value: enough that an
      // ordinary regression trips the gate, enough headroom that the untested
      // macOS-local vs CI-Linux difference does not. Tighten by a point once CI
      // has reported its own numbers; never lower one to turn a red run green —
      // add the missing test instead.
      thresholds: {
        lines: 83,
        statements: 80,
        functions: 73,
        branches: 70,
      },
    },
  },
});
