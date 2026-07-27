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
      // Calibrated from a measured run: lines 83.2, statements 80.9, functions
      // 73.4, branches 70.7. Those figures are a LOWER bound — they come from a
      // run whose suite was not fully green, so a clean run measures at least
      // this much. The thresholds sit a couple of points under that floor so an
      // ordinary regression trips them without flagging normal drift. Raise them
      // once a green run gives the true numbers; never lower one to turn a red
      // run green — add the missing test instead.
      thresholds: {
        lines: 80,
        statements: 78,
        functions: 70,
        branches: 68,
      },
    },
  },
});
