import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// Testing Library's async queries (`findBy*`, `waitFor`) run on their OWN budget
// — `asyncUtilTimeout`, default 1000 ms — which Vitest's `testTimeout` does not
// extend. Under v8 coverage instrumentation a jsdom render routinely pushes a
// single test past 2.5 s, so a query that resolves comfortably in a plain run
// can cross the 1 s ceiling and fail for reasons unrelated to the assertion —
// turning the coverage gate red without a coverage or product regression.
//
// This is a ceiling, not a delay: `findBy*` resolves the moment the element
// appears, so raising it costs a green run nothing. It is set unconditionally
// rather than only under coverage so `npm test` and `npm run coverage` share one
// timing regime — a test must not be able to pass in one mode and fail in the
// other. Kept well under the 20 s `testTimeout` in vite.config.ts so the
// Testing Library error (which dumps the DOM) always beats a bare Vitest
// timeout, whose message says nothing about what the query was looking for.
configure({ asyncUtilTimeout: 5000 });
