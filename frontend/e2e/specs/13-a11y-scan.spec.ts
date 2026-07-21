// R2-14 — automated accessibility scan (axe-core) across the 22-page matrix.
//
// Tagged @a11y and excluded from plain `npm test` (see package.json): the scan
// needs the live seeded stack, and its output is an acceptance-evidence
// artifact (docs/implementation/v18_final_acceptance.md), not a per-PR gate.
//
// Policy (GAP madde 16 / R2-14): critical + serious axe violations must be
// zero or explicitly recorded as an accepted deviation in
// docs/implementation/v18_final_acceptance.md. moderate/minor are reported
// for the record but do not fail the run.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

import { ensureAdmin } from "../fixtures/auth";
import { TARGET_PAGES, VIEWPORT_HEIGHT } from "../utils/screenshotMatrix";

const REPORT_DIR = path.join(__dirname, "..", "a11y-report");

// Serious-impact rules whose findings are recorded deviations pending the
// product-owner decision (docs/implementation/v18_final_acceptance.md §A11Y).
// Both stem from the canonical v18 palette (--accent #00a9e8, --text-dim
// #888888) — changing them is a theme decision, not a code defect, so this
// slice records rather than silently "fixes" them. Any OTHER serious rule
// appearing is an unrecorded regression and fails the gate.
const ACCEPTED_SERIOUS_RULES = ["color-contrast", "link-in-text-block"];

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

    // Critical is never acceptable.
    expect(
      results.filter((r) => r.critical > 0).map((r) => r.slug),
      "critical axe violations are never acceptable",
    ).toEqual([]);

    // Serious violations are allowed ONLY for the rules recorded as accepted
    // deviations in docs/implementation/v18_final_acceptance.md (§A11Y). A new
    // serious rule id appearing anywhere fails the gate.
    const unrecorded = results.flatMap((r) =>
      r.violations
        .filter((v) => v.impact === "serious" && !ACCEPTED_SERIOUS_RULES.includes(v.id))
        .map((v) => `${r.slug}: ${v.id} (${v.nodes} nodes) — ${v.help}`),
    );
    expect(
      unrecorded,
      "new serious violations must be fixed or recorded in v18_final_acceptance.md §A11Y",
    ).toEqual([]);
  });
});
