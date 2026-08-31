// RC §6.7 / P11-8 — Lighthouse as a RATCHET, not a threshold.
//
// Tagged @lighthouse and excluded from plain `npm test` (see package.json):
// like the axe scan it needs the live seeded Compose stack. It runs in the E2E
// workflow's `lighthouse` job on every PR and push to main.
//
// WHY A RATCHET AND NOT A SCORE FLOOR OF OUR CHOOSING
// ---------------------------------------------------
// An absolute target ("performance >= 90") is a number nobody measured. On a
// 2-vCPU shared runner it either sits so low it can never fail or so high it
// fails on weather, and a gate that fails on weather gets switched off inside a
// month — this repository already wrote that reasoning down for the load driver
// (docs/performance/README.md section 1) and applied the same answer to axe
// (frontend/e2e/a11y-baseline.json). So: today's measured score is frozen as
// the FLOOR and may only ever rise. No margin is subtracted; a run below the
// frozen floor is a regression and fails.
//
// TWO AUTHORITY BOUNDARIES THIS FILE MUST NOT CROSS
// -------------------------------------------------
//  1. ACCESSIBILITY. axe-core (specs/13-a11y-scan.spec.ts + a11y-baseline.json)
//     is the shipped a11y authority, with per-page per-rule node ceilings and a
//     written adjudication record. A second, coarser a11y number would create a
//     rival authority that can disagree with it. The category is therefore NOT
//     REQUESTED AT ALL — see CATEGORIES below. Nothing produced by this file is
//     evidence for A-08: the screen-reader audit ledger
//     (docs/audit/a11y_screen_reader_audit_results.md) records what a human
//     heard, and no DOM scanner — axe or Lighthouse — can write to its 1 or 2.
//  2. PERFORMANCE. scripts/loadgen.py measures the SERVER: per-endpoint HTTP
//     p95 against a real stack, control-normalised, gated nightly (P10-7). This
//     file measures the BROWSER: how the SPA shell paints and becomes
//     interactive on a route. docs/performance/README.md section 8 names
//     frontend rendering as explicitly out of the load driver's scope; this is
//     the gate that fills that declared gap. They answer different questions
//     and neither is allowed to be cited for the other's.
//
// WHAT THIS GATE CANNOT SEE (honest boundary, mirrored into the report)
// ---------------------------------------------------------------------
//  * The SPA holds a persistent SSE stream, so Lighthouse's network-quiet
//    condition can never fire — the same reason specs/09 and specs/13 cannot
//    use `networkidle`. The trace is therefore cut at MAX_WAIT_FOR_LOAD_MS. FCP
//    and LCP land long before that cut; anything a route does after it is not
//    measured here.
//  * Simulated throttling models the network from the trace. It does not
//    reproduce a real slow device, and the score is only comparable inside its
//    own runner class — exactly the constraint docs/performance/README.md
//    section 2 records for the load baseline.

import { chromium, test, expect, type Browser, type Page } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

import { ensureAdmin } from "../fixtures/auth";
import { TARGET_PAGES, VIEWPORT_HEIGHT } from "../utils/screenshotMatrix";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const REPORT_DIR = path.join(__dirname, "..", "lighthouse-report");
const BASELINE_PATH = path.join(__dirname, "..", "lighthouse-baseline.json");

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:8080";

// Chosen, not defaulted: Lighthouse needs the DevTools HTTP endpoint (a port),
// which Playwright does not expose from `browser.wsEndpoint()`. The browser is
// launched with an explicit debugging port and both tools drive the same
// profile, so the localStorage session token written by `ensureAdmin` is still
// there when Lighthouse opens its own tab (`disableStorageReset` below).
const DEBUG_PORT = Number(process.env.LH_DEBUG_PORT ?? 9222);

// accessibility is deliberately absent — see the authority note in the header.
const CATEGORIES = ["performance", "best-practices", "seo"] as const;
type Category = (typeof CATEGORIES)[number];

