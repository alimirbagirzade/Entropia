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
  },
});
