// R2-14 — automated accessibility scan (axe-core) across the 22-page matrix.
//
// Tagged @a11y and excluded from plain `npm test` (see package.json): the scan
// needs the live seeded stack. It runs on every PR in the E2E workflow's `a11y`
// job, so it IS a per-PR gate as well as the acceptance-evidence artifact
// referenced by docs/implementation/v18_final_acceptance.md.
//
// Policy (GAP madde 16 / R2-14, tightened by the A11Y-CI ratchet slice):
//   * critical  — never acceptable, anywhere. Not baselineable.
//   * serious   — gated against a FROZEN per-page, per-rule node-count ceiling
//                 (../a11y-baseline.json). Above its ceiling => fail. A rule
//                 with no ceiling on that page has ceiling 0 => fails on node 1.
//   * moderate/minor — reported for the record, not gated.
//
// The ceiling replaces the earlier `ACCEPTED_SERIOUS_RULES` list, which exempted
// a whole rule id (`color-contrast`) on every page. That exemption recorded the
// deviation but stopped MEASURING it: a brand-new low-contrast component could
// land and the gate stayed green, because the RULE was allow-listed rather than
// the known node count. Counting nodes keeps the recorded deviation recorded and
// makes the next one fail.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

import { ensureAdmin } from "../fixtures/auth";
import { TARGET_PAGES, VIEWPORT_HEIGHT } from "../utils/screenshotMatrix";

const REPORT_DIR = path.join(__dirname, "..", "a11y-report");
const BASELINE_PATH = path.join(__dirname, "..", "a11y-baseline.json");

// The frozen ceiling of recorded serious-impact deviations, keyed page -> rule
// -> max node count. Its provenance (which CI run measured it, on which commit)
// lives in the file itself; the adjudication behind each number lives in
// docs/implementation/a11y_ci_ratchet_and_adjudication.md.
//
// D-8 (PO 22-Jul): link-in-text-block is FIXED (in-paragraph links underlined
// via `p a` in global.css) and therefore has NO ceiling anywhere — a
// reappearance fails on its first node.
//
// D-7(b) (PO 22-Jul): color-contrast is partially fixed. The residual nodes are
// what the ceilings below record. They are NOT one homogeneous "accepted theme
// deviation" — see the adjudication doc: part of them are the v18 signature
// accent surfaces D-7(b) deliberately left alone, part of them are greys D-7(b)
// intended to darken but missed. Both are frozen here; only the second class is
// scheduled for a fix.
//
// Missing file = hard failure, not an empty ceiling: a deleted or unreadable
// baseline must never silently degrade into "everything is allowed".
interface Baseline {
  provenance?: Record<string, unknown>;
  pages: Record<string, Record<string, number>>;
}
const baseline: Baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, "utf8"));
const ceilingFor = (slug: string, rule: string): number =>
  baseline.pages[slug]?.[rule] ?? 0;

interface PageResult {
  slug: string;
  path: string;
  critical: number;
  serious: number;
  moderate: number;
  minor: number;
  violations: Array<{
    id: string;
    impact: string;
    nodes: number;
    help: string;
    // Per-node detail is what makes the report actionable evidence: which
    // element failed and axe's measured reason (e.g. the contrast ratio).
    detail: Array<{ target: string; summary: string }>;
  }>;
}

