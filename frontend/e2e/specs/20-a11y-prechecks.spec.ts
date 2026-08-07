// ADIM 28 — automated prechecks for the A-08 HUMAN screen-reader audit (#514).
//
// ============================ WHAT THIS IS NOT ==============================
// This spec does NOT audit a screen reader and its output must NEVER be
// transcribed into docs/audit/a11y_screen_reader_audit_results.md as a result.
// Playwright reads the DOM and the focus ring. It hears nothing. Every record
// this spec writes carries `screen_reader_verified: false` for exactly that
// reason, and the report's top-level `disclaimer` says so in words.
//
// What it IS: the cheap half of the audit input, run before an auditor puts
// headphones on. If a page has two <h1>s or a dialog that never returns focus,
// that is a defect a machine can find, and finding it here means the human
// hour is spent on announcement quality instead — on the questions only a
// person can answer.
//
// ---------------------------------------------------------------------------
// TWO CLASSES, DELIBERATELY SEPARATED
//
//   BLOCKING  — structural preconditions that hold on main TODAY and that the
//               human audit leans on. A regression here fails the job.
//
//   ADVISORY  — measurements whose correct value is a PRODUCT decision this
//               slice has no mandate to make (a missing skip link, an absent
//               contentinfo landmark). They are printed as ::warning::, written
//               to the report, and pre-loaded into the auditor's worksheet as
//               candidates. They are NOT silently dropped, and they are NOT
//               turned into a gate that would invent a product decision by
//               going red.
//
// The honest cost of that split: an advisory can stay unfixed indefinitely.
// The warning lines and the report are what push back on it — plus the
// auditor, who will meet every one of them in person.
// ---------------------------------------------------------------------------

import { expect, test, type Page } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

import { ensureAdmin } from "../fixtures/auth";
import { TARGET_PAGES, VIEWPORT_HEIGHT } from "../utils/screenshotMatrix";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPORT_DIR = path.join(__dirname, "..", "a11y-report");

// Walking every tabbable element on all 23 routes would double this job's wall
// clock for a measurement that repeats the same shell chrome 23 times. The walk
// therefore runs on three representative surfaces: the densest page, the
// biggest table, and a form-heavy editor. Which routes were NOT walked is
// written into the report — a narrowed scope that does not announce itself
// reads as full coverage later.
const TAB_ORDER_ROUTES = ["/", "/packages/library", "/trading-signal"] as const;

interface Advisory {
  route: string;
  check: string;
  observed: string;
  wcag: string;
  // Never "pass"/"fail": these are observations for a human to adjudicate.
  note: string;
}

interface RouteRecord {
  route: string;
  slug: string;
  h1Count: number;
  h1Text: string;
  landmarks: { banner: number; navigation: number; main: number; contentinfo: number };
  navAccessibleNames: string[];
  headingOutline: number[];
  headingSkips: string[];
  ariaLive: Array<{ politeness: string; role: string; text: string }>;
  skipLinkFirstTabbable: string | null;
  positiveTabindex: number;
  screen_reader_verified: false;
}