// Odd on purpose: the reported score per route is the MEDIAN of the repeats, so
// a single unlucky pass cannot move it. Raising this buys stability at a linear
// cost in wall time; lowering it below 3 removes the median entirely.
const REPEATS = Number(process.env.LH_REPEATS ?? 3);

const MAX_WAIT_FOR_LOAD_MS = 20_000;

// GH #677 asked whoever picked up `errors-in-console` to "read the actual
// console output before assuming it is cosmetic" — and the shipped artefact
// made that impossible: it recorded the audit's NAME and dropped its CONTENTS.
// Two sessions were spent trying to reproduce the console locally instead,
// which is the cost of naming a defect without carrying its evidence.
// Bounded on purpose: an audit like `unused-javascript` can list every asset,
// and an artefact nobody opens because it is 40 MB is the same failure again.
const MAX_EVIDENCE_ITEMS = 5;
const MAX_EVIDENCE_CHARS = 300;

/**
 * Render one `audit.details.items` entry as a single line. Deliberately generic
 * rather than shaped for `errors-in-console`: the next deduction to need
 * diagnosis will be a different audit, and a per-audit renderer would leave it
 * as blind as this one was. `description` and `url`/`sourceLocation.url` are
 * Lighthouse's own conventional keys, so they lead when present.
 */
const renderEvidence = (item: Record<string, unknown>): string => {
  const primitive = (v: unknown): string | null => {
    if (typeof v === "string") return v;
    if (typeof v === "number" || typeof v === "boolean") return String(v);
    return null;
  };
  const loc = item.sourceLocation as Record<string, unknown> | undefined;
  const lead = [
    primitive(item.description),
    primitive(item.url) ?? (loc ? primitive(loc.url) : null),
  ].filter((x): x is string => Boolean(x));
  const rest = lead.length
    ? []
    : Object.entries(item)
        .map(([k, v]) => {
          const p = primitive(v);
          return p ? `${k}=${p}` : null;
        })
        .filter((x): x is string => Boolean(x));
  const line = [...lead, ...rest].join(" :: ") || JSON.stringify(item);
  return line.length > MAX_EVIDENCE_CHARS ? `${line.slice(0, MAX_EVIDENCE_CHARS)}…` : line;
};

// Reported beside the scores but NOT gated. A category score is a bounded,
// quantised number and survives being ratcheted; a raw millisecond on a shared
// runner is the weather docs/performance/README.md section 1 refuses to gate on.
// They are here so a failing score can be diagnosed from the same artefact.
const METRIC_IDS = [
  "first-contentful-paint",
  "largest-contentful-paint",
  "total-blocking-time",
  "cumulative-layout-shift",
  "speed-index",
] as const;

interface Baseline {
  // A committed baseline with `armed: false` is the bootstrap state: the run
  // measures, writes the measured map and warns loudly, but does not gate.
  // A MISSING file is a hard failure — a deleted baseline must never degrade
  // into "every score is allowed".
  armed: boolean;
  provenance?: Record<string, unknown>;
  policy?: Record<string, unknown>;
  floors: Record<string, Partial<Record<Category, number>>>;
}

if (!fs.existsSync(BASELINE_PATH)) {
  throw new Error(
    `${BASELINE_PATH} is missing. The Lighthouse ratchet reads its floors from ` +
      "that file; without it the gate would pass everything. Restore it from git.",
  );
}
const baseline: Baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, "utf8"));

const floorFor = (slug: string, category: Category): number | null =>
  baseline.floors[slug]?.[category] ?? null;

interface RouteScores {
  slug: string;
  path: string;
  /** median across the repeats, 0-100 */
  median: Record<Category, number>;
  /** worst repeat, 0-100 — the input to any future noise decision */
  min: Record<Category, number>;
  max: Record<Category, number>;
  /** median of the headline metrics, milliseconds (cls is unitless) */
  metrics: Record<string, number | null>;
  /**
   * Which audits actually cost the route its missing points, from the last pass.
   * Without this a red gate says "seo dropped to 78" and the author has to
   * re-run Lighthouse by hand to find out why — and a *green* run says nothing
   * about the deductions already frozen into the floor, which is how a known
   * defect turns into an invisible one.
   */
  deductions: Record<
    Category,
    Array<{ id: string; title: string; weight: number; evidence: string[] }>
  >;
}