test.describe("@a11y axe-core scan — 22 pages", () => {
  test.describe.configure({ mode: "serial" });
  test.setTimeout(15 * 60 * 1000);

  test("scan all pages as admin @1440", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    await ensureAdmin(page);

    const results: PageResult[] = [];
    for (const target of TARGET_PAGES) {
      await page.goto(target.path);
      // networkidle never settles (persistent SSE stream — same reason as
      // specs/09) — wait for the workspace to mount and paint instead.
      await page.locator("main").waitFor();
      await page.waitForTimeout(800);
      const axe = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      const count = (impact: string) =>
        axe.violations.filter((v) => v.impact === impact).length;
      results.push({
        slug: target.slug,
        path: target.path,
        critical: count("critical"),
        serious: count("serious"),
        moderate: count("moderate"),
        minor: count("minor"),
        violations: axe.violations.map((v) => ({
          id: v.id,
          impact: v.impact ?? "unknown",
          nodes: v.nodes.length,
          help: v.help,
          detail: v.nodes.slice(0, 12).map((n) => ({
            target: n.target.join(" "),
            summary: (n.failureSummary ?? "").replace(/\s+/g, " ").trim().slice(0, 300),
          })),
        })),
      });
    }

    fs.mkdirSync(REPORT_DIR, { recursive: true });
    fs.writeFileSync(
      path.join(REPORT_DIR, "axe-results.json"),
      JSON.stringify(results, null, 2),
    );

    const summary = results
      .map(
        (r) =>
          `${r.slug}: critical=${r.critical} serious=${r.serious} moderate=${r.moderate} minor=${r.minor}` +
          (r.violations.length
            ? ` [${r.violations.map((v) => `${v.id}(${v.impact}×${v.nodes})`).join(", ")}]`
            : ""),
      )
      .join("\n");
    fs.writeFileSync(path.join(REPORT_DIR, "axe-summary.txt"), summary + "\n");
    console.log(summary);

    // ---- ratchet ---------------------------------------------------------
    // What the run actually measured, in baseline shape, so a real number is
    // always available as an artifact — nobody has to hand-count from the
    // report to re-baseline.
    const measured: Record<string, Record<string, number>> = {};
    for (const r of results) {
      const serious: Record<string, number> = {};
      for (const v of r.violations) {
        if (v.impact === "serious") serious[v.id] = v.nodes;
      }
      measured[r.slug] = serious;
    }
    fs.writeFileSync(
      path.join(REPORT_DIR, "axe-baseline.measured.json"),
      JSON.stringify({ pages: measured }, null, 2) + "\n",
    );

    // Critical is never acceptable and is never baselineable.
    expect(
      results.filter((r) => r.critical > 0).map((r) => r.slug),
      "critical axe violations are never acceptable",
    ).toEqual([]);

    // Serious violations are allowed only up to the frozen per-page, per-rule
    // ceiling. Over the ceiling — or a rule with no ceiling on that page — is a
    // regression, whatever its rule id.
    const regressions = results.flatMap((r) =>
      r.violations
        .filter((v) => v.impact === "serious" && v.nodes > ceilingFor(r.slug, v.id))
        .map(
          (v) =>
            `${r.slug}: ${v.id} — ${v.nodes} nodes, baseline allows ` +
            `${ceilingFor(r.slug, v.id)} — ${v.help}`,
        ),
    );
    expect(
      regressions,
      "serious a11y regressions: fix them, or have the product owner adjudicate " +
        "the new ceiling in docs/implementation/a11y_ci_ratchet_and_adjudication.md " +
        "and raise it in frontend/e2e/a11y-baseline.json — never widen the ceiling " +
        "to make CI green",
    ).toEqual([]);

    // Improvements do NOT fail the run: an unrelated PR that happens to fix a
    // contrast node should not turn red for it. They are reported loudly and the
    // tightened map is written out, so re-baselining is a copy, not a re-count.
    // The honest cost of that asymmetry: the ceiling can drift LOOSE until
    // somebody commits the tightened file. This warning is the only thing
    // pushing back on that drift.
    const improvements = results.flatMap((r) =>
      Object.entries(baseline.pages[r.slug] ?? {})
        .map(([rule, allowed]) => {
          const now = measured[r.slug]?.[rule] ?? 0;
          return now < allowed ? `${r.slug}: ${rule} — ${allowed} → ${now}` : null;
        })
        .filter((line): line is string => line !== null),
    );
    if (improvements.length) {
      const tightened: Record<string, Record<string, number>> = {};
      for (const [slug, rules] of Object.entries(baseline.pages)) {
        tightened[slug] = {};
        for (const [rule, allowed] of Object.entries(rules)) {
          const now = measured[slug]?.[rule] ?? 0;
          if (now > 0) tightened[slug][rule] = Math.min(allowed, now);
        }
      }
      fs.writeFileSync(
        path.join(REPORT_DIR, "axe-baseline.tightened.json"),
        JSON.stringify({ pages: tightened }, null, 2) + "\n",
      );
      console.log(
        `\n::warning::a11y baseline is now LOOSER than reality on ${improvements.length} ` +
          `page/rule pair(s). Copy a11y-report/axe-baseline.tightened.json into ` +
          `frontend/e2e/a11y-baseline.json's "pages" to re-freeze:\n` +
          improvements.map((l) => `  ${l}`).join("\n"),
      );
    }

    const measuredTotal = Object.values(measured)
      .flatMap((rules) => Object.values(rules))
      .reduce((a, b) => a + b, 0);
    const baselineTotal = Object.values(baseline.pages)
      .flatMap((rules) => Object.values(rules))
      .reduce((a, b) => a + b, 0);
    console.log(
      `\na11y ratchet: ${measuredTotal} serious node(s) measured against a frozen ` +
        `ceiling of ${baselineTotal}.`,
    );
  });
});
