#!/usr/bin/env node
// Dependency-audit gate for the npm workspaces (frontend/ and frontend/e2e/).
//
// `npm audit --audit-level=high` on its own cannot be a CI gate here: the
// frontend carries three high advisories whose only published fix is a MAJOR
// upgrade (eslint 10, or the react-router v8 migration that removes
// react-router-dom entirely). Silencing them with `continue-on-error` would
// leave a step that can never fail — not a gate at all.
//
// So this mirrors the idiom the a11y scan already uses (ACCEPTED_SERIOUS_RULES
// in frontend/e2e/specs/13-a11y-scan.spec.ts): a FROZEN allow-list of advisory
// ids. Anything at or above the threshold severity that is NOT on the list
// fails the build. Adding an id is a deliberate, reviewed act — the boundary is
// recorded, not waived.
//
// Usage: node scripts/npm-audit-gate.mjs <package-dir> [...more dirs]

import { execFileSync } from "node:child_process";
import * as path from "node:path";

const BLOCKING_SEVERITIES = ["high", "critical"];

// Frozen boundary, keyed by package dir (repo-relative). Every entry states the
// advisory, the package, and why it is not simply fixed. Revisit when the
// upstream fix stops being a major upgrade.
const FROZEN_ADVISORIES = {
  frontend: [
    // The two brace-expansion freezes that lived here were DROPPED 2026-08-03. Both
    // stated "npm's fix path is eslint@10, a major upgrade" — and that stopped being
    // true: brace-expansion 5.0.9 / 1.1.18 patch the same chain, so `npm audit fix`
    // now clears them in the lockfile with no major upgrade and no package.json
    // change. The gate's own "frozen but no longer reported" note is what surfaced
    // it. A freeze whose reason has expired is worse than no freeze — it silently
    // grants an exception nobody re-examined.
    {
      id: "GHSA-qwww-vcr4-c8h2",
      pkg: "react-router",
      reason:
        "RSC-mode CSRF bypass. This app is a Vite SPA on react-router-dom's BrowserRouter and never enables RSC mode. react-router-dom@7.18.1 pins react-router@7.18.1 exactly, so the only patched line is react-router@8.2.1+, i.e. the v8 migration that drops react-router-dom.",
    },
  ],
  "frontend/e2e": [],
};

function runAudit(dir) {
  try {
    // npm exits 1 when advisories exist, so success and failure both carry the
    // JSON payload we need; only a missing/broken payload is a real error.
    return execFileSync("npm", ["audit", "--json"], {
      cwd: dir,
      encoding: "utf8",
      maxBuffer: 32 * 1024 * 1024,
    });
  } catch (err) {
    if (err.stdout) return err.stdout;
    throw err;
  }
}

function collectFindings(report) {
  const findings = new Map();
  for (const [pkg, entry] of Object.entries(report.vulnerabilities ?? {})) {
    if (!BLOCKING_SEVERITIES.includes(entry.severity)) continue;
    for (const via of entry.via ?? []) {
      if (typeof via !== "object") continue;
      const id = String(via.url ?? "").split("/").pop();
      if (!id) continue;
      findings.set(id, { id, pkg, severity: entry.severity, title: via.title ?? "" });
    }
  }
  return [...findings.values()];
}

function gateDir(relDir) {
  const frozen = FROZEN_ADVISORIES[relDir];
  if (!frozen) throw new Error(`No frozen-advisory list declared for "${relDir}".`);
  const allowed = new Set(frozen.map((f) => f.id));

  const report = JSON.parse(runAudit(path.resolve(relDir)));
  const findings = collectFindings(report);
  const counts = report.metadata?.vulnerabilities ?? {};
  console.log(
    `\n${relDir}: high=${counts.high ?? 0} critical=${counts.critical ?? 0} ` +
      `(moderate=${counts.moderate ?? 0} low=${counts.low ?? 0})`,
  );

  const unrecorded = findings.filter((f) => !allowed.has(f.id));
  for (const f of findings) {
    const mark = allowed.has(f.id) ? "frozen  " : "UNKNOWN ";
    console.log(`  ${mark} ${f.id} ${f.severity} ${f.pkg} — ${f.title.slice(0, 90)}`);
  }
  for (const f of frozen) {
    if (!findings.some((x) => x.id === f.id)) {
      console.log(`  note     ${f.id} is frozen but no longer reported — drop it from the list.`);
    }
  }
  return unrecorded;
}

const dirs = process.argv.slice(2);
if (dirs.length === 0) {
  console.error("usage: node scripts/npm-audit-gate.mjs <package-dir> [...]");
  process.exit(2);
}

const unrecorded = dirs.flatMap((dir) => gateDir(dir).map((f) => ({ dir, ...f })));
if (unrecorded.length > 0) {
  console.error(
    `\nFAIL — ${unrecorded.length} unrecorded high/critical advisory(ies). Fix them, or ` +
      `record each one in FROZEN_ADVISORIES with a reason (scripts/npm-audit-gate.mjs):`,
  );
  for (const f of unrecorded) console.error(`  ${f.dir}: ${f.id} ${f.severity} ${f.pkg}`);
  process.exit(1);
}
console.log("\nOK — no unrecorded high/critical advisories.");