const median = (xs: number[]): number => {
  const s = [...xs].sort((a, b) => a - b);
  return s[(s.length - 1) >> 1];
};

test.describe("@lighthouse Lighthouse ratchet — every audited route", () => {
  test.describe.configure({ mode: "serial" });
  test.setTimeout(90 * 60 * 1000);

  test("score every route and hold the frozen floor", async () => {
    // Dynamic import: `lighthouse` is ESM-only, and importing it dynamically
    // keeps this spec loadable under either module emit.
    const { default: lighthouse } = await import("lighthouse");

    const browser: Browser = await chromium.launch({
      args: [`--remote-debugging-port=${DEBUG_PORT}`],
    });
    const context = await browser.newContext({
      baseURL: BASE_URL,
      viewport: { width: 1440, height: VIEWPORT_HEIGHT },
    });
    const page: Page = await context.newPage();

    const lhConfig = {
      extends: "lighthouse:default",
      settings: {
        onlyCategories: [...CATEGORIES],
        formFactor: "desktop",
        screenEmulation: {
          mobile: false,
          width: 1440,
          height: VIEWPORT_HEIGHT,
          deviceScaleFactor: 1,
          disabled: false,
        },
        // cpuSlowdownMultiplier 1: the runner is already a 2-vCPU box. Adding
        // Lighthouse's default 4x mobile slowdown on top would model a device
        // nobody has and widen the very noise this gate has to survive.
        throttling: {
          rttMs: 40,
          throughputKbps: 10 * 1024,
          cpuSlowdownMultiplier: 1,
          requestLatencyMs: 0,
          downloadThroughputKbps: 0,
          uploadThroughputKbps: 0,
        },
        throttlingMethod: "simulate",
        // Keep the localStorage session token the login above wrote.
        disableStorageReset: true,
        maxWaitForLoad: MAX_WAIT_FOR_LOAD_MS,
      },
    };

    const runOnce = async (routePath: string) => {
      const url = new URL(routePath, BASE_URL).toString();
      const result = await lighthouse(
        url,
        { port: DEBUG_PORT, output: "json", logLevel: "error" },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        lhConfig as any,
      );
      if (!result?.lhr) throw new Error(`Lighthouse returned no result for ${url}`);
      const lhr = result.lhr;
      const scores = {} as Record<Category, number>;
      for (const c of CATEGORIES) {
        const raw = lhr.categories[c]?.score;
        if (raw === null || raw === undefined) {
          throw new Error(
            `Lighthouse produced no ${c} score for ${url}. A null score is an ` +
              "unmeasured run, never a pass.",
          );
        }
        scores[c] = Math.round(raw * 100);
      }
      const metrics: Record<string, number | null> = {};
      for (const id of METRIC_IDS) {
        metrics[id] = lhr.audits[id]?.numericValue ?? null;
      }
      // A binary-failed audit that carries weight is what actually moved the
      // score. `score === null` means "not applicable / informative" and is not
      // a deduction; filtering it out keeps the list to things somebody could
      // act on.
      const deductions = {} as RouteScores["deductions"];
      for (const c of CATEGORIES) {
        deductions[c] = (lhr.categories[c]?.auditRefs ?? [])
          .map((ref) => ({ ref, audit: lhr.audits[ref.id] }))
          .filter(({ ref, audit }) => (ref.weight ?? 0) > 0 && audit && audit.score !== null && audit.score < 1)
          .map(({ ref, audit }) => {
            const items = (audit?.details as { items?: unknown[] } | undefined)?.items ?? [];
            return {
              id: ref.id,
              title: audit?.title ?? ref.id,
              weight: ref.weight ?? 0,
              // Empty is a real answer, not a gap: plenty of audits fail with no
              // item list at all (`is-crawlable` is one), and pretending
              // otherwise would send the next reader looking for missing data.
              evidence: items
                .slice(0, MAX_EVIDENCE_ITEMS)
                .map((it) => renderEvidence(it as Record<string, unknown>)),
            };
          });
      }
      return { scores, metrics, deductions };
    };

    const results: RouteScores[] = [];
    try {
      await ensureAdmin(page);

      // Warm-up, discarded: the first Lighthouse run of a process pays for V8
      // warm-up, the browser's first paint of the bundle and a cold HTTP cache.
      // Folding that into a route's score would make whichever route happens to
      // be first look permanently worse than the others.
      await page.goto(TARGET_PAGES[0].path);
      await runOnce(TARGET_PAGES[0].path);

      for (const target of TARGET_PAGES) {
        const passes = [];
        for (let i = 0; i < REPEATS; i += 1) {
          passes.push(await runOnce(target.path));
        }
        const med = {} as Record<Category, number>;
        const lo = {} as Record<Category, number>;
        const hi = {} as Record<Category, number>;
        for (const c of CATEGORIES) {
          const xs = passes.map((p) => p.scores[c]);
          med[c] = median(xs);
          lo[c] = Math.min(...xs);
          hi[c] = Math.max(...xs);
        }
        const metrics: Record<string, number | null> = {};
        for (const key of Object.keys(passes[0].metrics)) {
          const xs = passes
            .map((p) => p.metrics[key])
            .filter((v): v is number => typeof v === "number");
          metrics[key] = xs.length ? Math.round(median(xs) * 1000) / 1000 : null;
        }
        results.push({
          slug: target.slug,
          path: target.path,
          median: med,
          min: lo,
          max: hi,
          metrics,
          // From the last pass: the deductions are identical across repeats
          // whenever the score is (measured spread was 0 points on 2026-08-12),
          // and a per-pass union would only add noise to the artefact.
          deductions: passes[passes.length - 1].deductions,
        });
        console.log(
          `${target.slug.padEnd(20)} ` +
            CATEGORIES.map((c) => `${c}=${med[c]} (${lo[c]}-${hi[c]})`).join("  "),
        );
      }
    } finally {
      await context.close();
      await browser.close();
    }

    // ---- artefacts -------------------------------------------------------
    fs.mkdirSync(REPORT_DIR, { recursive: true });
    fs.writeFileSync(
      path.join(REPORT_DIR, "lighthouse-results.json"),
      JSON.stringify(
        {
          conditions: {
            base_url: BASE_URL,
            repeats: REPEATS,
            categories: CATEGORIES,
            form_factor: "desktop",
            viewport: `1440x${VIEWPORT_HEIGHT}`,
            throttling: "simulate, cpuSlowdownMultiplier 1",
            max_wait_for_load_ms: MAX_WAIT_FOR_LOAD_MS,
            accessibility_category: "NOT RUN — axe-core is the shipped authority",
          },
          routes: results,
        },
        null,
        2,
      ) + "\n",
    );

    const summary = results
      .map(
        (r) =>
          `${r.slug}: ` +
          CATEGORIES.map((c) => `${c}=${r.median[c]}[${r.min[c]}-${r.max[c]}]`).join(" "),
      )
      .join("\n");
    fs.writeFileSync(path.join(REPORT_DIR, "lighthouse-summary.txt"), summary + "\n");

    // Baseline-shaped measurement, so re-freezing is a copy and never a re-count.
    const measured: Record<string, Record<string, number>> = {};
    for (const r of results) {
      measured[r.slug] = Object.fromEntries(CATEGORIES.map((c) => [c, r.median[c]]));
    }
    fs.writeFileSync(
      path.join(REPORT_DIR, "lighthouse-baseline.measured.json"),
      JSON.stringify({ floors: measured }, null, 2) + "\n",
    );

    // The observed within-run spread, which is the only honest input to a future
    // decision about whether a category can be gated at all on this runner class.
    const spread = CATEGORIES.map((c) => {
      const worst = results.reduce((acc, r) => Math.max(acc, r.max[c] - r.min[c]), 0);
      return `${c}: worst repeat spread ${worst} point(s)`;
    }).join("\n  ");
    console.log(`\nlighthouse repeat spread over ${REPEATS} passes:\n  ${spread}`);

    // ---- gate ------------------------------------------------------------
    if (!baseline.armed) {
      console.log(
        "\n::warning::the Lighthouse ratchet is NOT ARMED (lighthouse-baseline.json " +
          '`"armed": false`). This run measured but gated nothing. Copy ' +
          "lighthouse-report/lighthouse-baseline.measured.json into the baseline's " +
          '`floors` and set `"armed": true` to freeze it.',
      );
      // Not a silent pass: an unarmed gate must be visible in the run's own
      // assertions, so the test still records what state it ran in.
      expect(
        Object.keys(baseline.floors),
        "unarmed baseline must carry no floors — a half-filled floors map would " +
          "read as a gate that is on",
      ).toEqual([]);
      return;
    }

    // A route in the matrix with no frozen floor is a HOLE, not a pass: the
    // matrix is the single source of the route list, so a new page must be
    // baselined rather than silently skipped.
    const unbaselined = results
      .filter((r) => CATEGORIES.some((c) => floorFor(r.slug, c) === null))
      .map((r) => r.slug);
    expect(
      unbaselined,
      "these routes are in screenshotMatrix.ts::TARGET_PAGES but carry no " +
        "Lighthouse floor. Add the measured score to " +
        "frontend/e2e/lighthouse-baseline.json rather than leaving the route ungated",
    ).toEqual([]);

    const regressions = results.flatMap((r) =>
      CATEGORIES.flatMap((c) => {
        const floor = floorFor(r.slug, c);
        if (floor === null || r.median[c] >= floor) return [];
        return [
          `${r.slug}: ${c} — median ${r.median[c]} over ${REPEATS} passes ` +
            `(range ${r.min[c]}-${r.max[c]}), frozen floor ${floor}`,
        ];
      }),
    );
    expect(
      regressions,
      "Lighthouse score regressions. Fix the cause, or — if the drop is a " +
        "deliberate, adjudicated trade-off — lower the floor in " +
        "frontend/e2e/lighthouse-baseline.json WITH a written reason. Never lower " +
        "a floor to make CI green",
    ).toEqual([]);

    // Improvements never fail the run (an unrelated PR that happens to speed a
    // page up must not turn red), but they are printed and the tightened map is
    // written out — the same asymmetry, and the same drift cost, as the axe
    // ratchet: the floor can sit LOOSER than reality until somebody commits the
    // tightened file, and this warning is the only thing pushing back.
    const improvements = results.flatMap((r) =>
      CATEGORIES.flatMap((c) => {
        const floor = floorFor(r.slug, c);
        return floor !== null && r.median[c] > floor
          ? [`${r.slug}: ${c} — ${floor} → ${r.median[c]}`]
          : [];
      }),
    );
    if (improvements.length) {
      const tightened: Record<string, Record<string, number>> = {};
      for (const r of results) {
        tightened[r.slug] = Object.fromEntries(
          CATEGORIES.map((c) => [c, Math.max(floorFor(r.slug, c) ?? 0, r.median[c])]),
        );
      }
      fs.writeFileSync(
        path.join(REPORT_DIR, "lighthouse-baseline.tightened.json"),
        JSON.stringify({ floors: tightened }, null, 2) + "\n",
      );
      console.log(
        `\n::warning::the Lighthouse floor is now LOWER than reality on ` +
          `${improvements.length} route/category pair(s). Copy ` +
          `lighthouse-report/lighthouse-baseline.tightened.json into ` +
          `frontend/e2e/lighthouse-baseline.json's "floors" to re-freeze:\n` +
          improvements.map((l) => `  ${l}`).join("\n"),
      );
    }

    console.log(
      `\nlighthouse ratchet: ${results.length} route(s) x ${CATEGORIES.length} ` +
        `categor(ies) held against a frozen floor.`,
    );
  });
});