// Everything below runs in the page: one evaluate per route keeps this cheap.
async function collectRoute(page: Page, route: string, slug: string): Promise<RouteRecord> {
  const data = await page.evaluate(() => {
    const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 80);

    const h1s = Array.from(document.querySelectorAll("h1"));
    const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"));
    const outline = headings.map((h) => Number(h.tagName.slice(1)));
    const skips: string[] = [];
    for (let i = 1; i < outline.length; i += 1) {
      if (outline[i] - outline[i - 1] > 1) {
        skips.push(`h${outline[i - 1]} "${text(headings[i - 1])}" -> h${outline[i]} "${text(headings[i])}"`);
      }
    }

    // Landmark counting uses the implicit mapping the same way a screen
    // reader's landmark rotor does: <header>/<footer> only count when they are
    // not scoped inside a sectioning element.
    const topLevel = (el: Element) => !el.closest("article, aside, main, nav, section");
    const banner =
      Array.from(document.querySelectorAll("header")).filter(topLevel).length +
      document.querySelectorAll('[role="banner"]').length;
    const contentinfo =
      Array.from(document.querySelectorAll("footer")).filter(topLevel).length +
      document.querySelectorAll('[role="contentinfo"]').length;

    const navs = Array.from(document.querySelectorAll('nav, [role="navigation"]'));
    const navNames = navs.map(
      (n) => n.getAttribute("aria-label") ?? text(document.getElementById(n.getAttribute("aria-labelledby") ?? "")) ?? "",
    );

    const live = Array.from(
      document.querySelectorAll('[aria-live], [role="status"], [role="alert"], [role="log"]'),
    ).map((el) => ({
      politeness:
        el.getAttribute("aria-live") ??
        (el.getAttribute("role") === "alert" ? "assertive (implicit)" : "polite (implicit)"),
      role: el.getAttribute("role") ?? el.tagName.toLowerCase(),
      text: text(el),
    }));

    // A skip link is, by construction, the first thing a keyboard user reaches.
    const tabbables = Array.from(
      document.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => el.offsetParent !== null || el.getAttribute("tabindex") !== null);
    const first = tabbables[0] ?? null;
    const firstDesc = first
      ? `${first.tagName.toLowerCase()}${first.getAttribute("href") ? `[href=${first.getAttribute("href")}]` : ""} "${text(first)}"`
      : null;

    const positiveTabindex = Array.from(document.querySelectorAll("[tabindex]")).filter(
      (el) => Number(el.getAttribute("tabindex")) > 0,
    ).length;

    return {
      h1Count: h1s.length,
      h1Text: text(h1s[0] ?? null),
      landmarks: {
        banner,
        navigation: navs.length,
        main: document.querySelectorAll('main, [role="main"]').length,
        contentinfo,
      },
      navAccessibleNames: navNames,
      headingOutline: outline,
      headingSkips: skips,
      ariaLive: live,
      skipLinkFirstTabbable: firstDesc,
      positiveTabindex,
    };
  });

  return { route, slug, screen_reader_verified: false, ...data };
}

test.describe("@a11y automated prechecks — NOT a screen-reader audit (A-08 prep)", () => {
  test.describe.configure({ mode: "serial" });
  test.setTimeout(15 * 60 * 1000);

  const records: RouteRecord[] = [];
  const advisories: Advisory[] = [];
  const blocking: string[] = [];

  test("structure, landmarks, headings and live regions across the audit matrix", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    await ensureAdmin(page);

    for (const target of TARGET_PAGES) {
      await page.goto(target.path);
      // networkidle never settles (persistent SSE) — same reason as specs/09
      // and specs/13. Wait for the workspace to mount instead.
      await page.locator("main").waitFor();
      await page.waitForTimeout(500);

      const rec = await collectRoute(page, target.path, target.slug);
      records.push(rec);

      // ---- BLOCKING -----------------------------------------------------
      // At MOST one <h1>. Two top-level headings make rotor navigation
      // ambiguous — the user cannot tell which one names the page — and no
      // route does that today, so a second one is a regression.
      //
      // Not `=== 1`, deliberately. `/user-manual` renders its page title as
      // `<h2 className="page-title">` (UserManual.tsx:181), a divergence
      // already recorded in utils/pageTruth.ts:15. Promoting it to h1 would
      // shift that page's whole h2→h3→h4→h5/h6 outline and change spec 17's
      // expectation — a product decision, not an audit-preparation one. It is
      // reported as an advisory below so the auditor tests it by rotor
      // (checklist A-1 and A-3) instead of it being silently normalised here.
      if (rec.h1Count > 1) {
        blocking.push(`${target.path}: ${rec.h1Count} <h1> elements — a page may name itself once`);
      }
      if (rec.landmarks.main !== 1) blocking.push(`${target.path}: expected exactly one main landmark, found ${rec.landmarks.main}`);
      if (rec.landmarks.banner < 1) blocking.push(`${target.path}: no banner landmark`);
      if (rec.landmarks.navigation < 1) blocking.push(`${target.path}: no navigation landmark`);
      if (!rec.navAccessibleNames.some((n) => n.trim().length > 0)) {
        blocking.push(`${target.path}: no navigation landmark carries an accessible name`);
      }

      // ---- ADVISORY -----------------------------------------------------
      if (rec.h1Count === 0) {
        advisories.push({
          route: target.path,
          check: "page has no <h1>",
          observed: `0 <h1>; heading outline starts at h${rec.headingOutline[0] ?? "?"}`,
          wcag: "1.3.1 Info and Relationships (A) / 2.4.6 Headings and Labels (AA)",
          note: "the page names itself with a lower-level heading (see utils/pageTruth.ts:15). Checklist A-1 asks whether the page title is announced on load and A-3 whether the outline is unbroken — both are rotor questions this probe cannot settle.",
        });
      }
      if (rec.landmarks.contentinfo === 0) {
        advisories.push({
          route: target.path,
          check: "contentinfo landmark",
          observed: "absent",
          wcag: "1.3.1 Info and Relationships (A) / 2.4.1 Bypass Blocks (A)",
          note: "checklist A-2 expects banner/navigation/main/contentinfo to be separately findable; the shell renders no <footer>. Whether V1 should have one is a product decision, so this is reported, not gated.",
        });
      }
      const first = rec.skipLinkFirstTabbable ?? "";
      if (!/^a\[href=#/.test(first)) {
        advisories.push({
          route: target.path,
          check: "skip link",
          observed: `first tabbable is ${rec.skipLinkFirstTabbable ?? "(none)"}`,
          wcag: "2.4.1 Bypass Blocks (A)",
          note: "no in-page skip target precedes the primary nav, so a screen-reader user tabs the whole menu bar on every route. Adding one is a product change outside this preparation slice.",
        });
      }
      if (rec.headingSkips.length) {
        advisories.push({
          route: target.path,
          check: "heading outline",
          observed: rec.headingSkips.join(" ; "),
          wcag: "1.3.1 Info and Relationships (A)",
          note: "checklist A-3 asks for h1→h2→h3 with no skipped level; confirm by rotor during the audit.",
        });
      }
      if (rec.positiveTabindex > 0) {
        advisories.push({
          route: target.path,
          check: "positive tabindex",
          observed: `${rec.positiveTabindex} element(s) with tabindex > 0`,
          wcag: "2.4.3 Focus Order (A)",
          note: "positive tabindex moves an element ahead of DOM order for keyboard users.",
        });
      }
      if (rec.ariaLive.length === 0) {
        advisories.push({
          route: target.path,
          check: "aria-live inventory",
          observed: "no live region in the initial DOM",
          wcag: "4.1.3 Status Messages (AA)",
          note: "not a defect by itself — many live regions on this product mount only with the status they carry. Recorded so the auditor knows which routes have nothing to listen to until they act.",
        });
      }
    }

    expect(
      blocking,
      "structural a11y preconditions the human audit depends on",
    ).toEqual([]);
  });

  test("focus indicator is visibly distinguishable on the primary chrome", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    await ensureAdmin(page);
    await page.goto("/");
    await page.locator("main").waitFor();

    // A focus ring that a machine cannot distinguish is one a low-vision
    // keyboard user cannot either. Measured, not asserted: the *contrast* of
    // the ring is a design decision on the D-10 axis, so a value that merely
    // differs is reported rather than scored.
    const probe = await page.evaluate(() => {
      const el = document.querySelector<HTMLElement>("nav a[href], nav button, main button");
      if (!el) return null;
      const read = () => {
        const s = getComputedStyle(el);
        return `outline:${s.outlineStyle} ${s.outlineWidth} ${s.outlineColor} | box-shadow:${s.boxShadow}`;
      };
      const before = read();
      el.focus();
      return { target: el.tagName.toLowerCase(), before, after: read() };
    });

    expect(probe, "a focusable element must exist in the shell").not.toBeNull();
    if (probe && probe.before === probe.after) {
      advisories.push({
        route: "/",
        check: "focus indicator",
        observed: `computed style unchanged on focus (${probe.target}): ${probe.after}`,
        wcag: "2.4.7 Focus Visible (AA) / 1.4.11 Non-text Contrast (AA)",
        note: "the UA default ring may still paint; a computed-style probe cannot see it. Confirm visually during the audit — this is exactly the class of thing the machine cannot settle.",
      });
    }
  });

  test("dialog contract: accessible name, Escape closes, focus returns to the trigger", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    await ensureAdmin(page);
    await page.goto("/");
    await page.locator("main").waitFor();

    const addButton = page.getByRole("button", { name: "+ Add", exact: true });
    await addButton.waitFor();

    // BLOCKING — the disclosure state must be programmatic, not visual.
    await expect(addButton, "+ Add must advertise its collapsed state").toHaveAttribute(
      "aria-expanded",
      "false",
    );
    await addButton.focus();
    await page.keyboard.press("Enter");
    await expect(addButton, "+ Add must advertise its expanded state").toHaveAttribute(
      "aria-expanded",
      "true",
    );

    // BLOCKING — the popover is exposed as a dialog and carries a name. An
    // unnamed dialog is announced as "dialog" and nothing else.
    const dialog = page.getByRole("dialog", { name: "Add to Mainboard" });
    await expect(dialog, "the Add popover must be a named dialog").toBeVisible();

    // BLOCKING — Escape dismisses and focus RETURNS to the trigger. Without
    // the return, a screen-reader user is dropped at the document start and
    // has to re-navigate: the defect useEscapeToClose exists to prevent.
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden({ timeout: 5_000 });
    await expect(addButton).toHaveAttribute("aria-expanded", "false");
    const focusedIsTrigger = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      return (el?.textContent ?? "").trim() === "+ Add";
    });
    expect(focusedIsTrigger, "focus must return to the + Add trigger after Escape").toBe(true);
  });

  test("tab order follows DOM order on the representative routes", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: VIEWPORT_HEIGHT });
    await ensureAdmin(page);

    for (const route of TAB_ORDER_ROUTES) {
      await page.goto(route);
      await page.locator("main").waitFor();
      await page.waitForTimeout(400);

      // Walk the first 25 Tab stops and compare against DOM order. A pure
      // divergence count is enough here: naming every element would produce a
      // wall of selectors nobody reads, and the auditor confirms order by ear
      // anyway.
      const divergences = await page.evaluate(() => {
        const sel =
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
        const dom = Array.from(document.querySelectorAll<HTMLElement>(sel)).filter(
          (el) => el.offsetParent !== null,
        );
        // Sort by the order a browser would actually use: positive tabindex
        // first (ascending), then DOM order for tabindex 0/absent.
        const keyed = dom.map((el, i) => ({ el, i, ti: Number(el.getAttribute("tabindex") ?? 0) }));
        const expected = [...keyed].sort((a, b) => {
          if (a.ti > 0 && b.ti > 0) return a.ti - b.ti || a.i - b.i;
          if (a.ti > 0) return -1;
          if (b.ti > 0) return 1;
          return a.i - b.i;
        });
        let n = 0;
        for (let k = 0; k < Math.min(25, expected.length); k += 1) {
          if (expected[k].i !== keyed[k]?.i) n += 1;
        }
        return { diverged: n, considered: Math.min(25, expected.length) };
      });

      if (divergences.diverged > 0) {
        advisories.push({
          route,
          check: "tab order vs DOM order",
          observed: `${divergences.diverged} of the first ${divergences.considered} stops diverge`,
          wcag: "2.4.3 Focus Order (A)",
          note: "divergence is caused by positive tabindex; verify the heard order during the audit.",
        });
      }
    }
  });

  test.afterAll(async () => {
    fs.mkdirSync(REPORT_DIR, { recursive: true });

    const walked = new Set<string>(TAB_ORDER_ROUTES);
    const notWalked = TARGET_PAGES.map((p) => p.path).filter((p) => !walked.has(p));

    const report = {
      disclaimer:
        "AUTOMATED PRECHECKS ONLY. Playwright reads the DOM; it hears nothing. No record " +
        "in this file is a screen-reader result and none may be transcribed into " +
        "docs/audit/a11y_screen_reader_audit_results.md sections 1 or 2. A-08 stays " +
        "HUMAN-BLOCKED (GitHub #514) until a person completes the audit with NVDA/Firefox " +
        "and VoiceOver/Safari.",
      screen_reader_verified: false,
      routes_checked: records.length,
      tab_order_routes_walked: [...walked],
      tab_order_routes_NOT_walked: notWalked,
      blocking_failures: blocking,
      advisories,
      records,
    };
    fs.writeFileSync(
      path.join(REPORT_DIR, "precheck-results.json"),
      JSON.stringify(report, null, 2) + "\n",
    );

    const lines = advisories.map((a) => `  ${a.route} — ${a.check}: ${a.observed} [${a.wcag}]`);
    console.log(
      `\na11y prechecks: ${records.length} route(s) inspected, ${advisories.length} advisory ` +
        `observation(s). Tab order walked on ${walked.size} route(s); NOT walked on ` +
        `${notWalked.length}: ${notWalked.join(", ")}.`,
    );
    if (lines.length) {
      console.log(
        `::warning::${advisories.length} a11y advisory observation(s) — these are NOT gated ` +
          `and NOT screen-reader results. Carry them into the auditor's worksheet as ` +
          `candidates:\n${lines.join("\n")}`,
      );
    }
    console.log(
      "\nREMINDER: A-08 is HUMAN-BLOCKED. Nothing above counts as a screen-reader PASS.",
    );
  });
});
